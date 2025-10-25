<div align="center">
  <img src="https://www.jovemprogramador.com.br/images/jovemprogramador_logo.png" alt="Logo Jovem Programador" width="150"/>
  <h1><b>Chatbot Leozin - Assistente Virtual do Jovem Programador</b></h1>
  <p>
    Um chatbot especialista construído com Python e IA Generativa (Google Gemini) para responder a todas as dúvidas sobre o programa Jovem Programador, utilizando dados extraídos em tempo real do site oficial.
  </p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.x-blue.svg" alt="Python 3.x">
    <img src="https://img.shields.io/badge/Framework-Flask-black.svg" alt="Flask">
    <img src="https://img.shields.io/badge/IA-Google%20Gemini-4285F4.svg" alt="Google Gemini">
    <img src="https://img.shields.io/badge/Web%20Scraping-BeautifulSoup-orange.svg" alt="BeautifulSoup">
    <img src="https://img.shields.io/badge/Licença-MIT-green.svg" alt="Licença MIT">
  </p>
</div>

---

## 🚀 Sobre o Projetos

O "Leozin" é um assistente virtual projetado para ser a fonte central e confiável de informações sobre o programa **Jovem Programador**. Ele resolve o problema de informações dispersas pelo site oficial, oferecendo respostas instantâneas, 24/7, para alunos, pais e empresas interessadas.

O grande diferencial deste projeto é o seu ciclo de vida completo:
1.  **Coleta de Dados Inteligente:** Um robô de web scraping (`scraper.py`) visita o site oficial e extrai meticulosamente todas as informações relevantes.
2.  **Base de Conhecimento Centralizada:** Os dados coletados são estruturados e salvos em um arquivo `dados.json`.
3.  **Cérebro de IA Especialista:** Um chatbot (`responder.py`), alimentado pela API do Google Gemini, é "doutrinado" com essa base de conhecimento para se tornar um especialista no assunto, com persona e regras de comportamento definidas.

## ✨ Funcionalidades

O chatbot é capaz de responder sobre praticamente todas as áreas do programa, graças ao seu robusto sistema de coleta de dados:

-   ✅ **Informações Gerais:** Sobre o programa, dúvidas frequentes e cidades participantes.
-   ✅ **Notícias e Blog:** Extrai o conteúdo completo de mais de 100 notícias.
-   ✅ **Oportunidades:** Como se tornar professor ou participar do Hackathon.
-   ✅ **Ecossistema:** Mapeia a lista completa de Apoiadores, Patrocinadores e Parceiros.
-   ✅ **Conectividade:** Fornece os links para todas as Redes Sociais e Portais de Acesso.

## 🛠️ Tecnologias Utilizadas

Este projeto foi construído com as seguintes tecnologias:

| Tecnologia      | Propósito                                                    |
| :-------------- | :----------------------------------------------------------- |
| **Python** | Linguagem principal para toda a lógica do backend.           |
| **Flask** | Micro-framework web para servir a API do chatbot.            |
| **Google Gemini** | Modelo de IA Generativa para o processamento de linguagem natural. |
| **Requests** | Biblioteca para realizar as requisições HTTP ao site.        |
| **BeautifulSoup4**| Biblioteca para analisar o HTML e extrair os dados (web scraping). |
| **Dotenv** | Para gerenciar as variáveis de ambiente de forma segura.     |

## ⚙️ Guia de Instalação e Execução

Siga estes passos para executar o projeto em sua máquina local.

#### 1. Clone o Repositório
```bash
git clone [https://github.com/moaaskt/ChatJovemProgramador.git](https://github.com/moaaskt/ChatJovemProgramador.git)
cd ChatJovemProgramador
```

#### 2. Crie e Ative um Ambiente Virtual
```bash
# Criar o ambiente
python -m venv venv

# Ativar no Windows
.\venv\Scripts\activate

# Ativar no macOS/Linux
source venv/bin/activate
```

#### 3. Instale as Dependências
```bash
pip install -r requirements.txt
```

#### 4. Configure a Chave da API
Crie um arquivo chamado `.env` na raiz do projeto e adicione sua chave da API do Google Gemini:
```
GEMINI_API_KEY="SUA_CHAVE_SECRETA_AQUI"
```

#### 5. Execute o Scraper
Este comando irá criar o arquivo `dados.json` com as informações mais recentes do site.
```bash
python utils/scraper.py
```

#### 6. Inicie o Chatbot
Execute o `app.py` para iniciar o chatbot no modo de terminal.
```bash
python app.py
```
Pronto! Agora você pode conversar com o "Leozin".

## Antes da apresentação
Para garantir que os dados estejam atualizados e deduplicados, execute:
```bash
python utils/update_on_demand.py --n 5
```

## 🤝 Contribuidores

Este projeto foi desenvolvido com a colaboração de uma equipe incrível. Agradecimentos a todos que contribuíram!

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/moaaskt">
        <img src="https://github.com/moaaskt.png?size=100" width="100px;" alt="Foto de Moacir"/>
        <br />
        <sub><b>Moacir</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/fabiof8">
        <img src="https://github.com/fabiof8.png?size=100" width="100px;" alt="Foto de Fabio"/>
        <br />
        <sub><b>Fabio</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/isaqmm">
        <img src="https://github.com/isaqmm.png?size=100" width="100px;" alt="Foto de Isaque"/>
        <br />
        <sub><b>Isaque</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/Pridss">
        <img src="https://github.com/Pridss.png?size=100" width="100px;" alt="Foto de Pridss"/>
        <br />
        <sub><b>Pridss</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/VitinhoBatista0103">
        <img src="https://github.com/VitinhoBatista0103.png?size=100" width="100px;" alt="Foto de VitinhoBatista"/>
        <br />
        <sub><b>VitinhoBatista</b></sub>
      </a>
    </td>
  </tr>
</table>

---

## 📜 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.
