import requests
from bs4 import BeautifulSoup

# URL da página de inscrições
URL = "https://www.jovemprogramador.com.br/inscricoes-jovem-programador/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def debug():
    print(f"--- Acessando {URL} ---")
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Erro ao acessar site: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # Vamos focar na DIV principal de conteúdo
    # Tentando achar containers comuns
    containers = soup.find_all("div", class_=["fh5co-heading", "container", "row", "col-md-12"])

    if not containers:
        print("Nenhum container padrão encontrado. Buscando no body inteiro.")
        containers = [soup.body]

    print("\n--- LINKS ENCONTRADOS ---")
    encontrados = 0
    for container in containers:
        links = container.find_all("a")
        for a in links:
            text = a.get_text(" ", strip=True)
            href = a.get("href", "")
            classes = a.get("class", [])

            # Filtra apenas links relevantes para não poluir o log
            if href and len(text) > 2:
                print(f"[LINK] Texto: '{text}' | Href: '{href}' | Classes: {classes}")
                encontrados += 1

    if encontrados == 0:
        print("Nenhum link encontrado nos containers. Tentando varredura global...")
        for a in soup.find_all("a"):
            print(f"[GLOBAL] Texto: '{a.get_text(strip=True)}' | Href: '{a.get('href','')}'")

if __name__ == "__main__":
    debug()
