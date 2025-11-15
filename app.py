
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from utils.responder import Chatbot
import textwrap
import os
import time
import random
import re
from datetime import datetime
from services.firestore import (
    init_admin,
    get_or_create_conversation,
    save_message,
    get_conversation,
    update_conversation,
    save_lead_from_conversation,
)

# --- Classe de Cores (Foco em Alto Contraste) ---
class Cores:
    """Classe para organizar os códigos de cores ANSI para máxima legibilidade."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    USER = '\033[92m'      
    BOT_TEXT = '\033[96m'  
    BOT_HEADER = '\033[94m' 
    SYSTEM = '\033[93m'    
    TIMESTAMP = '\033[90m' 


app = Flask(__name__)
CORS(app)

# Inicializa Firestore (se habilitado)
init_admin()

# Flag para habilitar/desabilitar Firestore
AI_FIRESTORE_ENABLED = os.getenv("AI_FIRESTORE_ENABLED", "false").lower() == "true"
if AI_FIRESTORE_ENABLED:
    print("[Firestore] Persistência de conversas HABILITADA")
else:
    print("[Firestore] Persistência de conversas DESABILITADA (AI_FIRESTORE_ENABLED=false)")

try:
    chatbot_web = Chatbot()
except Exception as e:
    print(f"CRÍTICO: Não foi possível inicializar o chatbot para a web. Erro: {e}")
    chatbot_web = None

# Logs de modelos disponíveis e modelo selecionado
try:
    if chatbot_web:
        print("[Gemini] Modelos disponíveis para generateContent:")
        for m in getattr(chatbot_web, 'available_models', []):
            print(f" - {m}")
        print(f"[Gemini] Modelo em uso: {getattr(chatbot_web, 'model_name', 'desconhecido')}")
except Exception as e:
    print("[Gemini] Falha ao logar modelos disponíveis:", e)

# --- Helpers para o fluxo de captura de leads ---
LEAD_FIELDS_ORDER = ["nome", "cidade", "estado", "idade", "email", "interesse"]

# Mapeamento de estados brasileiros (nome completo -> sigla)
ESTADOS_BRASIL = {
    "AC": "AC", "AL": "AL", "AP": "AP", "AM": "AM", "BA": "BA", "CE": "CE",
    "DF": "DF", "ES": "ES", "GO": "GO", "MA": "MA", "MT": "MT", "MS": "MS",
    "MG": "MG", "PA": "PA", "PB": "PB", "PR": "PR", "PE": "PE", "PI": "PI",
    "RJ": "RJ", "RN": "RN", "RS": "RS", "RO": "RO", "RR": "RR", "SC": "SC",
    "SP": "SP", "SE": "SE", "TO": "TO",
    # Nomes completos
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARA": "CE", "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES",
    "GOIAS": "GO", "MARANHAO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR",
    "PERNAMBUCO": "PE", "PIAUI": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC",
    "SAO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO"
}


def get_next_lead_field(lead_data: dict) -> str | None:
    """
    Retorna o próximo campo que ainda não foi preenchido no lead_data.
    Ordem: nome -> cidade -> estado -> idade -> email -> interesse.
    """
    lead_data = lead_data or {}
    for field in LEAD_FIELDS_ORDER:
        value = lead_data.get(field)
        if value in (None, "", 0):
            return field
    return None


def get_question_for_field(field: str, lead_data: dict) -> str:
    """
    Retorna a pergunta correspondente a cada campo do lead.
    """
    if field == "nome":
        return "Pra começar, qual é o seu nome?"
    if field == "cidade":
        nome = lead_data.get("nome") or ""
        prefix = f"Prazer, {nome}! " if nome else ""
        return prefix + "De qual cidade você fala?"
    if field == "estado":
        return "E o estado? Pode enviar a sigla, tipo SC/SP/RJ."
    if field == "idade":
        return "Qual a sua idade?"
    if field == "email":
        return "Qual seu e-mail para eu te enviar materiais?"
    if field == "interesse":
        return "Para finalizar, qual é o seu principal interesse?"
    # fallback
    return "Pode me contar um pouco mais sobre o que você procura?"


def get_error_message_for_field(field: str) -> str:
    """
    Retorna mensagem de erro personalizada para cada campo quando validação falha.
    """
    if field == "email":
        return "Hum… não reconheci esse e-mail 😅\nPode enviar um válido? Exemplo: nome@dominio.com"
    if field == "estado":
        return "Consegue me passar a sigla do estado? (Ex.: SC, SP, RJ)"
    if field == "idade":
        return "Você pode me enviar sua idade em números? (Ex.: 25)"
    return "Por favor, tente novamente."


def normalize_uf(text: str) -> str | None:
    """
    Normaliza texto para sigla de UF brasileira.
    Aceita: "SC", "Santa Catarina", "sA ntA cAtArInA", "sou de sc", etc.
    Retorna sigla em maiúsculas ou None se não reconhecer.
    """
    if not text:
        return None
    
    text_original = text.strip()
    text = text_original.upper()
    
    # Remove acentos e caracteres especiais para comparação
    text_clean = text.replace("Ã", "A").replace("Ç", "C").replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    
    # Tenta encontrar sigla direta (2 letras)
    if len(text) == 2 and text in ESTADOS_BRASIL:
        return text
    
    # Procura sigla no texto (ex: "sou de SC" -> "SC")
    # Procura por padrão de 2 letras maiúsculas consecutivas
    sigla_match = re.search(r'\b([A-Z]{2})\b', text)
    if sigla_match:
        sigla = sigla_match.group(1)
        if sigla in ESTADOS_BRASIL:
            return sigla
    
    # Procura nome completo no texto (mais específico primeiro)
    # Ordena por tamanho decrescente para pegar nomes compostos primeiro
    estados_nomes = [(nome, sigla) for nome, sigla in ESTADOS_BRASIL.items() if len(nome) > 2]
    estados_nomes.sort(key=lambda x: len(x[0]), reverse=True)
    
    for nome, sigla in estados_nomes:
        nome_clean = nome.replace("Ã", "A").replace("Ç", "C").replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
        # Remove espaços para comparação mais flexível
        nome_clean_no_space = nome_clean.replace(" ", "")
        text_clean_no_space = text_clean.replace(" ", "")
        
        # Verifica se o nome está contido no texto
        if nome_clean in text_clean or nome_clean_no_space in text_clean_no_space:
            return sigla
    
    return None


def validate_email(email: str) -> bool:
    """
    Valida formato básico de email usando regex leve.
    """
    if not email or len(email) > 120:
        return False
    
    # Regex leve: deve ter @ e pelo menos um ponto após o @
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return bool(re.match(pattern, email.lower()))


def normalize_lead_answer(field: str, answer: str):
    """
    Normaliza e valida a resposta do usuário para cada campo.
    Retorna valor normalizado ou None se inválido.
    """
    if not answer:
        return None
    
    answer = answer.strip()
    
    # Nome, Cidade, Interesse: trim, limitar 120 chars, não vazio
    if field in ["nome", "cidade", "interesse"]:
        if not answer or len(answer) == 0:
            return None
        if len(answer) > 120:
            answer = answer[:120]
        return answer
    
    # Idade: extrair dígitos, converter para int, validar faixa 10-110
    if field == "idade":
        digits = "".join(ch for ch in answer if ch.isdigit())
        if not digits:
            return None
        try:
            idade = int(digits)
            if 10 <= idade <= 110:
                return idade
        except ValueError:
            pass
        return None
    
    # Estado (UF): normalizar para sigla
    if field == "estado":
        return normalize_uf(answer)
    
    # Email: validar formato, converter para lowercase, limitar 120 chars
    if field == "email":
        if len(answer) > 120:
            return None
        email_lower = answer.lower()
        if validate_email(email_lower):
            return email_lower
        return None
    
    return answer


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    if not chatbot_web:
        return jsonify({'response': "Desculpe, o chatbot está temporariamente fora de serviço."}), 500

    user_message = request.json.get('message', '')
    if not user_message:
        return jsonify({'response': "Por favor, digite sua mensagem!"}), 400

    session_id = request.json.get('session_id')
    if not session_id:
        epoch = int(time.time() * 1000)
        rand = random.randint(1000, 9999)
        session_id = f"sess_{epoch}_{rand}"

    # Se Firestore estiver desativado, mantém comportamento original
    if not AI_FIRESTORE_ENABLED:
        bot_response = chatbot_web.gerar_resposta(user_message)
        return jsonify({
            'response': bot_response,
            'session_id': session_id
        })

    # Firestore habilitado: fluxo com leads
    try:
        # Garante que a conversa existe
        get_or_create_conversation(session_id)

        # Lê estado atual da conversa
        conv_data = get_conversation(session_id) or {}
        lead_stage = conv_data.get("lead_stage")  # None, "collecting", "done"
        lead_done = conv_data.get("lead_done", False)
        lead_data = conv_data.get("lead_data") or {}

        # Sempre salva mensagem do usuário
        save_message(session_id, "user", user_message, meta={"source": "web"})
    except Exception as e:
        print(f"[Firestore] Erro inicial no fluxo de lead/conversa: {e}")
        lead_stage = None
        lead_done = False
        lead_data = {}

    # Detectar comandos especiais (processar antes de verificar lead_done)
    user_msg_lower = user_message.strip().lower()
    is_skip_command = user_msg_lower in ["pular", "pular cadastro", "skip", "pula"]
    is_delete_command = user_msg_lower in ["apagar dados", "apagar meu cadastro", "apagar", "deletar dados", "deletar"]

    # Comando: pular cadastro (funciona em qualquer estágio)
    if is_skip_command:
        try:
            update_conversation(session_id, {
                "lead_stage": "done",
                "lead_done": True,
                "lead_data": lead_data,  # Mantém dados parciais se houver
            })
            bot_response = "Sem problemas! Vamos seguir com sua pergunta normalmente. 🙂"
            save_message(session_id, "assistant", bot_response, meta={"source": "web", "type": "lead_skipped"})
        except Exception as e:
            print(f"[Firestore] Erro ao pular cadastro: {e}")
            bot_response = "Sem problemas! Vamos seguir com sua pergunta normalmente. 🙂"
        
        return jsonify({
            'response': bot_response,
            'session_id': session_id
        })

    # Comando: apagar dados (funciona em qualquer estágio)
    if is_delete_command:
        try:
            update_conversation(session_id, {
                "lead_stage": None,
                "lead_done": False,
                "lead_data": {},
            })
            bot_response = "Tudo certo! Seus dados foram apagados.\nSe quiser, posso coletar novamente depois. 🙂"
            save_message(session_id, "assistant", bot_response, meta={"source": "web", "type": "lead_deleted"})
        except Exception as e:
            print(f"[Firestore] Erro ao apagar dados: {e}")
            bot_response = "Tudo certo! Seus dados foram apagados.\nSe quiser, posso coletar novamente depois. 🙂"
        
        return jsonify({
            'response': bot_response,
            'session_id': session_id
        })

    # 1) Se já terminou o lead, fluxo normal com IA
    if lead_done or lead_stage == "done":
        bot_response = chatbot_web.gerar_resposta(user_message)
        if AI_FIRESTORE_ENABLED:
            try:
                save_message(session_id, "assistant", bot_response, meta={"source": "web"})
            except Exception as e:
                print(f"[Firestore] Erro ao salvar resposta do bot: {e}")
        return jsonify({
            'response': bot_response,
            'session_id': session_id
        })

    # 2) Se ainda não começou o fluxo de lead -> iniciar agora
    if lead_stage is None:
        lead_stage = "collecting"
        lead_data = {}

        first_field = get_next_lead_field(lead_data)  # deve ser "nome"
        question = get_question_for_field(first_field, lead_data)

        try:
            update_conversation(session_id, {
                "lead_stage": lead_stage,
                "lead_data": lead_data,
                "lead_done": False,
            })
            save_message(session_id, "assistant", question, meta={"source": "web", "type": "lead_question"})
        except Exception as e:
            print(f"[Firestore] Erro ao iniciar fluxo de lead: {e}")

        return jsonify({
            'response': question,
            'session_id': session_id
        })

    # 3) Estamos no meio do fluxo de lead ("collecting")
    if lead_stage == "collecting":
        # Descobre qual é o próximo campo a ser preenchido
        current_field = get_next_lead_field(lead_data)
        if current_field is None:
            # Estranho, mas considera lead completo
            current_field = "interesse"

        # Normaliza e valida a resposta do usuário
        normalized_value = normalize_lead_answer(current_field, user_message)

        # Se validação falhou (retornou None), pedir novamente com mensagem de erro
        if normalized_value is None:
            error_message = get_error_message_for_field(current_field)
            
            try:
                save_message(session_id, "assistant", error_message, meta={"source": "web", "type": "lead_error"})
            except Exception as e:
                print(f"[Firestore] Erro ao salvar mensagem de erro: {e}")

            return jsonify({
                'response': error_message,
                'session_id': session_id
            })

        # Validação passou: salva o valor normalizado
        lead_data[current_field] = normalized_value

        # Verifica se o lead está completo
        next_field = get_next_lead_field(lead_data)

        if next_field is None:
            # Lead completo -> salvar em "leads" e marcar como done
            # Garantir tipos corretos antes de salvar
            lead_data_final = {
                "nome": str(lead_data.get("nome", "")).strip()[:120],
                "cidade": str(lead_data.get("cidade", "")).strip()[:120],
                "estado": str(lead_data.get("estado", "")).strip().upper()[:2],
                "idade": int(lead_data.get("idade", 0)) if lead_data.get("idade") else None,
                "email": str(lead_data.get("email", "")).strip().lower()[:120],
                "interesse": str(lead_data.get("interesse", "")).strip()[:120],
            }
            
            # Remove campos vazios/None
            lead_data_final = {k: v for k, v in lead_data_final.items() if v not in (None, "", 0)}
            
            try:
                save_lead_from_conversation(session_id, lead_data_final)
                update_conversation(session_id, {
                    "lead_stage": "done",
                    "lead_done": True,
                    "lead_data": lead_data_final,
                })
            except Exception as e:
                print(f"[Firestore] Erro ao salvar lead: {e}")

            bot_response = (
                "Perfeito, já anotei seus dados aqui! 🎉\n"
                "Agora posso te ajudar com dúvidas sobre o programa e próximos passos."
            )

            if AI_FIRESTORE_ENABLED:
                try:
                    save_message(session_id, "assistant", bot_response, meta={"source": "web", "type": "lead_done"})
                except Exception as e:
                    print(f"[Firestore] Erro ao salvar mensagem de conclusão de lead: {e}")

            return jsonify({
                'response': bot_response,
                'session_id': session_id
            })

        # Ainda faltam campos -> pergunta próxima informação
        next_question = get_question_for_field(next_field, lead_data)

        try:
            update_conversation(session_id, {
                "lead_stage": "collecting",
                "lead_data": lead_data,
                "lead_done": False,
            })
            save_message(session_id, "assistant", next_question, meta={"source": "web", "type": "lead_question"})
        except Exception as e:
            print(f"[Firestore] Erro ao avançar no fluxo de lead: {e}")

        return jsonify({
            'response': next_question,
            'session_id': session_id
        })

    # 4) Fallback: se lead_stage tiver um valor desconhecido, segue fluxo normal com IA
    bot_response = chatbot_web.gerar_resposta(user_message)
    if AI_FIRESTORE_ENABLED:
        try:
            save_message(session_id, "assistant", bot_response, meta={"source": "web"})
        except Exception as e:
            print(f"[Firestore] Erro ao salvar resposta do bot (fallback): {e}")

    return jsonify({
        'response': bot_response,
        'session_id': session_id
    })

@app.route('/health')
def health():
    status = {
        'status': 'ok' if chatbot_web else 'unavailable',
        'model': getattr(chatbot_web, 'model_name', None),
        'available_models': getattr(chatbot_web, 'available_models', []),
    }
    return jsonify(status)


# --- Função para Teste no Terminal (VERSÃO APRESENTAÇÃO) ---
def main_terminal():
    """Função com visual elegante para apresentação no terminal."""
    try:
        chatbot_terminal = Chatbot()
    except Exception as e:
        print(f"CRÍTICO: Falha ao iniciar o chatbot para o terminal. Erro: {e}")
        return

    print(f"\n{Cores.SYSTEM}✅ Chatbot 'Leozin' pronto. Inicie a conversa ou digite '/sair'.{Cores.RESET}")

    while True:
        try:
            # --- TURNO DO USUÁRIO ---
            timestamp_user = datetime.now().strftime('%H:%M:%S')
            print(f"\n{Cores.TIMESTAMP}[{timestamp_user}]{Cores.RESET} {Cores.USER}{Cores.BOLD}Você diz:{Cores.RESET}")
            user_message = input("└──> ") # Usando caracteres de caixa para o prompt

            # Lógica para sair
            if user_message.lower() in ['/sair', 'exit', 'quit']:
                print(f"{Cores.SYSTEM}Encerrando sessão. Até logo!{Cores.RESET}")
                break
            
            if not user_message:
                continue

            # --- TURNO DO BOT ---
            bot_response = chatbot_terminal.gerar_resposta(user_message)
            
            # Cabeçalho da resposta do bot
            timestamp_bot = datetime.now().strftime('%H:%M:%S')
            print(f"{Cores.TIMESTAMP}[{timestamp_bot}]{Cores.RESET} {Cores.BOT_HEADER}{Cores.BOLD}Leozin responde:{Cores.RESET}")
            
            # Linha superior da "caixa"
            print(f"{Cores.BOT_TEXT}┌{'─' * 78}{Cores.RESET}")
            
            # Quebra o texto e imprime cada linha dentro da "caixa"
            wrapped_lines = textwrap.wrap(bot_response, width=76)
            for line in wrapped_lines:
                print(f"{Cores.BOT_TEXT}│ {line.ljust(76)} │{Cores.RESET}")
            
            # Linha inferior da "caixa"
            print(f"{Cores.BOT_TEXT}└{'─' * 78}{Cores.RESET}")

        except KeyboardInterrupt:
            print(f"\n{Cores.SYSTEM}Encerrando sessão. Até logo!{Cores.RESET}")
            break
        except Exception as e:
            print(f"🤖 Ocorreu um erro inesperado: {e}")

# --- Registro do Blueprint Admin ---
from admin import admin_bp
app.register_blueprint(admin_bp)

# --- Ponto de Entrada do Script ---
if __name__ == '__main__':
    # Para rodar o chatbot no terminal, descomente a linha abaixo:
    # main_terminal()

    # Para rodar o servidor web, descomente a linha abaixo:
    app.run(debug=True, port=5000, host='0.0.0.0')
    
