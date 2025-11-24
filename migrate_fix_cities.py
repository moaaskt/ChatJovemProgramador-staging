#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migração completo, seguro e performático para corrigir dados de cidades no Firestore.

Este script:
- Lê todos os documentos da coleção 'leads'
- Usa EXATAMENTE a função normalize_city_name() REAL do projeto
- Reprocessa e atualiza cidades apenas quando necessário
- Registra logs detalhados de todas as operações
- Suporta modo dry-run (simulação) e apply (aplicação real)
- Detecta e corrige variações de "Palhoça" e demais cidades
- NUNCA sobrescreve dados válidos
- Gera estatísticas finais completas e relatório JSON
- Usa batches do Firestore para melhor performance
- Totalmente compatível com Windows/macOS/Linux e UTF-8

Uso:
    python migrate_fix_cities.py              # Modo DRY RUN (simulação)
    python migrate_fix_cities.py --apply      # Aplica alterações no Firestore
    python migrate_fix_cities.py --test       # Executa testes de validação
"""

import os
import sys
import argparse
import json
import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Força encoding UTF-8 no Windows
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Carrega variáveis de ambiente
load_dotenv()

# Adiciona o diretório raiz ao path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import services.firestore as firestore_module
    from services.firestore import (
        init_admin,
        normalize_city_name,
        _is_enabled,
        CIDADES_SANTA_CATARINA,
    )
except ImportError as e:
    print(f"ERRO CRITICO: Nao foi possivel importar modulos do projeto: {e}")
    print("Certifique-se de estar executando o script na raiz do projeto.")
    sys.exit(1)

# ============================================================================
# CONFIGURAÇÕES E CONSTANTES
# ============================================================================

# Tamanho do batch para atualizações do Firestore (otimização de performance)
BATCH_SIZE = 500

# Variações conhecidas de Palhoça para análise
PALHOCA_VARIATIONS = [
    "palhoca",
    "Palhoca",
    "palhoça",
    "PALHOCA",
    "palhocá",
    "PalhocA",
    "palhoca sc",
    "palhoça sc",
    "palhoca-sc",
    "palhoca, sc",
    "rua x, palhoca",
    "centro de palhoca",
    "palhoca centro",
    "bairro x palhoca",
    "moro em palhoca",
]

# ============================================================================
# CLASSES E ESTRUTURAS DE DADOS
# ============================================================================

class MigrationStats:
    """Armazena estatísticas detalhadas da migração."""
    
    def __init__(self):
        self.total_analyzed = 0
        self.total_corrected = 0
        self.total_ignored = 0
        self.total_errors = 0
        self.total_maintained = 0  # Cidades válidas mantidas
        self.palhoca_corrections = 0
        self.empty_to_other = 0
        self.other_corrections = 0
        self.corrections_by_city: Dict[str, int] = {}
        self.errors_list: List[Dict] = []
        self.corrections_log: List[Dict] = []
        self.maintained_log: List[Dict] = []  # Log de cidades válidas mantidas
        self.start_time = datetime.now()
        self.end_time = None
    
    def add_correction(self, old_value: str, new_value: str, doc_id: str, is_palhoca: bool = False):
        """Registra uma correção."""
        self.total_corrected += 1
        if is_palhoca:
            self.palhoca_corrections += 1
        if old_value in ("", None) or (isinstance(old_value, str) and not str(old_value).strip()):
            self.empty_to_other += 1
        else:
            self.other_corrections += 1
        
        city_key = new_value if new_value else "Outras cidades do Brasil"
        self.corrections_by_city[city_key] = self.corrections_by_city.get(city_key, 0) + 1
        
        self.corrections_log.append({
            "doc_id": doc_id,
            "old_value": old_value,
            "new_value": new_value,
            "is_palhoca": is_palhoca,
            "timestamp": datetime.now().isoformat(),
        })
    
    def add_maintained(self, city_value: str, doc_id: str):
        """Registra uma cidade válida que foi mantida (não alterada)."""
        self.total_maintained += 1
        self.maintained_log.append({
            "doc_id": doc_id,
            "city_value": city_value,
            "timestamp": datetime.now().isoformat(),
        })
    
    def add_error(self, doc_id: str, error_msg: str, cidade_bruta: str = None):
        """Registra um erro."""
        self.total_errors += 1
        self.errors_list.append({
            "doc_id": doc_id,
            "error": str(error_msg),
            "cidade_bruta": cidade_bruta,
            "timestamp": datetime.now().isoformat(),
        })
    
    def add_ignored(self):
        """Registra um documento ignorado (sem campo cidade)."""
        self.total_ignored += 1
    
    def finish(self):
        """Marca o fim da migração."""
        self.end_time = datetime.now()
    
    def get_duration(self) -> float:
        """Retorna a duração da migração em segundos."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_summary(self) -> Dict:
        """Retorna resumo completo das estatísticas."""
        return {
            "total_analyzed": self.total_analyzed,
            "total_corrected": self.total_corrected,
            "total_ignored": self.total_ignored,
            "total_maintained": self.total_maintained,
            "total_errors": self.total_errors,
            "palhoca_corrections": self.palhoca_corrections,
            "empty_to_other": self.empty_to_other,
            "other_corrections": self.other_corrections,
            "corrections_by_city": self.corrections_by_city,
            "duration_seconds": self.get_duration(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def is_palhoca_variation(cidade: str) -> bool:
    """Verifica se a cidade é uma variação de Palhoça."""
    if not cidade:
        return False
    try:
        cidade_lower = str(cidade).lower()
        return "palhoca" in cidade_lower or "palhoça" in cidade_lower or "palhocá" in cidade_lower
    except Exception:
        return False


def is_valid_city(cidade: str) -> bool:
    """
    Verifica se a cidade é válida (está na lista oficial de SC).
    
    Args:
        cidade: Nome da cidade a verificar
    
    Returns:
        True se a cidade está na lista oficial de SC, False caso contrário
    """
    if not cidade:
        return False
    try:
        cidade_stripped = str(cidade).strip()
        return cidade_stripped in CIDADES_SANTA_CATARINA
    except Exception:
        return False


def should_update_city(cidade_antiga: str, cidade_nova: str) -> bool:
    """
    Determina se a cidade deve ser atualizada de forma SEGURA.
    
    Regras de segurança:
    - NUNCA sobrescreve cidade válida (oficial de SC) com outra cidade válida
    - Atualiza apenas se:
      * cidade_antiga != cidade_nova (após normalização de espaços)
      * cidade_antiga está vazia/None e cidade_nova não está
      * cidade_antiga não está normalizada e cidade_nova está
      * cidade_antiga não é válida e cidade_nova é válida
    
    Returns:
        True se deve atualizar, False caso contrário
    """
    try:
        # Normaliza espaços para comparação
        antiga_norm = str(cidade_antiga).strip() if cidade_antiga else ""
        nova_norm = str(cidade_nova).strip() if cidade_nova else ""
        
        # Se ambas estão vazias, não atualiza
        if not antiga_norm and not nova_norm:
            return False
        
        # Se são iguais, não atualiza
        if antiga_norm == nova_norm:
            return False
        
        # PROTEÇÃO CRÍTICA: NUNCA sobrescreve cidade válida com outra cidade válida
        if is_valid_city(antiga_norm) and is_valid_city(nova_norm):
            # Ambas são válidas e diferentes - não sobrescreve
            return False
        
        # Se a antiga é válida e a nova não é, não atualiza (proteção)
        if is_valid_city(antiga_norm) and not is_valid_city(nova_norm):
            return False
        
        # Casos onde DEVE atualizar:
        # 1. Antiga vazia e nova preenchida
        if not antiga_norm and nova_norm:
            return True
        
        # 2. Antiga não válida e nova válida
        if not is_valid_city(antiga_norm) and is_valid_city(nova_norm):
            return True
        
        # 3. Antiga não normalizada e nova normalizada (mesma cidade)
        # Verifica se são variações da mesma cidade
        if antiga_norm.lower() != nova_norm.lower():
            # São diferentes, então atualiza
            return True
        
        return False
    except Exception as e:
        # Em caso de erro, não atualiza (segurança)
        print(f"AVISO: Erro ao verificar se deve atualizar: {e}")
        return False


def safe_normalize_city(cidade: str) -> Optional[str]:
    """
    Normaliza cidade de forma segura, capturando exceções.
    
    Args:
        cidade: Nome da cidade a normalizar
    
    Returns:
        str: Cidade normalizada ou None se não reconhecida
        None: Se ocorrer erro na normalização
    """
    try:
        if not cidade:
            return None
        # Usa EXATAMENTE a função do backend
        return normalize_city_name(str(cidade))
    except Exception as e:
        print(f"AVISO: Erro ao normalizar cidade '{cidade}': {e}")
        return None


def determine_final_city(cidade_antiga: str, cidade_normalizada: Optional[str]) -> str:
    """
    Determina a cidade final a ser salva de forma segura.
    
    Regras:
    1. Se normalizou para cidade de SC → usa normalizada
    2. Se não normalizou mas tem valor válido → mantém original (limitado)
    3. Se vazio/None → "Outras cidades do Brasil"
    
    Args:
        cidade_antiga: Cidade original do documento
        cidade_normalizada: Cidade normalizada pela função do backend
    
    Returns:
        str: Cidade final a ser salva
    """
    try:
        if cidade_normalizada:
            # Cidade reconhecida e normalizada
            return cidade_normalizada
        elif cidade_antiga and str(cidade_antiga).strip():
            # Cidade não reconhecida, mas tem valor válido
            # Limita tamanho para evitar problemas
            return str(cidade_antiga).strip()[:100]
        else:
            # Cidade vazia, None ou só espaços
            return "Outras cidades do Brasil"
    except Exception as e:
        print(f"AVISO: Erro ao determinar cidade final: {e}")
        return "Outras cidades do Brasil"


def validate_firestore_connection() -> Tuple[bool, str]:
    """
    Valida a conexão com o Firestore de forma robusta.
    
    Returns:
        Tuple[bool, str]: (sucesso, mensagem)
    """
    try:
        # Verifica se Firestore está habilitado
        if not _is_enabled():
            return False, "Firestore nao esta habilitado (AI_FIRESTORE_ENABLED=false)"
        
        # Acessa _db através do módulo para obter o valor atualizado
        _db = firestore_module._db
        
        # Verifica se _db foi inicializado
        if _db is None:
            return False, "Firestore nao foi inicializado corretamente"
        
        # Tenta fazer uma operação de teste (leitura simples)
        try:
            # Tenta acessar a coleção (sem ler documentos)
            firestore_module._db.collection("leads").limit(1).stream()
        except Exception as e:
            return False, f"Erro ao acessar Firestore: {e}"
        
        return True, "Conexao validada com sucesso"
    
    except Exception as e:
        return False, f"Erro ao validar Firestore: {e}"


# ============================================================================
# FUNÇÃO PRINCIPAL DE MIGRAÇÃO
# ============================================================================

def migrate_cities(dry_run: bool = True) -> MigrationStats:
    """
    Migra cidades nos documentos de leads do Firestore de forma segura e performática.
    
    Args:
        dry_run: Se True, apenas simula as mudanças sem aplicar
    
    Returns:
        MigrationStats: Estatísticas da migração
    """
    stats = MigrationStats()
    
    # Valida conexão com Firestore
    is_valid, message = validate_firestore_connection()
    if not is_valid:
        print(f"ERRO: {message}")
        print("Configure a variavel de ambiente AI_FIRESTORE_ENABLED=true")
        print("e verifique as credenciais do Firebase antes de executar a migracao.")
        return stats
    
    print("=" * 80)
    print("MIGRACAO DE CIDADES - FIRESTORE")
    print("=" * 80)
    print(f"Modo: {'DRY-RUN (simulacao)' if dry_run else 'APLICACAO (real)'}")
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Batch size: {BATCH_SIZE}")
    print("=" * 80)
    print()
    
    try:
        # Acessa _db através do módulo para obter o valor atualizado
        _db = firestore_module._db
        
        # Lê todos os documentos da coleção 'leads'
        print("Lendo documentos da coleção 'leads'...")
        leads_ref = _db.collection("leads")
        
        # Conta total de documentos para progresso
        try:
            total_docs = len(list(leads_ref.stream()))
            print(f"Total de documentos encontrados: {total_docs}")
        except Exception:
            total_docs = 0
            print("Nao foi possivel contar documentos (continuando...)")
        
        print("Processando documentos...")
        print()
        
        # Batch para atualizações (performance)
        batch = None
        batch_count = 0
        
        # Processa documentos
        for doc in leads_ref.stream():
            stats.total_analyzed += 1
            doc_id = doc.id
            data = doc.to_dict() or {}
            cidade_antiga = data.get("cidade")
            
            # Progresso visual
            if stats.total_analyzed % 100 == 0:
                progress = (stats.total_analyzed / total_docs * 100) if total_docs > 0 else 0
                print(f"Progresso: {stats.total_analyzed}/{total_docs} ({progress:.1f}%) - "
                      f"Corrigidos: {stats.total_corrected}, Mantidos: {stats.total_maintained}, "
                      f"Erros: {stats.total_errors}")
            
            try:
                # Pula se não tiver campo cidade
                if "cidade" not in data:
                    stats.add_ignored()
                    continue
                
                # Verifica se a cidade atual é válida (proteção)
                cidade_antiga_str = str(cidade_antiga) if cidade_antiga else ""
                if is_valid_city(cidade_antiga_str):
                    # Cidade já é válida - mantém e registra
                    stats.add_maintained(cidade_antiga_str, doc_id)
                    continue
                
                # Normaliza a cidade usando a função REAL do projeto
                cidade_normalizada = safe_normalize_city(cidade_antiga)
                
                # Determina a cidade final
                cidade_final = determine_final_city(cidade_antiga, cidade_normalizada)
                
                # Verifica se precisa atualizar (com proteção)
                if should_update_city(cidade_antiga_str, cidade_final):
                    # Verifica se é variação de Palhoça
                    is_palhoca = is_palhoca_variation(cidade_antiga_str)
                    
                    # Registra correção
                    stats.add_correction(
                        old_value=cidade_antiga_str,
                        new_value=cidade_final,
                        doc_id=doc_id,
                        is_palhoca=is_palhoca
                    )
                    
                    # Log detalhado (apenas primeiros 20 para não poluir)
                    if stats.total_corrected <= 20:
                        status_icon = "[PALHOCA]" if is_palhoca else "[CORRIGIDO]"
                        print(f"{status_icon} Doc: {doc_id[:20]}...")
                        print(f"   '{cidade_antiga_str}' -> '{cidade_final}'")
                        if is_palhoca:
                            print(f"   * Variacao de Palhoca detectada e corrigida")
                    
                    # Aplica atualização se não for dry-run
                    if not dry_run:
                        try:
                            # Inicializa batch se necessário
                            if batch is None:
                                batch = firestore_module._db.batch()
                                batch_count = 0
                            
                            # Adiciona atualização ao batch
                            doc_ref = doc.reference
                            batch.update(doc_ref, {"cidade": cidade_final})
                            batch_count += 1
                            
                            # Commit batch quando atingir o tamanho
                            if batch_count >= BATCH_SIZE:
                                batch.commit()
                                batch = None
                                batch_count = 0
                        
                        except Exception as e:
                            stats.add_error(doc_id, f"Erro ao atualizar: {e}", cidade_antiga_str)
                            print(f"ERRO ao atualizar documento {doc_id}: {e}")
                else:
                    # Não precisa atualizar (já está correto ou protegido)
                    if is_valid_city(cidade_final):
                        stats.add_maintained(cidade_final, doc_id)
                    else:
                        stats.add_ignored()
            
            except Exception as e:
                # Erro ao processar documento
                stats.add_error(doc_id, f"Erro ao processar: {e}", cidade_antiga_str if cidade_antiga else None)
                if stats.total_errors <= 10:  # Mostra apenas primeiros 10 erros
                    print(f"ERRO ao processar documento {doc_id}: {e}")
                continue
        
        # Commit batch final se houver
        if not dry_run and batch is not None and batch_count > 0:
            try:
                batch.commit()
                print(f"Commit final do batch: {batch_count} documentos atualizados")
            except Exception as e:
                print(f"ERRO ao fazer commit final do batch: {e}")
        
        # Finaliza estatísticas
        stats.finish()
        
        # Exibe estatísticas finais
        print()
        print("=" * 80)
        print("ESTATISTICAS FINAIS")
        print("=" * 80)
        summary = stats.get_summary()
        print(f"Total de documentos analisados: {summary['total_analyzed']}")
        print(f"Documentos corrigidos: {summary['total_corrected']}")
        print(f"  - Variacoes de Palhoca corrigidas: {summary['palhoca_corrections']}")
        print(f"  - Cidades vazias -> 'Outras cidades do Brasil': {summary['empty_to_other']}")
        print(f"  - Outras correcoes: {summary['other_corrections']}")
        print(f"Documentos mantidos (ja validos): {summary['total_maintained']}")
        print(f"Documentos ignorados (sem campo cidade): {summary['total_ignored']}")
        print(f"Erros encontrados: {summary['total_errors']}")
        print(f"Duracao: {summary['duration_seconds']:.2f} segundos")
        print()
        
        if summary['corrections_by_city']:
            print("Correcoes por cidade:")
            for cidade, count in sorted(summary['corrections_by_city'].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {cidade}: {count}")
            print()
        
        if dry_run:
            print("MODO DRY-RUN: Nenhuma mudanca foi aplicada.")
            print("Execute com --apply para aplicar as mudancas.")
        else:
            print("Migracao concluida com sucesso!")
            print(f"{summary['total_corrected']} documentos foram atualizados.")
        
        # Exibe erros se houver
        if stats.errors_list:
            print()
            print("=" * 80)
            print("ERROS ENCONTRADOS")
            print("=" * 80)
            for error in stats.errors_list[:10]:  # Mostra apenas os 10 primeiros
                print(f"Doc: {error['doc_id'][:20]}... | Erro: {error['error']}")
            if len(stats.errors_list) > 10:
                print(f"... e mais {len(stats.errors_list) - 10} erros")
            print()
        
        return stats
        
    except Exception as e:
        print(f"ERRO CRITICO durante a migracao: {e}")
        import traceback
        traceback.print_exc()
        stats.add_error("SYSTEM", f"Erro critico: {e}")
        stats.finish()
        return stats


# ============================================================================
# TESTES DE VALIDAÇÃO
# ============================================================================

def run_validation_tests() -> bool:
    """
    Executa testes de validação da função normalize_city_name().
    
    Testa casos críticos:
    - Variações de "Palhoça"
    - "Itá" vs "Itajaí" (não deve confundir)
    - Entradas irreconhecíveis retornam None
    - Cidades válidas não são sobrescritas
    
    Returns:
        bool: True se todos os testes passaram, False caso contrário
    """
    print("=" * 80)
    print("TESTES DE VALIDACAO - normalize_city_name()")
    print("=" * 80)
    print()
    
    all_passed = True
    
    # Teste 1: Variações de Palhoça (devem retornar "Palhoça")
    print("Teste 1: Variacoes de 'Palhoca' (devem retornar 'Palhoca')")
    print("-" * 80)
    palhoca_tests = [
        ("palhoca", "Palhoça"),
        ("Palhoça", "Palhoça"),
        ("PALHOCA", "Palhoça"),
        ("palhoca sc", "Palhoça"),
        ("palhoça sc", "Palhoça"),
        ("palhoca-sc", "Palhoça"),
        ("palhoca, sc", "Palhoça"),
        ("rua x, palhoca", "Palhoça"),
        ("centro de palhoca", "Palhoça"),
        ("palhoca centro", "Palhoça"),
    ]
    
    palhoca_passed = 0
    palhoca_failed = 0
    
    for test_input, expected in palhoca_tests:
        try:
            result = normalize_city_name(test_input)
            if result == expected:
                print(f"OK '{test_input}' -> '{result}'")
                palhoca_passed += 1
            else:
                print(f"FALHOU '{test_input}' -> '{result}' (esperado: '{expected}')")
                palhoca_failed += 1
                all_passed = False
        except Exception as e:
            print(f"ERRO ao testar '{test_input}': {e}")
            palhoca_failed += 1
            all_passed = False
    
    print()
    print(f"Resultado: {palhoca_passed}/{len(palhoca_tests)} passaram")
    print()
    
    # Teste 2: Casos críticos - Itá vs Itajaí
    print("Teste 2: Casos criticos - Ita vs Itajai")
    print("-" * 80)
    critical_tests = [
        ("Itá", "Itá"),  # Deve retornar "Itá"
        ("ita", None),  # Deve retornar None (muito curto, pode ser erro)
        ("Itajaí", "Itajaí"),  # Deve retornar "Itajaí"
        ("itajai", "Itajaí"),  # Deve retornar "Itajaí"
        ("itajaí", "Itajaí"),  # Deve retornar "Itajaí"
    ]
    
    critical_passed = 0
    critical_failed = 0
    
    for test_input, expected in critical_tests:
        try:
            result = normalize_city_name(test_input)
            if result == expected:
                print(f"OK '{test_input}' -> {result}")
                critical_passed += 1
            else:
                print(f"FALHOU '{test_input}' -> {result} (esperado: {expected})")
                critical_failed += 1
                all_passed = False
        except Exception as e:
            print(f"ERRO ao testar '{test_input}': {e}")
            critical_failed += 1
            all_passed = False
    
    print()
    print(f"Resultado: {critical_passed}/{len(critical_tests)} passaram")
    print()
    
    # Teste 3: Entradas irreconhecíveis (devem retornar None)
    print("Teste 3: Entradas irreconheciveis (devem retornar None)")
    print("-" * 80)
    unrecognized_tests = [
        "",
        " ",
        "xyz123",
        "cidade inexistente",
        "12345",
        "SC",  # Estado, não cidade
    ]
    
    unrecognized_passed = 0
    unrecognized_failed = 0
    
    for test_input in unrecognized_tests:
        try:
            result = normalize_city_name(test_input)
            if result is None:
                print(f"OK '{test_input}' -> None")
                unrecognized_passed += 1
            else:
                print(f"FALHOU '{test_input}' -> '{result}' (esperado: None)")
                unrecognized_failed += 1
                all_passed = False
        except Exception as e:
            print(f"ERRO ao testar '{test_input}': {e}")
            unrecognized_failed += 1
            all_passed = False
    
    print()
    print(f"Resultado: {unrecognized_passed}/{len(unrecognized_tests)} passaram")
    print()
    
    # Teste 4: Cidades válidas não são sobrescritas
    print("Teste 4: Cidades validas nao sao sobrescritas")
    print("-" * 80)
    valid_cities = [
        "Florianópolis",
        "Blumenau",
        "Joinville",
        "Itajaí",
        "Itá",
        "Palhoça",
    ]
    
    valid_passed = 0
    valid_failed = 0
    
    for test_input in valid_cities:
        try:
            result = normalize_city_name(test_input)
            if result == test_input:
                print(f"OK '{test_input}' -> '{result}' (mantido)")
                valid_passed += 1
            else:
                print(f"FALHOU '{test_input}' -> '{result}' (alterado)")
                valid_failed += 1
                all_passed = False
        except Exception as e:
            print(f"ERRO ao testar '{test_input}': {e}")
            valid_failed += 1
            all_passed = False
    
    print()
    print(f"Resultado: {valid_passed}/{len(valid_cities)} passaram")
    print()
    
    # Resumo final
    print("=" * 80)
    print("RESUMO DOS TESTES")
    print("=" * 80)
    total_tests = len(palhoca_tests) + len(critical_tests) + len(unrecognized_tests) + len(valid_cities)
    total_passed = palhoca_passed + critical_passed + unrecognized_passed + valid_passed
    print(f"Total de testes: {total_tests}")
    print(f"Testes passaram: {total_passed}")
    print(f"Testes falharam: {total_tests - total_passed}")
    print()
    
    if all_passed:
        print("SUCESSO: Todos os testes passaram!")
    else:
        print("ERRO: Alguns testes falharam. Revise a funcao normalize_city_name().")
    print()
    
    return all_passed


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    """Função principal do script."""
    parser = argparse.ArgumentParser(
        description="Migra e normaliza cidades nos documentos de leads do Firestore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python migrate_fix_cities.py              # Modo DRY RUN (simulacao)
  python migrate_fix_cities.py --apply      # Aplica mudancas no Firestore
  python migrate_fix_cities.py --test       # Executa testes de validacao
        """
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica as mudancas no Firestore (use com cuidado!)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Executa testes de validacao da funcao normalize_city_name()"
    )
    
    args = parser.parse_args()
    
    # Modo de teste
    if args.test:
        success = run_validation_tests()
        sys.exit(0 if success else 1)
    
    # Valida argumentos
    if args.apply:
        print("ATENCAO: Modo APLICACAO ativado!")
        print("As mudancas serao aplicadas no Firestore.")
        response = input("Deseja continuar? (sim/nao): ").strip().lower()
        if response not in ("sim", "s", "yes", "y"):
            print("Operacao cancelada pelo usuario.")
            return
        dry_run = False
    else:
        dry_run = True
    
    # Inicializa Firestore
    print("Inicializando Firestore...")
    try:
        init_admin()
    except Exception as e:
        print(f"ERRO ao inicializar Firestore: {e}")
        sys.exit(1)
    
    # Valida conexão
    is_valid, message = validate_firestore_connection()
    if not is_valid:
        print(f"ERRO: {message}")
        print("Verifique as credenciais e a variavel AI_FIRESTORE_ENABLED")
        sys.exit(1)
    
    print("Firestore inicializado com sucesso")
    print()
    
    # Executa migração
    stats = migrate_cities(dry_run=dry_run)
    
    # Salva relatório JSON completo
    report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "summary": stats.get_summary(),
        "corrections": stats.corrections_log,
        "maintained": stats.maintained_log[:100],  # Limita a 100 para não ficar muito grande
        "errors": stats.errors_list,
    }
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"Relatorio JSON salvo em: {report_file}")
    except Exception as e:
        print(f"AVISO: Nao foi possivel salvar relatorio: {e}")


if __name__ == "__main__":
    main()
