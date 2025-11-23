#!/usr/bin/env python3
"""
Script de migração completo e seguro para corrigir dados de cidades no Firestore.

Este script:
- Lê todos os documentos da coleção 'leads'
- Usa a função normalize_city_name() REAL do projeto
- Reprocessa e atualiza cidades apenas quando necessário
- Registra logs detalhados de todas as operações
- Suporta modo dry-run (simulação) e apply (aplicação real)
- Detecta e corrige variações de "Palhoça" e demais cidades
- Evita sobrescritas perigosas
- Gera estatísticas finais completas

Uso:
    python migrate_fix_cities.py          # Modo DRY RUN (simulação)
    python migrate_fix_cities.py --apply  # Aplica alterações no Firestore
"""

import os
import sys
import argparse
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Adiciona o diretório raiz ao path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.firestore import (
    init_admin,
    normalize_city_name,
    _is_enabled,
    _db,
    CIDADES_SANTA_CATARINA,
)

# ============================================================================
# CONFIGURAÇÕES E CONSTANTES
# ============================================================================

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
    """Armazena estatísticas da migração."""
    
    def __init__(self):
        self.total_analyzed = 0
        self.total_corrected = 0
        self.total_ignored = 0
        self.total_errors = 0
        self.palhoca_corrections = 0
        self.empty_to_other = 0
        self.other_corrections = 0
        self.corrections_by_city: Dict[str, int] = {}
        self.errors_list: List[Dict] = []
        self.corrections_log: List[Dict] = []
    
    def add_correction(self, old_value: str, new_value: str, doc_id: str, is_palhoca: bool = False):
        """Registra uma correção."""
        self.total_corrected += 1
        if is_palhoca:
            self.palhoca_corrections += 1
        if old_value in ("", None) or (isinstance(old_value, str) and not old_value.strip()):
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
        })
    
    def add_error(self, doc_id: str, error_msg: str, cidade_bruta: str = None):
        """Registra um erro."""
        self.total_errors += 1
        self.errors_list.append({
            "doc_id": doc_id,
            "error": error_msg,
            "cidade_bruta": cidade_bruta,
        })
    
    def add_ignored(self):
        """Registra um documento ignorado (já correto)."""
        self.total_ignored += 1
    
    def get_summary(self) -> Dict:
        """Retorna resumo das estatísticas."""
        return {
            "total_analyzed": self.total_analyzed,
            "total_corrected": self.total_corrected,
            "total_ignored": self.total_ignored,
            "total_errors": self.total_errors,
            "palhoca_corrections": self.palhoca_corrections,
            "empty_to_other": self.empty_to_other,
            "other_corrections": self.other_corrections,
            "corrections_by_city": self.corrections_by_city,
        }

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def is_palhoca_variation(cidade: str) -> bool:
    """Verifica se a cidade é uma variação de Palhoça."""
    if not cidade:
        return False
    cidade_lower = str(cidade).lower()
    return "palhoca" in cidade_lower or "palhoça" in cidade_lower or "palhocá" in cidade_lower


def should_update_city(cidade_antiga: str, cidade_nova: str) -> bool:
    """
    Determina se a cidade deve ser atualizada.
    
    Retorna True se:
    - cidade_antiga != cidade_nova (após normalização de espaços)
    - cidade_antiga está vazia/None e cidade_nova não está
    - cidade_antiga não está normalizada e cidade_nova está
    """
    # Normaliza espaços para comparação
    antiga_norm = str(cidade_antiga).strip() if cidade_antiga else ""
    nova_norm = str(cidade_nova).strip() if cidade_nova else ""
    
    # Se ambas estão vazias, não atualiza
    if not antiga_norm and not nova_norm:
        return False
    
    # Se são diferentes, atualiza
    if antiga_norm != nova_norm:
        return True
    
    return False


def safe_normalize_city(cidade: str) -> Optional[str]:
    """
    Normaliza cidade de forma segura, capturando exceções.
    
    Returns:
        str: Cidade normalizada ou None se não reconhecida
        None: Se ocorrer erro na normalização
    """
    try:
        if not cidade:
            return None
        return normalize_city_name(cidade)
    except Exception as e:
        print(f"⚠️  ERRO ao normalizar cidade '{cidade}': {e}")
        return None


def determine_final_city(cidade_antiga: str, cidade_normalizada: Optional[str]) -> str:
    """
    Determina a cidade final a ser salva.
    
    Regras:
    1. Se normalizou para cidade de SC → usa normalizada
    2. Se não normalizou mas tem valor válido → mantém original (limitado)
    3. Se vazio/None → "Outras cidades do Brasil"
    """
    if cidade_normalizada:
        # Cidade reconhecida e normalizada
        return cidade_normalizada
    elif cidade_antiga and str(cidade_antiga).strip():
        # Cidade não reconhecida, mas tem valor válido
        return str(cidade_antiga).strip()[:100]
    else:
        # Cidade vazia, None ou só espaços
        return "Outras cidades do Brasil"


# ============================================================================
# FUNÇÃO PRINCIPAL DE MIGRAÇÃO
# ============================================================================

def migrate_cities(dry_run: bool = True) -> MigrationStats:
    """
    Migra cidades nos documentos de leads do Firestore.
    
    Args:
        dry_run: Se True, apenas simula as mudanças sem aplicar
    
    Returns:
        MigrationStats: Estatísticas da migração
    """
    stats = MigrationStats()
    
    if not _is_enabled():
        print("❌ ERRO: Firestore não está habilitado (AI_FIRESTORE_ENABLED=false)")
        print("   Configure a variável de ambiente antes de executar a migração.")
        return stats
    
    if _db is None:
        print("❌ ERRO: Firestore não foi inicializado corretamente.")
        print("   Verifique as credenciais do Firebase.")
        return stats
    
    print("=" * 80)
    print("🔍 MIGRAÇÃO DE CIDADES - FIRESTORE")
    print("=" * 80)
    print(f"Modo: {'DRY-RUN (simulação)' if dry_run else 'APLICAÇÃO (real)'}")
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    try:
        # Lê todos os documentos da coleção 'leads'
        print("📖 Lendo documentos da coleção 'leads'...")
        leads_ref = _db.collection("leads")
        leads = leads_ref.stream()
        
        print("🔄 Processando documentos...")
        print()
        
        for doc in leads:
            stats.total_analyzed += 1
            doc_id = doc.id
            data = doc.to_dict() or {}
            cidade_antiga = data.get("cidade")
            
            try:
                # Pula se não tiver campo cidade
                if "cidade" not in data:
                    stats.add_ignored()
                    continue
                
                # Normaliza a cidade usando a função REAL do projeto
                cidade_normalizada = safe_normalize_city(cidade_antiga)
                
                # Determina a cidade final
                cidade_final = determine_final_city(cidade_antiga, cidade_normalizada)
                
                # Verifica se precisa atualizar
                if should_update_city(cidade_antiga, cidade_final):
                    # Verifica se é variação de Palhoça
                    is_palhoca = is_palhoca_variation(cidade_antiga)
                    
                    # Registra correção
                    stats.add_correction(
                        old_value=cidade_antiga,
                        new_value=cidade_final,
                        doc_id=doc_id,
                        is_palhoca=is_palhoca
                    )
                    
                    # Log detalhado
                    status_icon = "🔧" if is_palhoca else "📝"
                    print(f"{status_icon} [{'SIMULAÇÃO' if dry_run else 'CORRIGIDO'}] Doc: {doc_id[:20]}...")
                    print(f"   '{cidade_antiga}' → '{cidade_final}'")
                    if is_palhoca:
                        print(f"   ⭐ Variação de Palhoça detectada e corrigida")
                    print()
                    
                    # Aplica atualização se não for dry-run
                    if not dry_run:
                        try:
                            doc.reference.update({"cidade": cidade_final})
                        except Exception as e:
                            stats.add_error(doc_id, f"Erro ao atualizar: {e}", cidade_antiga)
                            print(f"❌ ERRO ao atualizar documento {doc_id}: {e}")
                else:
                    # Não precisa atualizar (já está correto)
                    stats.add_ignored()
            
            except Exception as e:
                # Erro ao processar documento
                stats.add_error(doc_id, f"Erro ao processar: {e}", cidade_antiga)
                print(f"❌ ERRO ao processar documento {doc_id}: {e}")
                continue
        
        # Exibe estatísticas finais
        print()
        print("=" * 80)
        print("📊 ESTATÍSTICAS FINAIS")
        print("=" * 80)
        summary = stats.get_summary()
        print(f"Total de documentos analisados: {summary['total_analyzed']}")
        print(f"Documentos corrigidos: {summary['total_corrected']}")
        print(f"  - Variações de Palhoça corrigidas: {summary['palhoca_corrections']}")
        print(f"  - Cidades vazias → 'Outras cidades do Brasil': {summary['empty_to_other']}")
        print(f"  - Outras correções: {summary['other_corrections']}")
        print(f"Documentos ignorados (já corretos): {summary['total_ignored']}")
        print(f"Erros encontrados: {summary['total_errors']}")
        print()
        
        if summary['corrections_by_city']:
            print("Correções por cidade:")
            for cidade, count in sorted(summary['corrections_by_city'].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {cidade}: {count}")
            print()
        
        if dry_run:
            print("⚠️  MODO DRY-RUN: Nenhuma mudança foi aplicada.")
            print("   Execute com --apply para aplicar as mudanças.")
        else:
            print("✅ Migração concluída com sucesso!")
            print(f"   {summary['total_corrected']} documentos foram atualizados.")
        
        # Exibe erros se houver
        if stats.errors_list:
            print()
            print("=" * 80)
            print("⚠️  ERROS ENCONTRADOS")
            print("=" * 80)
            for error in stats.errors_list[:10]:  # Mostra apenas os 10 primeiros
                print(f"Doc: {error['doc_id'][:20]}... | Erro: {error['error']}")
            if len(stats.errors_list) > 10:
                print(f"... e mais {len(stats.errors_list) - 10} erros")
            print()
        
        return stats
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO durante a migração: {e}")
        import traceback
        traceback.print_exc()
        stats.add_error("SYSTEM", f"Erro crítico: {e}")
        return stats


# ============================================================================
# TESTES DE VALIDAÇÃO
# ============================================================================

def run_validation_tests():
    """
    Executa testes de validação da função normalize_city_name().
    
    Testa:
    - 10 variações diferentes de "Palhoça"
    - Entradas irreconhecíveis retornam None
    - Cidades válidas não são sobrescritas
    """
    import io
    import sys
    # Força encoding UTF-8 no Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 80)
    print("TESTES DE VALIDACAO")
    print("=" * 80)
    print()
    
    # Teste 1: Variações de Palhoça
    print("Teste 1: Variações de 'Palhoça' (devem retornar 'Palhoça')")
    print("-" * 80)
    palhoca_tests = [
        "palhoca",
        "Palhoça",
        "PALHOCA",
        "palhoca sc",
        "palhoça sc",
        "palhoca-sc",
        "palhoca, sc",
        "rua x, palhoca",
        "centro de palhoca",
        "palhoca centro",
    ]
    
    palhoca_passed = 0
    palhoca_failed = 0
    
    for test_input in palhoca_tests:
        result = normalize_city_name(test_input)
        if result == "Palhoça":
            print(f"✅ '{test_input}' → '{result}'")
            palhoca_passed += 1
        else:
            print(f"❌ '{test_input}' → '{result}' (esperado: 'Palhoça')")
            palhoca_failed += 1
    
    print()
    print(f"Resultado: {palhoca_passed}/{len(palhoca_tests)} passaram")
    print()
    
    # Teste 2: Entradas irreconhecíveis
    print("Teste 2: Entradas irreconhecíveis (devem retornar None)")
    print("-" * 80)
    unrecognized_tests = [
        "",
        " ",
        "xyz123",
        "cidade inexistente",
        "12345",
    ]
    
    unrecognized_passed = 0
    unrecognized_failed = 0
    
    for test_input in unrecognized_tests:
        result = normalize_city_name(test_input)
        if result is None:
            print(f"✅ '{test_input}' → None")
            unrecognized_passed += 1
        else:
            print(f"⚠️  '{test_input}' → '{result}' (esperado: None)")
            unrecognized_failed += 1
    
    print()
    print(f"Resultado: {unrecognized_passed}/{len(unrecognized_tests)} passaram")
    print()
    
    # Teste 3: Cidades válidas não são sobrescritas
    print("Teste 3: Cidades válidas não são sobrescritas")
    print("-" * 80)
    valid_cities = [
        "Florianópolis",
        "Blumenau",
        "Joinville",
        "Itajaí",
    ]
    
    valid_passed = 0
    valid_failed = 0
    
    for test_input in valid_cities:
        result = normalize_city_name(test_input)
        if result == test_input:
            print(f"✅ '{test_input}' → '{result}' (mantido)")
            valid_passed += 1
        else:
            print(f"⚠️  '{test_input}' → '{result}' (alterado)")
            valid_failed += 1
    
    print()
    print(f"Resultado: {valid_passed}/{len(valid_cities)} passaram")
    print()
    
    # Resumo final
    print("=" * 80)
    print("📊 RESUMO DOS TESTES")
    print("=" * 80)
    total_tests = len(palhoca_tests) + len(unrecognized_tests) + len(valid_cities)
    total_passed = palhoca_passed + unrecognized_passed + valid_passed
    print(f"Total de testes: {total_tests}")
    print(f"Testes passaram: {total_passed}")
    print(f"Testes falharam: {total_tests - total_passed}")
    print()
    
    if total_passed == total_tests:
        print("✅ Todos os testes passaram!")
    else:
        print("⚠️  Alguns testes falharam. Revise a função normalize_city_name().")
    print()


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
  python migrate_fix_cities.py              # Modo DRY RUN (simulação)
  python migrate_fix_cities.py --apply      # Aplica mudanças no Firestore
  python migrate_fix_cities.py --test       # Executa testes de validação
        """
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica as mudanças no Firestore (use com cuidado!)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Executa testes de validação da função normalize_city_name()"
    )
    
    args = parser.parse_args()
    
    # Modo de teste
    if args.test:
        run_validation_tests()
        return
    
    # Valida argumentos
    if args.apply:
        print("⚠️  ATENÇÃO: Modo APLICAÇÃO ativado!")
        print("   As mudanças serão aplicadas no Firestore.")
        response = input("   Deseja continuar? (sim/não): ").strip().lower()
        if response not in ("sim", "s", "yes", "y"):
            print("❌ Operação cancelada pelo usuário.")
            return
        dry_run = False
    else:
        dry_run = True
    
    # Inicializa Firestore
    print("🔧 Inicializando Firestore...")
    init_admin()
    
    if not _is_enabled() or _db is None:
        print("❌ ERRO: Não foi possível inicializar o Firestore")
        print("   Verifique as credenciais e a variável AI_FIRESTORE_ENABLED")
        sys.exit(1)
    
    print("✅ Firestore inicializado com sucesso")
    print()
    
    # Executa migração
    stats = migrate_cities(dry_run=dry_run)
    
    # Salva relatório em arquivo (opcional)
    if stats.corrections_log:
        report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "summary": stats.get_summary(),
            "corrections": stats.corrections_log[:100],  # Limita a 100 para não ficar muito grande
            "errors": stats.errors_list[:50],  # Limita a 50
        }
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            print(f"📄 Relatório salvo em: {report_file}")
        except Exception as e:
            print(f"⚠️  Não foi possível salvar relatório: {e}")


if __name__ == "__main__":
    main()

