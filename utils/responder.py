import os
import json
try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None  # type: ignore
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (como a sua API key) do arquivo .env
load_dotenv()


class Chatbot:
    # O método __init__ é o construtor da classe. É executado uma única vez quando o chatbot é criado.
    def __init__(self):
        print("🤖 Inicializando o Chatbot com Gemini...")

        # 1. Configura a chave da API do Google Gemini de forma segura a partir do arquivo .env
        api_key = os.getenv("GEMINI_API_KEY")
        self.llm_available = True
        if (genai is None) or (not api_key):
            self.llm_available = False
        else:
            try:
                genai.configure(api_key=api_key)
            except Exception:
                self.llm_available = False

        # 2. Carrega toda a base de conhecimento do arquivo dados.json para a memória (self.dados)
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(base_dir)
            dados_path = os.path.join(root_dir, "dados.json")
            with open(dados_path, "r", encoding="utf-8") as f:
                self.dados = json.load(f)
        except FileNotFoundError:
            # Não interrompe a execução; usa fallback com base vazia
            self.dados = {}
            self.dados_indisponiveis = True

        # 3. Prepara o "super prompt" inicial com todas as regras e dados
        self.contexto_inicial = self._criar_contexto()
        # 3.1. Prompt curto de sistema (tom jovem, escopo estrito, chips)
        self.prompt_sistema = self._criar_prompt_sistema()
        
        # 4. Inicializa o modelo de IA e a sessão de chat
        if self.llm_available:
            self.model = genai.GenerativeModel("gemini-1.5-flash")
            self.chat_session = self.model.start_chat(history=[])
            
            # 5. Primeiro, envie o prompt de sistema; depois, o contexto inicial
            try:
                self.chat_session.send_message(self.prompt_sistema)
            except Exception:
                pass
            try:
                self.chat_session.send_message(self.contexto_inicial)
            except Exception:
                pass
        else:
            self.model = None
            self.chat_session = None
        print("✅ Chatbot pronto e online!")

    # Prompt curto orientando tom, escopo e chips
    def _criar_prompt_sistema(self):
        chips = "[!noticias] [!inscricao] [!cursos] [!contatos] [!materiais]"
        site = "https://www.jovemprogramador.com.br"
        return (
            "Você é o 'Leozin', jovem, direto e focado no Programa Jovem Programador.\n"
            "Siga estas diretrizes:\n"
            "• Tom jovem e objetivo; respostas curtas, claras, com 3–5 bullets quando útil.\n"
            "• Máximo de 1 link por resposta, sempre oficial.\n"
            f"• Sugira chips quando a pergunta for vaga: {chips}.\n"
            "• Escopo estrito: responda somente sobre o Programa Jovem Programador; recuse política/ideologia.\n"
            "• Ao citar notícias do dados.json, use o formato 'Título — Data' quando houver.\n"
            f"Link oficial: {site}"
        )

    # Este método privado é o coração da inteligência, responsável por montar o prompt.
    def _criar_contexto(self):

        # Para cada seção, ele pega os dados do self.dados e formata em um texto legível.
        # Define um texto padrão caso a seção não seja encontrada no JSON.
        
        # Formata a seção de dúvidas
        duvidas_texto = "".join(
            [
                f"• {pergunta}: {resposta}\n"
                for pergunta, resposta in self.dados.get("duvidas", {}).items()
            ]
        )

        # Formata a seção 'notícias'
        todas_as_noticias = self.dados.get("noticias", [])
        # OTIMIZAÇÃO: Pega apenas as 5 notícias mais recentes para não sobrecarregar a IA
        noticias_para_contexto = todas_as_noticias[:5]

        noticias_texto = "Nenhuma notícia recente disponível."
        if isinstance(noticias_para_contexto, list) and noticias_para_contexto:
            noticias_texto = "".join(
                [
                    f"• Título: {n.get('titulo', '')}\n  Texto Completo: {n.get('texto_completo', '')}\n  Link: {n.get('link', '')}\n\n"
                    for n in noticias_para_contexto
                ]
            )

        # Formata a seção 'Como ser professor'
        prof_info = self.dados.get("ser_professor", {})
        prof_texto = "Informação sobre como se tornar professor não foi encontrada."
        if prof_info and prof_info.get("vagas_abertas"):
            vagas = prof_info.get("vagas_abertas", {})
            interesse = prof_info.get("registrar_interesse", {})
            prof_texto = (
                f"Existem duas maneiras de se candidatar:\n"
                f"1. Para Vagas Abertas: {vagas.get('texto', '')} O link do portal é: {vagas.get('link', '')}\n"
                f"2. Para Registrar Interesse: {interesse.get('texto', '')} A página para isso é: {interesse.get('link_pagina', '')}"
            )

        # Formata a seção 'Hackathon' de forma robusta, adicionando as partes que encontrar
        hackathon_info = self.dados.get("hackathon", {})
        hackathon_texto = "Informação sobre o Hackathon não foi encontrada."
        if hackathon_info:
            partes_texto = []
            if hackathon_info.get("descricao"):
                partes_texto.append(hackathon_info.get("descricao"))
            if hackathon_info.get("link_video"):
                partes_texto.append(f"Para saber mais, assista ao vídeo principal: {hackathon_info.get('link_video')}")
            if hackathon_info.get("noticias"):
                partes_texto.append("\nÚLTIMAS NOTÍCIAS SOBRE O HACKATHON:")
                noticias_formatadas = "".join(
                    [
                        f"- Título: {n.get('titulo')}\n  Resumo: {n.get('resumo')}\n  Leia mais em: {n.get('link')}\n"
                        for n in hackathon_info.get("noticias", [])
                    ]
                )
                partes_texto.append(noticias_formatadas)
            if partes_texto:
                hackathon_texto = "\n\n".join(partes_texto)

        # Formata a seção 'Redes Sociais'
        redes_info = self.dados.get("redes_sociais", {})
        redes_texto = "Não encontrei informações sobre as redes sociais oficiais do programa."
        if redes_info:
            lista_redes = [f"- {nome}: {url}" for nome, url in redes_info.items()]
            redes_texto = (
                "Você pode encontrar e seguir o Jovem Programador nas seguintes redes sociais:\n"
                + "\n".join(lista_redes)
            )

        # Formata as listas de Apoiadores, Patrocinadores e Parceiros como texto corrido
        apoiadores_texto = "Não encontrei a lista de empresas apoiadoras."
        if self.dados.get("apoiadores"):
            apoiadores_texto = "O programa conta com o apoio de: " + ", ".join([apoiador.get("nome", "") for apoiador in self.dados.get("apoiadores")]) + "."
        
        patrocinadores_texto = "Não encontrei a lista de empresas patrocinadoras."
        if self.dados.get("patrocinadores"):
            patrocinadores_texto = "O programa é patrocinado por: " + ", ".join([p.get("nome", "") for p in self.dados.get("patrocinadores")]) + "."

        parceiros_texto = "Não encontrei a lista de parceiros do programa."
        if self.dados.get("parceiros"):
            parceiros_texto = "Os parceiros do programa são: " + ", ".join([p.get("nome", "") for p in self.dados.get("parceiros")]) + "."
            
        # Formata a seção 'Links de Acesso'
        acesso_info = self.dados.get("links_acesso", {})
        acesso_texto = "Não encontrei os links para as áreas de acesso."
        if acesso_info:
            link_aluno = acesso_info.get("aluno", "Link não disponível")
            link_empresa = acesso_info.get("empresa", "Link não disponível")
            acesso_texto = f"Existem portais de acesso específicos. O link para a Área do Aluno é: {link_aluno}. O link para a Área da Empresa é: {link_empresa}."

        # A montagem do PROMPT FINAL que define todo o comportamento do chatbot
        contexto = f"""
        Você é um assistente virtual chamado "leo" ou "leozin" especialista no programa Jovem Programador.
        Sua única e exclusiva função é responder perguntas sobre este programa.
        Sua personalidade é amigável, prestativa e você usa emojis de forma leve e ocasional 😊. 
        Evite repetir saudações como "Olá" ou "Oi" em todas as respostas. Use saudações apenas no início da conversa.

        Use APENAS as informações oficiais fornecidas abaixo para basear 100% de suas respostas.
        NÃO invente informações e NÃO use conhecimento externo.

        --- INFORMAÇÕES OFICIAIS ---
        
        SOBRE O PROGRAMA:
        {self.dados.get("sobre", "Informação não disponível.")}

        DÚVIDAS FREQUENTES:
        {duvidas_texto}
        
        ÚLTIMAS NOTÍCIAS:
        {noticias_texto}

        SOBRE O BLOG:
        A seção 'Blog' e a seção 'ÚLTIMAS NOTÍCIAS' do site Jovem Programador são a mesma coisa e apresentam o mesmo conteúdo. Se um usuário perguntar sobre o blog, use as informações disponíveis em 'ÚLTIMAS NOTÍCIAS' para formular a resposta.

        COMO SER PROFESSOR:
        {prof_texto}
        
        SOBRE O HACKATHON:
        {hackathon_texto}
        
        REDES SOCIAIS:
        {redes_texto}
        
        APOIADORES:
        {apoiadores_texto}
        
        PATROCINADORES:
        {patrocinadores_texto}
        
        PARCEIROS:
        {parceiros_texto}
        
        PORTAIS DE ACESSO:
        {acesso_texto}

        --- REGRAS DE COMPORTAMENTO ---
        1. Se a pergunta do usuário não tiver relação com o programa Jovem Programador, recuse educadamente. Diga algo como: "Minha especialidade é apenas o programa Jovem Programador. Posso ajudar com algo sobre isso? 😉"
        2. Mantenha as respostas claras e diretas.
        3. Seja sempre simpático e profissional.
        """
        return contexto

    # Este método é chamado toda vez que o usuário envia uma nova mensagem.
    def gerar_resposta(self, user_message):
        # Validação simples para não enviar mensagens vazias para a API
        if not user_message.strip():
            return "Por favor, digite sua pergunta! Estou aqui para ajudar. 😄"

        # Interceptação de intents por comando
        intent = user_message.strip().lower()
        if intent.startswith("!noticias"):
            return self._intent_noticias()
        if intent.startswith("!inscricao"):
            return self._intent_inscricao()
        if intent.startswith("!cursos"):
            return self._intent_cursos()
        if intent.startswith("!contatos"):
            return self._intent_contatos()
        if intent.startswith("!materiais"):
            return self._intent_materiais()

        # Fallback amigável se o LLM estiver indisponível (sem import ou sem chave)
        if not getattr(self, "llm_available", True) or (self.chat_session is None):
            return (
                "Estou temporariamente sem conexão com o serviço de IA. 😅\n"
                "Use as ações rápidas ou tente novamente em instantes."
            )

        try:
            # Envia apenas a pergunta do usuário para a sessão de chat, que já tem o contexto.
            response = self.chat_session.send_message(user_message)
            return response.text
        except Exception as e:
            # Tratamento de erro caso a comunicação com a API do Gemini falhe.
            print(f"❌ Erro ao se comunicar com a API do Gemini: {e}")
            return "Ops, parece que estou com um probleminha de conexão... 😅 Poderia tentar de novo em um instante?"

    # --- Intents helpers ---
    def _intent_noticias(self):
        noticias = self.dados.get("noticias", [])
        if not isinstance(noticias, list) or not noticias:
            return "Não encontrei notícias recentes no momento."
        latest = noticias[:5]
        bullets = []
        link_mais = None
        for n in latest:
            titulo = n.get("titulo", "")
            data = n.get("data") or n.get("data_publicacao") or n.get("quando")
            bullets.append(f"• {titulo}" + (f" — {data}" if data else ""))
            if not link_mais and n.get("link"):
                link_mais = n.get("link")
        resposta = "\n".join(bullets)
        if link_mais:
            resposta += f"\nVeja mais: {link_mais}"
        return resposta

    def _intent_inscricao(self):
        acesso = self.dados.get("links_acesso", {})
        link_aluno = acesso.get("aluno")
        if link_aluno:
            return (
                "• Inscrição: acesse a Área do Aluno e preencha o cadastro.\n"
                f"Link: {link_aluno}"
            )
        return "Informações de inscrição não disponíveis no momento."

    def _intent_cursos(self):
        sobre = self.dados.get("sobre", "")
        duvidas = self.dados.get("duvidas", {})
        pontos_duvidas = list(duvidas.items())[:2]
        bullets = ["• Cursos focados em programação e empregabilidade."]
        if sobre:
            bullets.append("• Visão geral: " + (sobre[:120] + ("…" if len(sobre) > 120 else "")))
        for p, r in pontos_duvidas:
            bullets.append(f"• {p}: {r[:80]}" + ("…" if len(r) > 80 else ""))
        return "\n".join(bullets)

    def _intent_contatos(self):
        redes = self.dados.get("redes_sociais", {})
        if not redes:
            return "Redes sociais oficiais não encontradas."
        lista = [f"• {nome}: {url}" for nome, url in redes.items()]
        return "\n".join(lista)

    def _intent_materiais(self):
        redes = self.dados.get("redes_sociais", {})
        youtube = redes.get("YouTube") or redes.get("youtube")
        noticias = self.dados.get("noticias", [])
        link_blog = None
        for n in noticias:
            if n.get("link"):
                link_blog = n.get("link")
                break
        bullets = []
        if youtube:
            bullets.append(f"• Vídeos e aulas: {youtube}")
        if link_blog:
            bullets.append(f"• Blog/Notícias: {link_blog}")
        if not bullets:
            return "Materiais como YouTube ou blog não foram encontrados."
        return "\n".join(bullets)