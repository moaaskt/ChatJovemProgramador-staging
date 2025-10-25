import os
import json
import argparse
import time
import logging
from typing import List, Dict

import requests
from requests.exceptions import RequestException

# Importa o scraper existente
try:
    from utils.scraper import salvar_dados  # executado a partir da raiz do projeto
except Exception:
    # fallback caso o script seja executado dentro de utils/
    from scraper import salvar_dados  # type: ignore


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT_DIR, "dados.json")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def has_internet(url: str = "https://www.jovemprogramador.com.br/") -> bool:
    """Verifica conexão rápida com timeout curto."""
    try:
        requests.get(url, timeout=5)
        return True
    except RequestException:
        return False


def normalize_title(title: str) -> str:
    return " ".join(title.lower().strip().split())


def dedupe_noticias(noticias: List[Dict]) -> List[Dict]:
    """Remove duplicadas por link e por título normalizado, preservando a ordem."""
    seen_links = set()
    seen_titles = set()
    unique = []
    for item in noticias:
        link = item.get("link", "").strip()
        title = normalize_title(item.get("titulo", ""))
        key_link = link
        key_title = title
        if key_link and key_link in seen_links:
            continue
        if key_title and key_title in seen_titles:
            continue
        unique.append(item)
        if key_link:
            seen_links.add(key_link)
        if key_title:
            seen_titles.add(key_title)
    return unique


def safe_load_json(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def safe_write_json(path: str, data: Dict) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def update_data() -> Dict:
    """Tenta atualizar via scraper e aplica dedupe em noticias."""
    logging.info("Iniciando atualização on-demand...")
    salvar_dados()  # escreve dados.json
    data = safe_load_json(DATA_PATH)
    # Dedupe de notícias
    noticias = data.get("noticias", [])
    if isinstance(noticias, list) and noticias:
        deduped = dedupe_noticias(noticias)
        if len(deduped) != len(noticias):
            logging.info(f"Removidas {len(noticias) - len(deduped)} notícias duplicadas.")
            data["noticias"] = deduped
            safe_write_json(DATA_PATH, data)
    logging.info("Atualização concluída.")
    return data


def print_offline_cache(data: Dict, n: int = 5) -> None:
    noticias = data.get("noticias", [])
    if not noticias:
        logging.warning("Nenhuma notícia disponível no cache.")
        return
    logging.info(f"Mostrando últimas {min(n, len(noticias))} notícias do cache:")
    # Mostra do início assumindo ordem mais recente primeiro; ajuste se necessário
    for i, item in enumerate(noticias[:n], start=1):
        titulo = item.get("titulo", "(sem título)")
        link = item.get("link", "(sem link)")
        resumo = item.get("resumo")
        print(f"{i:02d}. {titulo}\n    Link: {link}")
        if resumo:
            print(f"    Resumo: {resumo}")


def main():
    parser = argparse.ArgumentParser(description="Atualização on-demand com fallback offline e dedupe")
    parser.add_argument("--n", type=int, default=5, help="Quantidade de notícias para exibir no modo offline")
    parser.add_argument("--offline-only", action="store_true", help="Não tentar baixar; usar somente cache")
    args = parser.parse_args()

    if args.offline_only:
        data = safe_load_json(DATA_PATH)
        logging.info("Modo offline-only ativado. Exibindo cache.")
        print_offline_cache(data, n=args.n)
        return

    if not has_internet():
        logging.warning("Sem internet detectada. Usando cache local.")
        data = safe_load_json(DATA_PATH)
        print_offline_cache(data, n=args.n)
        return

    try:
        data = update_data()
        # Feedback rápido pós-atualização
        noticias = data.get("noticias", [])
        logging.info(f"Cache atualizado. Total de notícias: {len(noticias)}")
    except Exception as e:
        logging.error(f"Falha na atualização: {e}. Exibindo cache local.")
        data = safe_load_json(DATA_PATH)
        print_offline_cache(data, n=args.n)


if __name__ == "__main__":
    main()