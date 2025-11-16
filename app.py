
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
    init_default_admin,
    get_or_create_conversation,
    save_message,
    get_conversation,
    update_conversation,
    save_lead_from_conversation,
    get_settings,
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
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)

# Inicializa Firestore (se habilitado)
print("[DEBUG] Iniciando Firestore...")
init_admin()
# Inicializa admin padrão após Firestore estar pronto
print("[DEBUG] Chamando init_default_admin()...")
init_default_admin()
print("[DEBUG] Inicialização do Firestore concluída.")

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
# Ordem dos campos do lead (sem e-mail)
LEAD_FIELDS_ORDER = ["nome", "interesse", "cidade", "estado", "idade"]

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
    Ordem: nome -> interesse -> cidade -> estado -> idade.
    """
    lead_data = lead_data or {}
    for field in LEAD_FIELDS_ORDER:
        value = lead_data.get(field)
        if value in (None, "", 0):
            return field
    return None


def get_question_for_field(field: str, lead_data: dict | None = None) -> str:
    """
    Retorna a pergunta amigável para cada etapa do lead.
    """
    lead_data = lead_data or {}
    nome = lead_data.get("nome")

    if field == "nome":
        return (
            "Oi! 😄 Que bom ter você aqui!\n"
            "Eu sou o assistente oficial do Programa Jovem Programador.\n"
            "Antes de te explicar tudo, como posso te chamar?"
        )

    if field == "interesse":
        prefix = f"Legal, {nome}! " if nome else "Legal! "
        return (
            prefix
            + "Me conta, o que mais te chama atenção no Programa Jovem Programador?\n"
              "Cursos, aulas, empregabilidade, tecnologia… ou outra coisa?"
        )

    if field == "cidade":
        return "Show! De qual cidade você está falando?"

    if field == "estado":
        return "Boa! E qual é o estado? Pode mandar só a sigla, tipo SC/SP/RJ 🙂"

    if field == "idade":
        return "Perfeito! Pra eu te orientar certinho, quantos anos você tem?"

    # fallback
    return "Pode me contar um pouco mais sobre você? 🙂"


def get_error_message_for_field(field: str) -> str:
    """
    Mensagens de erro quando a validação falha.
    (E-mail saiu do fluxo, então só estado/idade precisam de erro específico)
    """
    if field == "estado":
        return "Consegue me passar a sigla do estado? (Ex.: SC, SP, RJ)"
    if field == "idade":
        return "Você pode me enviar sua idade em números? (Ex.: 16, 18, 25)"
    return "Não entendi muito bem, pode tentar de outro jeito? 🙂"


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


def normalize_city_name(city: str) -> str | None:
    """
    Normaliza o nome da cidade removendo prefixos comuns, estados e formatando para Title Case.
    Exemplos:
    - "eu falo de palhoça, sc" -> "Palhoça"
    - "sou de florianópolis" -> "Florianópolis"
    - "moro em palhoça - sc" -> "Palhoça"
    Retorna None se a cidade não puder ser normalizada (vazia ou muito curta).
    """
    if not city:
        return None
    
    # Converte para lowercase
    city = city.lower().strip()
    
    if not city:
        return None
    
    # Remove prefixos comuns no início da frase (case-insensitive)
    prefixes = [
        "eu sou de",
        "eu moro em",
        "eu falo de",
        "sou de",
        "moro em",
        "falo de",
        "sou",
        "moro",
        "falo"
    ]
    
    for prefix in prefixes:
        if city.startswith(prefix):
            city = city[len(prefix):].strip()
            break
    
    # Corta tudo após vírgula ou hífen (geralmente estado)
    if "," in city:
        city = city.split(",")[0].strip()
    if "-" in city:
        city = city.split("-")[0].strip()
    
    # Remove palavras genéricas no começo
    generic_words = ["cidade de", "município de", "cidade", "município"]
    for word in generic_words:
        if city.startswith(word):
            city = city[len(word):].strip()
            break
    
    # Remove espaços extras e faz strip final
    city = " ".join(city.split())
    city = city.strip()
    
    # Validação: se ficou com menos de 2 caracteres, retorna None
    if len(city) < 2:
        return None
    
    # Limita a 50 caracteres
    if len(city) > 50:
        city = city[:50]
    
    # Converte para Title Case (primeira letra de cada palavra em maiúscula)
    city = " ".join(word.capitalize() for word in city.split() if word)
    
    return city if city else None


def validate_email(email: str) -> bool:
    """
    Valida formato básico de email usando regex permissivo.
    """
    if not email or len(email) > 120:
        return False
    
    # Regex permissivo: deve ter @ e pelo menos um ponto
    pattern = r'.+@.+\..+'
    return bool(re.match(pattern, email.lower()))


def normalize_lead_answer(field: str, answer: str):
    """
    Normaliza/valida a resposta de cada campo do lead.
    Retorna o valor normalizado ou None se inválido.
    """
    if answer is None:
        return None

    answer = str(answer).strip()
    if not answer:
        return None

    # Nome: só limita tamanho
    if field == "nome":
        return answer[:120]

    # Interesse: texto livre, só limita tamanho
    if field == "interesse":
        return answer[:200]

    # Cidade: usa normalização esperta, com fallback pro texto cru
    if field == "cidade":
        normalized = normalize_city_name(answer)
        return normalized or answer[:120]

    # Estado (UF): normaliza usando a helper de UF
    if field == "estado":
        uf = normalize_uf(answer)
        return uf  # pode ser None se inválido

    # Idade: extrai dígitos e valida faixa
    if field == "idade":
        digits = re.sub(r"[^\d]", "", answer)
        if not digits:
            return None
        idade = int(digits)
        if idade < 10 or idade > 110:
            return None
        return idade

    # Fallback genérico
    return answer[:255]


@app.route('/')
def index():
    return render_template('index.html')

# Defaults para botões rápidos
DEFAULT_QUICK_ACTIONS = [
    {"label": "💻 Como começar?",      "message": "Quero saber como começar na programação."},
    {"label": "🎯 Dicas de carreira",  "message": "Quais são as dicas de carreira em tecnologia?"},
    {"label": "🔧 Ferramentas úteis",  "message": "Quais ferramentas são úteis para programação?"},
    {"label": "📚 Recursos de estudo", "message": "Quais são os melhores recursos de estudo?"}
]

@app.route('/api/chat-config', methods=['GET'])
def api_chat_config():
    """Endpoint público para configs do chat widget."""
    chat_cfg = get_settings("chat_config") or {}
    
    # Processar quick_actions com defaults
    quick_actions = chat_cfg.get("quick_actions")
    if not isinstance(quick_actions, list) or len(quick_actions) == 0:
        quick_actions = DEFAULT_QUICK_ACTIONS
    
    quick_actions_enabled = chat_cfg.get("quick_actions_enabled")
    if quick_actions_enabled is None:
        quick_actions_enabled = True  # ligado por padrão quando estamos usando os defaults
    
    # Defaults seguros
    data = {
        "chat_title": chat_cfg.get("chat_title", "ChatLeo"),
        "welcome_message": chat_cfg.get(
            "welcome_message",
            "Olá! 👋 Sou o assistente do Jovem Programador. Como posso te ajudar hoje? 🚀",
        ),
        "bot_avatar": chat_cfg.get("bot_avatar", "/static/assets/logo.png"),
        "user_avatar": chat_cfg.get("user_avatar", "/static/assets/logo-user.png"),
        "primary_color": chat_cfg.get("primary_color", "#3D7EFF"),
        "secondary_color": chat_cfg.get("secondary_color", "#8B5CF6"),
        "quick_actions_enabled": quick_actions_enabled,
        "quick_actions": quick_actions,
        # Novos campos de papel de parede
        "chat_background_enabled": chat_cfg.get("chat_background_enabled", True),
        "chat_background_type": chat_cfg.get("chat_background_type", "default"),
        "chat_background_color": chat_cfg.get("chat_background_color", ""),
        "chat_background_image_url": chat_cfg.get("chat_background_image_url", ""),
    }
    return jsonify(data)

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

    # ---------------------------------------------------------
    # 2) Comandos especiais (apagar cadastro, etc) - opcional manter seu código atual
    # ---------------------------------------------------------
    # Comando: apagar dados (funciona em qualquer estágio)
    user_msg_lower = user_message.strip().lower()
    is_delete_command = user_msg_lower in ["apagar dados", "apagar meu cadastro", "apagar", "deletar dados", "deletar"]
    
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

    # ---------------------------------------------------------
    # 3) Se lead já foi concluído, segue fluxo normal com IA
    # ---------------------------------------------------------
    if lead_done or lead_stage == "done":
        bot_response = chatbot_web.gerar_resposta(user_message)

        if AI_FIRESTORE_ENABLED:
            try:
                save_message(session_id, "assistant", bot_response, meta={"source": "web"})
            except Exception as e:
                print(f"[Firestore] Erro ao salvar resposta do bot: {e}")

        return jsonify({
            "response": bot_response,
            "session_id": session_id,
        })

    # ---------------------------------------------------------
    # 4) Fluxo de LEAD (sem e-mail, com 'pular' em qualquer etapa)
    # ---------------------------------------------------------
    # Se ainda não começou, inicia coleta
    if not lead_stage:
        lead_stage = "collecting"
        lead_data = lead_data or {}
        try:
            update_conversation(session_id, {
                "lead_stage": lead_stage,
                "lead_data": lead_data,
                "lead_done": False,
            })
        except Exception as e:
            print(f"[Firestore] Erro ao iniciar lead: {e}")

        # Primeira pergunta: nome
        first_field = get_next_lead_field(lead_data)
        question = get_question_for_field(first_field, lead_data)

        if AI_FIRESTORE_ENABLED:
            try:
                save_message(session_id, "assistant", question, meta={"source": "web", "type": "lead_question"})
            except Exception as e:
                print(f"[Firestore] Erro ao salvar pergunta de lead: {e}")

        return jsonify({
            "response": question,
            "session_id": session_id,
        })

    # Já está em coleta: descobre campo atual
    current_field = get_next_lead_field(lead_data)

    # Se por algum motivo não tem campo pendente, marca como done e cai no fluxo normal na próxima mensagem
    if current_field is None:
        try:
            update_conversation(session_id, {
                "lead_stage": "done",
                "lead_done": True,
                "lead_data": lead_data,
            })
        except Exception as e:
            print(f"[Firestore] Erro ao finalizar lead sem campos: {e}")

        final_msg = (
            "Tudo certo! Obrigado por compartilhar suas informações 😊\n"
            "Agora posso te ajudar com qualquer dúvida sobre o Programa Jovem Programador!\n"
            "O que você gostaria de saber?"
        )

        if AI_FIRESTORE_ENABLED:
            try:
                save_message(session_id, "assistant", final_msg, meta={"source": "web", "type": "lead_done"})
            except Exception as e:
                print(f"[Firestore] Erro ao salvar mensagem final de lead: {e}")

        return jsonify({
            "response": final_msg,
            "session_id": session_id,
        })

    # Comandos para pular etapa
    msg_lower = user_message.strip().lower()
    skip_commands = {
        "pular",
        "pula",
        "pular etapa",
        "pular essa etapa",
        "pode pular",
        "pode pular essa etapa",
        "não quero responder",
        "prefiro não informar",
    }

    if msg_lower in skip_commands:
        # Só marca o campo atual como None e segue
        lead_data[current_field] = None
    else:
        # Normaliza/valida resposta
        normalized_value = normalize_lead_answer(current_field, user_message)

        # Se falhou validação, pede de novo com mensagem amigável
        if normalized_value is None:
            error_message = get_error_message_for_field(current_field)

            if AI_FIRESTORE_ENABLED:
                try:
                    save_message(session_id, "assistant", error_message, meta={"source": "web", "type": "lead_error"})
                except Exception as e:
                    print(f"[Firestore] Erro ao salvar mensagem de erro do lead: {e}")

            return jsonify({
                "response": error_message,
                "session_id": session_id,
            })

        lead_data[current_field] = normalized_value

    # Verifica se ainda há campos pendentes
    next_field = get_next_lead_field(lead_data)

    # Se terminou todos os campos -> salva lead e finaliza
    if next_field is None:
        if AI_FIRESTORE_ENABLED:
            try:
                save_lead_from_conversation(session_id, lead_data)
                update_conversation(session_id, {
                    "lead_stage": "done",
                    "lead_done": True,
                    "lead_data": lead_data,
                })
            except Exception as e:
                print(f"[Firestore] Erro ao salvar lead: {e}")

        final_msg = (
            "Fechado! Obrigado por compartilhar suas informações 😊\n"
            "Agora eu consigo te ajudar MUITO melhor sobre o Programa Jovem Programador.\n"
            "O que você quer saber primeiro?"
        )

        if AI_FIRESTORE_ENABLED:
            try:
                save_message(session_id, "assistant", final_msg, meta={"source": "web", "type": "lead_done"})
            except Exception as e:
                print(f"[Firestore] Erro ao salvar mensagem final de lead: {e}")

        return jsonify({
            "response": final_msg,
            "session_id": session_id,
        })

    # Ainda falta coletar algum campo → pergunta seguinte
    try:
        update_conversation(session_id, {
            "lead_stage": "collecting",
            "lead_data": lead_data,
            "lead_done": False,
        })
    except Exception as e:
        print(f"[Firestore] Erro ao atualizar lead em coleta: {e}")

    next_question = get_question_for_field(next_field, lead_data)

    if AI_FIRESTORE_ENABLED:
        try:
            save_message(session_id, "assistant", next_question, meta={"source": "web", "type": "lead_question"})
        except Exception as e:
            print(f"[Firestore] Erro ao salvar próxima pergunta de lead: {e}")

    return jsonify({
        "response": next_question,
        "session_id": session_id,
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
    
