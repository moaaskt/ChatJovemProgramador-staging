import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (como a sua API key) do arquivo .env
load_dotenv()


class Chatbot:
    # O método __init__ é o construtor da classe. É executado uma única vez quando o chatbot é criado.
    def __init__(self):
        print("🤖 Inicializando o Chatbot com Gemini...")

        # 1. Configura a chave da API do Google Gemini de forma segura a partir do arquivo .env
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY ausente no .env")
        genai.configure(api_key=api_key)

        # 2. Carrega toda a base de conhecimento do arquivo dados.json para a memória (self.dados)
        try:
            with open("dados.json", "r", encoding="utf-8") as f:
                self.dados = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                "Arquivo 'dados.json' não encontrado! Execute o scraper.py primeiro."
            )

        # 3. Prepara o "super prompt" inicial com todas as regras e dados
        self.contexto_inicial = self._criar_contexto()

        # 4. Logar versão do SDK e tentar inicializar dinamicamente um modelo suportado
        sdk_version = getattr(genai, "__version__", "desconhecida")
        print(f"[Gemini] SDK version: {sdk_version}")

        # Tentar listar modelos e armazenar nomes (todos) e os que suportam generateContent
        self.available_models = []
        self.available_models_supported = []
        try:
            for m in genai.list_models():
                name = getattr(m, "name", "")
                self.available_models.append(name)
                if getattr(m, "supported_generation_methods", None) and "generateContent" in m.supported_generation_methods:
                    self.available_models_supported.append(name)
        except Exception as e:
            print("[Gemini] Falha ao listar modelos:", e)
        if self.available_models:
            print("[Gemini] Modelos listados:")
            for nm in self.available_models:
                print(" -", nm)
        if self.available_models_supported:
            print("[Gemini] Modelos com generateContent:")
            for nm in self.available_models_supported:
                print(" -", nm)


     # utils/responder.py (Linha 80)
        CANDIDATOS = [
          "gemini-pro-latest",
          "gemini-1.5-flash",  
          "gemini-1.5-pro",
         ]

        initialized = False
        for c in CANDIDATOS:
            if self._try_model(c):
                initialized = True
                break
        if not initialized:
            # Fallback dinâmico: tentar os modelos listados que suportam generateContent
            for nm in self.available_models_supported:
                # Passar nome possivelmente já prefixado; o helper tratará
                cleaned = nm
                if cleaned.startswith("models/"):
                    cleaned = cleaned[len("models/"):]
                if self._try_model(cleaned):
                    initialized = True
                    break
        if not initialized:
            raise RuntimeError("Nenhum modelo Gemini disponível")

        print(f"[Gemini] Modelo selecionado: {self.model_name}")

        # 5. Envia o contexto inicial para a IA para "doutriná-la" sobre como se comportar
        sent = False
        try:
            self.chat_session.send_message(self.contexto_inicial)
            sent = True
        except Exception as e:
            print("[Gemini] Falha ao enviar contexto com", getattr(self, 'model_name', None), "->", e)
            # Tentar fallback para outro modelo suportado
            for nm in self.available_models_supported:
                # Evitar tentar o mesmo modelo novamente
                if nm == getattr(self, 'model_name', None):
                    continue
                cleaned = nm
                if cleaned.startswith("models/"):
                    cleaned = cleaned[len("models/"):]
                if self._try_model(cleaned):
                    try:
                        self.chat_session.send_message(self.contexto_inicial)
                        sent = True
                        break
                    except Exception as e2:
                        print("[Gemini] Contexto falhou com", getattr(self, 'model_name', None), "->", e2)
                        continue

        if not sent:
            raise RuntimeError("Nenhum modelo Gemini disponível para envio de contexto inicial")

        print("✅ Chatbot pronto e online!")

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
        Você é Leo, o assistente oficial do Programa Jovem Programador.
        Tom: jovem, especialista, motivador e levemente informal, mantendo profissionalismo.
        Emojis: use pontualmente para dar ênfase (🚀, 💡, 🎓, 👉), sem excesso.
        Formatação: use quebras de linha curtas e respostas interessantes, evitando textões.
        Blindagem: responda APENAS com base no conteúdo abaixo. Se a resposta não estiver no texto, diga que o melhor é verificar no site oficial ou acionar um humano.
        Proibição: não recomende cursos externos ou plataformas fora do Programa Jovem Programador.

        Política de resposta (AIDA):
        1) Acolhimento: reconheça a iniciativa do usuário de estudar ou evoluir na carreira (ex.: "Ótima iniciativa querer estudar!" 💡).
        2) Benefício/Desejo: destaque benefícios reais do programa (ex.: "O curso é gratuito e conecta você com empresas parceiras." 🎓).
        3) Chamada para Ação (CTA com link): entregue o link com uma chamada clara, nunca de forma seca (ex.: "Para garantir sua vaga ou ver o edital, acesse: [link]" 👉).

        Inscrições e anos futuros:
        - Quando perguntarem sobre "Inscrições 2026" ou edições futuras, se houver dados com datas no texto abaixo, cite-os de forma objetiva.
        - Se não houver datas específicas, oriente a acompanhar o site para não perder prazos e inclua CTA com link de inscrição.

        Captura de lead:
        - Somente após entregar o CTA quando o usuário demonstrar intenção clara, convide gentilmente a compartilhar nome, cidade, estado e idade, um item por vez.
        - Não solicite dados antes de responder a dúvidas objetivas sobre inscrição/site/edital.

        Concisão: responda em 3 a 5 linhas, a menos que o usuário peça detalhes técnicos.

        --- INFORMAÇÕES OFICIAIS ---

        SOBRE O PROGRAMA:
        {self.dados.get("sobre", "Informação não disponível.")}

        --- INSCRIÇÕES E EDITAIS ---
        {self.dados.get("inscricoes", {}).get("texto_geral", "Consulte o site.")}
        Link para Inscrição: {self.dados.get("inscricoes", {}).get("link_inscricao") or "Consulte a página oficial de inscrições."}
        Link do Edital/Regulamento: {self.dados.get("inscricoes", {}).get("link_edital") or "Consulte o regulamento na página de inscrição."}
        Se o link do edital não existir, entregue o Link para Inscrição com CTA e informe que as regras estão lá.

        DÚVIDAS FREQUENTES:
        {duvidas_texto}

        ÚLTIMAS NOTÍCIAS:
        {noticias_texto}

        COMO SER PROFESSOR:
        {prof_texto}

        HACKATHON:
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

        """
        return contexto

    def _try_model(self, name: str) -> bool:
        try:
            n = name if name.startswith("models/") else f"models/{name}"
            self.model = genai.GenerativeModel(n)
            self.chat_session = self.model.start_chat(history=[])
            self.model_name = n
            print("[Gemini] Modelo inicializado com:", n)
            return True
        except Exception as e:
            print("[Gemini] Falha com", name, "->", e)
            return False

    # Este método é chamado toda vez que o usuário envia uma nova mensagem.
    def gerar_resposta(self, pergunta: str) -> str:
        # Validação simples para não enviar mensagens vazias para a API
        if not pergunta.strip():
            return "Por favor, digite sua pergunta! Estou aqui para ajudar. 😄"

        # Verificar se chat_session existe, se não, reinicializar
        if not hasattr(self, 'chat_session') or self.chat_session is None:
            print("[Gemini] chat_session não existe, reinicializando...")
            if hasattr(self, 'model_name') and self.model_name:
                model_name_clean = self.model_name.replace("models/", "")
                if self._try_model(model_name_clean):
                    try:
                        self.chat_session.send_message(self.contexto_inicial)
                        print("[Gemini] Sessão reinicializada com sucesso")
                    except Exception as e:
                        print(f"[Gemini] Erro ao enviar contexto após reinicialização: {e}")
                        return "Humm… não consegui processar agora 😅\nPode tentar reformular sua pergunta sobre o Jovem Programador?"
                else:
                    return "Humm… não consegui processar agora 😅\nPode tentar reformular sua pergunta sobre o Jovem Programador?"
            else:
                return "Humm… não consegui processar agora 😅\nPode tentar reformular sua pergunta sobre o Jovem Programador?"

        try:
            composed = f"Usuário: {pergunta}"
            resp = self.chat_session.send_message(composed)
            text = getattr(resp, "text", None) or getattr(resp, "candidates", None)
            return text if isinstance(text, str) else (str(text) if text else "Humm… não consegui processar agora 😅\nPode tentar reformular sua pergunta sobre o Jovem Programador?")
        except Exception as e:
            print(f"[Gemini] erro:", e)
            # Tentar reinicializar a sessão automaticamente
            try:
                print("[Gemini] Tentando reinicializar sessão após erro...")
                if hasattr(self, 'model_name') and self.model_name:
                    model_name_clean = self.model_name.replace("models/", "")
                    if self._try_model(model_name_clean):
                        self.chat_session.send_message(self.contexto_inicial)
                        print("[Gemini] Sessão reinicializada, tentando novamente...")
                        # Tentar novamente
                        composed = f"Usuário: {pergunta}"
                        resp = self.chat_session.send_message(composed)
                        text = getattr(resp, "text", None) or getattr(resp, "candidates", None)
                        if text and isinstance(text, str):
                            return text
            except Exception as e2:
                print(f"[Gemini] Erro ao reinicializar sessão: {e2}")
            
            return "Humm… não consegui processar agora 😅\nPode tentar reformular sua pergunta sobre o Jovem Programador?"
