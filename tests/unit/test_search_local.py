import pytest

from utils.search_local import buscar_local


def test_busca_inscricao_link_acesso():
    dados = {
        "links_acesso": {
            "inscricao": "https://www.jovemprogramador.com.br/inscricao",
            "programa": "https://www.jovemprogramador.com.br/",
        }
    }
    hits = buscar_local("Quero fazer a inscrição", dados)
    assert hits, "Deve retornar pelo menos um hit"
    assert hits[0]["tipo"] == "inscricao"
    assert "inscricao" in hits[0]["titulo"].lower()


def test_busca_noticias_por_palavra_chave():
    dados = {
        "noticias": [
            {
                "titulo": "Hackathon 2025 abre inscrições",
                "link": "https://example.com/hackathon",
                "texto_completo": "O hackathon do Jovem Programador abre inscrições em outubro.",
            },
            {
                "titulo": "Apoio a empresas parceiras",
                "link": "https://example.com/empresas",
                "texto_completo": "Novos parceiros apoiam o programa.",
            },
        ]
    }
    hits = buscar_local("hackathon", dados)
    assert any(h["tipo"] == "noticia" for h in hits)
    assert any("Hackathon" in (h.get("titulo") or "") for h in hits)