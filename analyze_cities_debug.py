#!/usr/bin/env python3
"""
Script de análise forense para identificar problemas com cidades no Firestore.
Este script lê todos os documentos de leads e analisa os valores de cidade.
"""

import os
import sys
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
    CITY_EQUIVALENCE_MAP,
)

def analyze_cities():
    """Analisa todas as cidades no Firestore e identifica problemas."""
    if not _is_enabled():
        print("❌ ERRO: Firestore não está habilitado")
        return
    
    if _db is None:
        print("❌ ERRO: Firestore não foi inicializado")
        return
    
    print("=" * 80)
    print("🔍 ANÁLISE FORENSE - CIDADES NO FIRESTORE")
    print("=" * 80)
    print()
    
    try:
        leads = _db.collection("leads").stream()
        
        # Estatísticas
        stats = {
            "total": 0,
            "palhoca_variations": [],
            "empty_or_none": 0,
            "normalized_correctly": 0,
            "not_normalized": [],
            "unique_cities": set(),
        }
        
        print("📊 COLETANDO DADOS...")
        print()
        
        for doc in leads:
            stats["total"] += 1
            data = doc.to_dict() or {}
            cidade_bruta = data.get("cidade")
            
            # Coleta cidade única
            if cidade_bruta:
                stats["unique_cities"].add(str(cidade_bruta))
            
            # Verifica variações de Palhoça
            if cidade_bruta:
                cidade_lower = str(cidade_bruta).lower()
                if "palhoca" in cidade_lower or "palhoça" in cidade_lower or "palhocá" in cidade_lower:
                    normalized = normalize_city_name(cidade_bruta)
                    stats["palhoca_variations"].append({
                        "doc_id": doc.id,
                        "cidade_bruta": cidade_bruta,
                        "normalized": normalized,
                        "is_correct": normalized == "Palhoça"
                    })
            
            # Verifica vazios
            if not cidade_bruta or not str(cidade_bruta).strip():
                stats["empty_or_none"] += 1
            
            # Testa normalização
            if cidade_bruta:
                normalized = normalize_city_name(cidade_bruta)
                if normalized:
                    if normalized in CIDADES_SANTA_CATARINA:
                        stats["normalized_correctly"] += 1
                    else:
                        stats["not_normalized"].append({
                            "cidade_bruta": cidade_bruta,
                            "normalized": normalized
                        })
                else:
                    stats["not_normalized"].append({
                        "cidade_bruta": cidade_bruta,
                        "normalized": None
                    })
        
        # Exibe resultados
        print("=" * 80)
        print("📊 ESTATÍSTICAS GERAIS")
        print("=" * 80)
        print(f"Total de documentos: {stats['total']}")
        print(f"Cidades vazias/None: {stats['empty_or_none']}")
        print(f"Cidades normalizadas corretamente: {stats['normalized_correctly']}")
        print(f"Cidades não normalizadas: {len(stats['not_normalized'])}")
        print(f"Cidades únicas encontradas: {len(stats['unique_cities'])}")
        print()
        
        # Exibe variações de Palhoça
        print("=" * 80)
        print("🔍 VARIAÇÕES DE 'PALHOÇA' ENCONTRADAS")
        print("=" * 80)
        if stats["palhoca_variations"]:
            for item in stats["palhoca_variations"]:
                status = "✅ CORRETO" if item["is_correct"] else "❌ PROBLEMA"
                print(f"{status} | Doc: {item['doc_id'][:20]}... | '{item['cidade_bruta']}' → '{item['normalized']}'")
        else:
            print("Nenhuma variação de 'Palhoça' encontrada nos documentos.")
        print()
        
        # Exibe cidades não normalizadas (primeiras 20)
        print("=" * 80)
        print("⚠️  CIDADES NÃO NORMALIZADAS (primeiras 20)")
        print("=" * 80)
        for i, item in enumerate(stats["not_normalized"][:20], 1):
            print(f"{i}. '{item['cidade_bruta']}' → {item['normalized']}")
        if len(stats["not_normalized"]) > 20:
            print(f"... e mais {len(stats['not_normalized']) - 20} cidades não normalizadas")
        print()
        
        # Exibe todas as cidades únicas (primeiras 30)
        print("=" * 80)
        print("📋 TODAS AS CIDADES ÚNICAS ENCONTRADAS (primeiras 30)")
        print("=" * 80)
        sorted_cities = sorted(stats["unique_cities"])
        for i, cidade in enumerate(sorted_cities[:30], 1):
            normalized = normalize_city_name(cidade)
            status = "✅" if normalized == "Palhoça" else ("⚠️" if normalized else "❌")
            print(f"{i}. {status} '{cidade}' → '{normalized}'")
        if len(sorted_cities) > 30:
            print(f"... e mais {len(sorted_cities) - 30} cidades únicas")
        print()
        
        # Testa casos específicos
        print("=" * 80)
        print("🧪 TESTES DE NORMALIZAÇÃO - CASOS ESPECÍFICOS")
        print("=" * 80)
        test_cases = [
            "palhoca",
            "Palhoça",
            "PALHOCA",
            "palhoca sc",
            "palhoça sc",
            "sou de palhoca",
            "centro de palhoca",
            "bairro x palhoca",
            "palhoca centro",
            "rua x, palhoca",
            "moro em palhoca SC",
            "palhocá",
            "Palhoca",
            "PalhocA",
        ]
        
        for test in test_cases:
            result = normalize_city_name(test)
            status = "✅" if result == "Palhoça" else "❌"
            print(f"{status} '{test}' → '{result}'")
        print()
        
        # Verifica CITY_EQUIVALENCE_MAP
        print("=" * 80)
        print("🗺️  VERIFICAÇÃO DO CITY_EQUIVALENCE_MAP")
        print("=" * 80)
        palhoca_keys = [k for k in CITY_EQUIVALENCE_MAP.keys() if "palhoca" in k.lower()]
        print(f"Chaves relacionadas a 'Palhoça' no mapa: {len(palhoca_keys)}")
        for key in palhoca_keys:
            print(f"  - '{key}' → '{CITY_EQUIVALENCE_MAP[key]}'")
        print()
        
        # Verifica se Palhoça está na lista oficial
        print("=" * 80)
        print("✅ VERIFICAÇÃO DA LISTA OFICIAL")
        print("=" * 80)
        if "Palhoça" in CIDADES_SANTA_CATARINA:
            print("✅ 'Palhoça' está na lista CIDADES_SANTA_CATARINA")
        else:
            print("❌ 'Palhoça' NÃO está na lista CIDADES_SANTA_CATARINA")
        print()
        
    except Exception as e:
        print(f"❌ ERRO durante análise: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Função principal."""
    print("🔧 Inicializando Firestore...")
    init_admin()
    
    if not _is_enabled() or _db is None:
        print("❌ ERRO: Não foi possível inicializar o Firestore")
        return
    
    print("✅ Firestore inicializado")
    print()
    
    analyze_cities()


if __name__ == "__main__":
    main()

