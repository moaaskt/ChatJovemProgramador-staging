#!/usr/bin/env python3
"""
Script de migração para normalizar cidades nos documentos de leads do Firestore.

Este script:
- Lê todos os documentos da coleção 'leads'
- Normaliza o campo 'cidade' usando a mesma função do backend
- Atualiza documentos com cidades inválidas ou variações incorretas
- Suporta modo dry-run para preview antes de aplicar

Uso:
    python migrate_cities.py --dry-run    # Preview das mudanças
    python migrate_cities.py --apply      # Aplicar mudanças
"""

import os
import sys
import argparse
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
)

# Lista de variações problemáticas de Palhoça que devem ser corrigidas
PALHOCA_VARIATIONS = [
    "",
    " ",
    "  ",
    "palhoca",
    "Palhoca",
    "palhocá",
    "PalhocA",
    "palhoça",  # minúsculo
    "palhoca sc",
    "palhoça sc",
]


def migrate_cities(dry_run: bool = True):
    """
    Migra cidades nos documentos de leads do Firestore.
    
    Args:
        dry_run: Se True, apenas mostra o que seria alterado sem aplicar mudanças
    """
    if not _is_enabled():
        print("❌ ERRO: Firestore não está habilitado (AI_FIRESTORE_ENABLED=false)")
        print("   Configure a variável de ambiente antes de executar a migração.")
        return
    
    if _db is None:
        print("❌ ERRO: Firestore não foi inicializado corretamente.")
        print("   Verifique as credenciais do Firebase.")
        return
    
    print("=" * 80)
    print("🔍 MIGRAÇÃO DE CIDADES - FIRESTORE")
    print("=" * 80)
    print(f"Modo: {'DRY-RUN (preview)' if dry_run else 'APLICAÇÃO (real)'}")
    print("=" * 80)
    print()
    
    try:
        # Lê todos os documentos da coleção 'leads'
        print("📖 Lendo documentos da coleção 'leads'...")
        leads_ref = _db.collection("leads")
        leads = leads_ref.stream()
        
        stats = {
            "total": 0,
            "atualizados": 0,
            "ignorados": 0,
            "corrigidos_vazios": 0,
            "corrigidos_palhoca": 0,
            "outros_corrigidos": 0,
        }
        
        updates_log = []
        
        for doc in leads:
            stats["total"] += 1
            doc_id = doc.id
            data = doc.to_dict() or {}
            cidade_atual = data.get("cidade")
            
            # Pula se não tiver campo cidade
            if "cidade" not in data:
                stats["ignorados"] += 1
                continue
            
            # Normaliza a cidade usando a mesma função do backend
            cidade_normalizada = normalize_city_name(cidade_atual)
            
            # Determina a cidade final
            if cidade_normalizada:
                # Cidade reconhecida e normalizada
                cidade_final = cidade_normalizada
            elif cidade_atual and str(cidade_atual).strip():
                # Cidade não reconhecida, mas tem valor válido
                cidade_final = str(cidade_atual).strip()[:100]
            else:
                # Cidade vazia, None ou só espaços
                cidade_final = "Outras cidades do Brasil"
            
            # Verifica se precisa atualizar
            cidade_atual_str = str(cidade_atual) if cidade_atual is not None else ""
            cidade_final_str = str(cidade_final) if cidade_final is not None else ""
            
            if cidade_atual_str.strip() != cidade_final_str.strip():
                # Precisa atualizar
                stats["atualizados"] += 1
                
                # Classifica o tipo de correção
                cidade_atual_lower = cidade_atual_str.lower().strip() if cidade_atual_str else ""
                
                if not cidade_atual_str or not cidade_atual_str.strip():
                    stats["corrigidos_vazios"] += 1
                    tipo = "CORRIGIDO (vazio)"
                elif cidade_atual_lower in [v.lower() for v in PALHOCA_VARIATIONS]:
                    stats["corrigidos_palhoca"] += 1
                    tipo = "CORRIGIDO (Palhoça)"
                else:
                    stats["outros_corrigidos"] += 1
                    tipo = "ATUALIZADO"
                
                log_entry = f"[{tipo}] '{cidade_atual_str}' → '{cidade_final_str}' (doc id: {doc_id})"
                updates_log.append(log_entry)
                
                if not dry_run:
                    # Aplica a atualização
                    doc.reference.update({"cidade": cidade_final})
                    print(f"✅ {log_entry}")
            else:
                # Não precisa atualizar
                stats["ignorados"] += 1
                if cidade_atual_str:
                    log_entry = f"[IGNORADO] '{cidade_atual_str}' (já está correto) (doc id: {doc_id})"
                    updates_log.append(log_entry)
        
        # Exibe estatísticas
        print()
        print("=" * 80)
        print("📊 ESTATÍSTICAS")
        print("=" * 80)
        print(f"Total de documentos processados: {stats['total']}")
        print(f"Documentos que precisam atualização: {stats['atualizados']}")
        print(f"  - Cidades vazias corrigidas: {stats['corrigidos_vazios']}")
        print(f"  - Variações de Palhoça corrigidas: {stats['corrigidos_palhoca']}")
        print(f"  - Outras correções: {stats['outros_corrigidos']}")
        print(f"Documentos ignorados (já corretos): {stats['ignorados']}")
        print("=" * 80)
        print()
        
        # Exibe log detalhado
        if updates_log:
            print("=" * 80)
            print("📝 LOG DETALHADO DE MUDANÇAS")
            print("=" * 80)
            for entry in updates_log:
                print(entry)
            print("=" * 80)
            print()
        
        if dry_run:
            print("⚠️  MODO DRY-RUN: Nenhuma mudança foi aplicada.")
            print("   Execute com --apply para aplicar as mudanças.")
        else:
            print("✅ Migração concluída com sucesso!")
            print(f"   {stats['atualizados']} documentos foram atualizados.")
        
    except Exception as e:
        print(f"❌ ERRO durante a migração: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Função principal do script."""
    parser = argparse.ArgumentParser(
        description="Migra e normaliza cidades nos documentos de leads do Firestore"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo preview: mostra o que seria alterado sem aplicar mudanças"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica as mudanças no Firestore (use com cuidado!)"
    )
    
    args = parser.parse_args()
    
    # Valida argumentos
    if not args.dry_run and not args.apply:
        print("❌ ERRO: Você deve especificar --dry-run ou --apply")
        print()
        print("Uso:")
        print("  python migrate_cities.py --dry-run    # Preview das mudanças")
        print("  python migrate_cities.py --apply      # Aplicar mudanças")
        sys.exit(1)
    
    if args.dry_run and args.apply:
        print("❌ ERRO: Não é possível usar --dry-run e --apply ao mesmo tempo")
        sys.exit(1)
    
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
    dry_run = args.dry_run
    migrate_cities(dry_run=dry_run)


if __name__ == "__main__":
    main()

