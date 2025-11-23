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
            # Formata de forma simples e direta, uma rede por linha com nome e URL completa
            lista_redes = [f"{nome}: {url}" for nome, url in redes_info.items()]
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
        
        CRÍTICO - Formatação de Links e Redes Sociais:
        - Quando o usuário perguntar sobre redes sociais, você DEVE incluir as URLs completas na resposta
        - Formato OBRIGATÓRIO: "Nome da Rede: URL completa" (exemplo: "Facebook: https://www.facebook.com/programajovemprogramador")
        - NUNCA liste apenas os nomes das redes sem as URLs
        - NUNCA use ícones, símbolos especiais (□, ■, etc) ou formatação visual complexa
        - NUNCA duplique informações (não repita o nome da rede após o link)
        - Exemplo de resposta CORRETA sobre redes sociais:
          "Aqui estão os nossos canais oficiais:
          Facebook: https://www.facebook.com/programajovemprogramador
          Instagram: https://www.instagram.com/programa_jovemprogramador
          LinkedIn: https://www.linkedin.com/company/programajovemprogramador
          TikTok: https://www.tiktok.com/@jovemprogramador_sc"
        - Exemplo de resposta INCORRETA (NÃO FAÇA ISSO):
          "Facebook: 
          Instagram: 
          LinkedIn: 
          TikTok:"
        - SEMPRE copie as URLs exatamente como aparecem na seção REDES SOCIAIS abaixo
        - IMPORTANTE: Se você listar "Facebook:", "Instagram:", etc, você DEVE incluir a URL completa logo após os dois pontos
        - NÃO deixe linhas vazias após os nomes das redes. SEMPRE coloque a URL na mesma linha ou logo abaixo

        REGRA ABSOLUTA - Formatação de Links e CTAs:
        - SEMPRE coloque o link NA MESMA LINHA ou IMEDIATAMENTE APÓS o emoji/texto de chamada
        - Formato OBRIGATÓRIO para links de inscrição/edital:
          "Para garantir sua vaga, acesse: https://www.jovemprogramador.com.br/inscricoes-jovem-programador/#inscrevase"
          OU
          "👉 https://www.jovemprogramador.com.br/inscricoes-jovem-programador/#inscrevase"
        - NUNCA faça:
          "👉 \n\nhttps://..." (link em linha separada com linhas vazias)
          "👉 \n\n\nAqui está! \n\nhttps://..." (link no final separado)
        - O link DEVE estar conectado ao texto de chamada, sem linhas vazias entre eles
        - NUNCA coloque o link no final da mensagem separado do contexto
        - NUNCA adicione linhas extras antes ou depois do link
        - NUNCA reorganize parágrafos após mencionar o link
        - Se você usar "👉", o link DEVE estar na mesma linha ou na linha imediata seguinte (sem linhas vazias)

        TEMPLATE FIXO para respostas com link de inscrição:
        "[Acolhimento] 🚀

        [Benefício/Desejo] 🎓

        [Informação sobre datas/prazos, se houver]

        Para garantir sua vaga, acesse: [URL COMPLETA AQUI]

        [Finalização amigável]"

        TEMPLATE FIXO para respostas com link de edital:
        "[Acolhimento] 🚀

        [Benefício/Desejo] 🎓

        Para ver o edital completo, acesse: [URL COMPLETA AQUI]

        [Finalização amigável]"

        VERIFICAÇÃO OBRIGATÓRIA antes de enviar resposta:
        - Se você mencionou "acesse:", "link:", "👉", ou similar, VERIFIQUE se o link está na mesma linha ou linha imediata seguinte
        - Se o link estiver separado por mais de 1 linha vazia, CORRIJA movendo o link para logo após o texto de chamada
        - NUNCA envie resposta com emoji de chamada sem o link logo após
        - Se você colocou "👉" em uma linha, o link DEVE estar na mesma linha ou na próxima linha (sem linhas vazias)

        Política de resposta (AIDA):
        1) Acolhimento: reconheça a iniciativa do usuário de estudar ou evoluir na carreira (ex.: "Ótima iniciativa querer estudar!" 💡).
        2) Benefício/Desejo: destaque benefícios reais do programa (ex.: "O curso é gratuito e conecta você com empresas parceiras." 🎓).
        3) Chamada para Ação (CTA com link): entregue o link com uma chamada clara, nunca de forma seca (ex.: "Para garantir sua vaga ou ver o edital, acesse: [link]" 👉).

        --- DIRETRIZ DE FINALIZAÇÃO ---
        Ao entregar um link, seja educado e prestativo.
        Se você souber o nome da pessoa, use-o (ex.: "Aqui está, Lucas!").
        Se não souber, convide-a para continuar o papo (ex.: "Aqui está! Qualquer dúvida, estou por aqui.").
        NÃO force perguntas repetitivas se o papo já estiver fluindo.

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

        REDES SOCIAIS (COPIE AS URLs EXATAMENTE COMO ESTÃO AQUI - NÃO OMITA AS URLs):
        {redes_texto}
        
        REGRA ABSOLUTA: Ao responder sobre redes sociais, você DEVE copiar EXATAMENTE o formato acima, incluindo TODAS as URLs completas. 
        NÃO liste apenas "Facebook:", "Instagram:" sem as URLs. SEMPRE inclua: "Facebook: https://...", "Instagram: https://...", etc.

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

    def _fix_social_media_links(self, resposta: str) -> str:
        """
        Corrige respostas sobre redes sociais que não incluem URLs.
        Se a resposta menciona redes sociais mas não tem URLs, adiciona automaticamente.
        """
        if not resposta or not isinstance(resposta, str):
            return resposta
        
        # Verifica se a resposta menciona redes sociais mas não tem URLs completas
        redes_mentions = ["Facebook:", "Instagram:", "LinkedIn:", "TikTok:"]
        tem_mencoes = any(mention in resposta for mention in redes_mentions)
        tem_urls = "https://www.facebook.com" in resposta or "https://www.instagram.com" in resposta or "https://www.linkedin.com" in resposta or "https://www.tiktok.com" in resposta
        
        # Se menciona redes mas não tem URLs, adiciona
        if tem_mencoes and not tem_urls:
            redes_info = self.dados.get("redes_sociais", {})
            if redes_info:
                # Procura por linhas que mencionam redes sociais sem URLs
                linhas = resposta.split('\n')
                novas_linhas = []
                for linha in linhas:
                    linha_original = linha
                    # Verifica se a linha menciona uma rede social mas não tem URL
                    for nome_rede, url in redes_info.items():
                        if f"{nome_rede}:" in linha and url not in linha:
                            # Substitui a linha pela versão com URL
                            linha = f"{nome_rede}: {url}"
                            break
                    novas_linhas.append(linha)
                return '\n'.join(novas_linhas)
        
        return resposta

    def _fix_link_formatting(self, resposta: str) -> str:
        """
        Corrige formatação de links que foram separados incorretamente.
        Move links que estão no final ou muito separados para o lugar correto.
        """
        if not resposta or not isinstance(resposta, str):
            return resposta
        
        import re
        
        # Regex para encontrar URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, resposta)
        
        if not urls:
            return resposta
        
        linhas = resposta.split('\n')
        resultado_linhas = []
        urls_processadas = set()
        
        i = 0
        while i < len(linhas):
            linha = linhas[i]
            
            # Verifica se a linha tem padrão de chamada
            tem_chamada = (
                '👉' in linha or
                re.search(r'acesse:\s*$', linha, re.IGNORECASE) or
                re.search(r'link:\s*$', linha, re.IGNORECASE) or
                re.search(r'acesse\s+o\s+link:\s*$', linha, re.IGNORECASE)
            )
            
            # Verifica se linha já tem URL
            url_na_linha = re.search(url_pattern, linha)
            
            if tem_chamada:
                if url_na_linha:
                    # Já está correto - tem chamada e URL na mesma linha
                    resultado_linhas.append(linha)
                else:
                    # Tem chamada mas não tem URL - procura URL próxima
                    url_encontrada = None
                    indice_url = None
                    
                    # Procura nas próximas 3 linhas
                    for j in range(i + 1, min(i + 4, len(linhas))):
                        url_match = re.search(url_pattern, linhas[j])
                        if url_match:
                            url_candidata = url_match.group(0)
                            if url_candidata not in urls_processadas:
                                url_encontrada = url_candidata
                                indice_url = j
                                break
                    
                    if url_encontrada:
                        # Adiciona URL na mesma linha da chamada
                        resultado_linhas.append(linha.rstrip() + ' ' + url_encontrada)
                        urls_processadas.add(url_encontrada)
                        # Pula até a linha que tinha a URL (mas mantém outras linhas entre)
                        for k in range(i + 1, indice_url):
                            if linhas[k].strip() and not re.search(url_pattern, linhas[k]):
                                resultado_linhas.append(linhas[k])
                        i = indice_url + 1
                        continue
                    else:
                        # Não encontrou URL próxima, mantém linha original
                        resultado_linhas.append(linha)
            elif url_na_linha:
                # Linha tem URL mas não tem chamada - verifica se deveria estar junto com chamada anterior
                url_atual = url_na_linha.group(0)
                
                # Verifica se há chamada nas últimas 3 linhas do resultado
                tem_chamada_antes = False
                for j in range(max(0, len(resultado_linhas) - 3), len(resultado_linhas)):
                    linha_antes = resultado_linhas[j]
                    if (
                        '👉' in linha_antes or
                        re.search(r'acesse:\s*$', linha_antes, re.IGNORECASE) or
                        re.search(r'link:\s*$', linha_antes, re.IGNORECASE)
                    ):
                        # Verifica se já tem URL após essa chamada
                        if j + 1 >= len(resultado_linhas) or not re.search(url_pattern, resultado_linhas[j]):
                            # Move URL para após a chamada
                            resultado_linhas[j] = resultado_linhas[j].rstrip() + ' ' + url_atual
                            urls_processadas.add(url_atual)
                            # Remove URL da linha atual, mantém resto do texto
                            linha_sem_url = linha.replace(url_atual, '').strip()
                            if linha_sem_url:
                                resultado_linhas.append(linha_sem_url)
                            i += 1
                            continue
                        tem_chamada_antes = True
                        break
                
                if not tem_chamada_antes and url_atual not in urls_processadas:
                    resultado_linhas.append(linha)
                    urls_processadas.add(url_atual)
            else:
                # Linha normal sem chamada nem URL
                resultado_linhas.append(linha)
            
            i += 1
        
        resultado = '\n'.join(resultado_linhas)
        
        # Limpa linhas vazias excessivas (mais de 2 consecutivas)
        resultado = re.sub(r'\n{3,}', '\n\n', resultado)
        
        return resultado

    def _validate_response_formatting(self, resposta: str) -> str:
        """
        Valida e corrige formatação da resposta antes de retornar.
        Garante que links estejam no lugar correto.
        """
        if not resposta or not isinstance(resposta, str):
            return resposta
        
        import re
        
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        tem_urls = bool(re.search(url_pattern, resposta))
        
        if not tem_urls:
            return resposta
        
        # Verifica se há 👉 sem URL próximo
        if '👉' in resposta:
            linhas = resposta.split('\n')
            for i, linha in enumerate(linhas):
                if '👉' in linha:
                    # Verifica se tem URL nas próximas 2 linhas
                    proximas_linhas = '\n'.join(linhas[i:min(i+3, len(linhas))])
                    if not re.search(url_pattern, proximas_linhas):
                        # Procura primeira URL na resposta
                        todas_urls = re.findall(url_pattern, resposta)
                        if todas_urls:
                            primeira_url = todas_urls[0]
                            # Remove URL do lugar original
                            resposta = resposta.replace(primeira_url, '', 1)
                            # Adiciona após 👉 na mesma linha
                            resposta = resposta.replace(linha, linha.rstrip() + ' ' + primeira_url, 1)
                    break
        
        # Verifica se há "acesse:" sem URL próximo
        if re.search(r'acesse:\s*$', resposta, re.MULTILINE | re.IGNORECASE):
            linhas = resposta.split('\n')
            for i, linha in enumerate(linhas):
                if re.search(r'acesse:\s*$', linha, re.IGNORECASE):
                    # Verifica se próxima linha tem URL
                    if i + 1 < len(linhas):
                        proxima = linhas[i + 1].strip()
                        if not re.search(url_pattern, proxima):
                            # Procura primeira URL
                            todas_urls = re.findall(url_pattern, resposta)
                            if todas_urls:
                                primeira_url = todas_urls[0]
                                # Remove do lugar original
                                resposta = resposta.replace(primeira_url, '', 1)
                                # Adiciona após "acesse:"
                                resposta = resposta.replace(linha, linha.rstrip() + ' ' + primeira_url, 1)
                    break
        
        return resposta

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
            resposta_final = text if isinstance(text, str) else (str(text) if text else "Humm… não consegui processar agora 😅\nPode tentar reformular sua pergunta sobre o Jovem Programador?")
            # Aplica correções de formatação (ordem importa)
            resposta_final = self._fix_social_media_links(resposta_final)
            resposta_final = self._fix_link_formatting(resposta_final)
            resposta_final = self._validate_response_formatting(resposta_final)
            return resposta_final
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
                            resposta_final = text
                            # Aplica correções de formatação (ordem importa)
                            resposta_final = self._fix_social_media_links(resposta_final)
                            resposta_final = self._fix_link_formatting(resposta_final)
                            resposta_final = self._validate_response_formatting(resposta_final)
                            return resposta_final
            except Exception as e2:
                print(f"[Gemini] Erro ao reinicializar sessão: {e2}")
            
            return "Humm… não consegui processar agora 😅\nPode tentar reformular sua pergunta sobre o Jovem Programador?"
