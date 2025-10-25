import re
import unicodedata
from typing import List, Dict


def strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(s).lower().strip())


def buscar_local(query: str, dados: Dict, top_n: int = 5) -> List[Dict]:
    q = norm(query)
    hits: List[Dict] = []

    # Notícias
    for n in dados.get("noticias", []):
        texto = " ".join([
            n.get("titulo", ""),
            n.get("resumo", ""),
            n.get("texto_completo", ""),
        ])
        if q in norm(texto):
            hits.append({
                "tipo": "noticia",
                "titulo": n.get("titulo"),
                "data": n.get("data"),
                "link": n.get("link"),
                "resumo": n.get("resumo"),
            })

    # Inscrição (links_acesso)
    acesso = dados.get("links_acesso", {})
    for key, url in acesso.items():
        if ("inscr" in norm(key) or "inscr" in q) and url:
            hits.append({"tipo": "inscricao", "titulo": "Inscrição", "link": url})

    # Cursos (sobre/duvidas)
    sobre = dados.get("sobre", "")
    if "curso" in q and "curso" in norm(sobre):
        hits.append({"tipo": "curso", "titulo": "Sobre os cursos", "link": None, "resumo": sobre})

    duvidas = dados.get("duvidas", {})
    for pergunta, resposta in duvidas.items():
        if any(k in norm(pergunta + " " + resposta) for k in ["curso", "inscr", "matricula", "material"]):
            hits.append({"tipo": "faq", "titulo": pergunta, "link": None, "resumo": resposta})

    # Contatos (redes_sociais)
    redes = dados.get("redes_sociais", {})
    if "contat" in q or "rede" in q:
        for nome, url in redes.items():
            hits.append({"tipo": "contato", "titulo": f"Contato ({nome})", "link": url})

    # Materiais (YouTube)
    if "material" in q or "apostila" in q:
        if redes.get("youtube"):
            hits.append({"tipo": "materiais", "titulo": "YouTube oficial", "link": redes["youtube"]})

    ordem = {"inscricao": 0, "curso": 1, "faq": 2, "noticia": 3, "materiais": 4, "contato": 5}
    hits.sort(key=lambda h: ordem.get(h["tipo"], 99))
    return hits[:top_n]