
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from utils.responder import Chatbot
import textwrap
import os
import time
import random
from datetime import datetime
from services.firestore import init_admin, get_or_create_conversation, save_message

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    if not chatbot_web:
        return jsonify({'response': "Desculpe, o chatbot está temporariamente fora de serviço."}), 500
    
    # Extrai mensagem do usuário (retrocompatível)
    user_message = request.json.get('message', '')
    if not user_message:
        return jsonify({'response': "Por favor, digite sua mensagem!"}), 400
    
    # Gera ou recupera session_id (retrocompatível)
    session_id = request.json.get('session_id')
    if not session_id:
        # Fallback: gera session_id no formato "sess_" + epoch + rand
        epoch = int(time.time() * 1000)
        rand = random.randint(1000, 9999)
        session_id = f"sess_{epoch}_{rand}"
    
    # Salva mensagem do usuário no Firestore (se habilitado)
    if AI_FIRESTORE_ENABLED:
        try:
            get_or_create_conversation(session_id)
            save_message(session_id, "user", user_message, meta={"source": "web"})
            print(f"[Firestore] Mensagem do usuário salva: session_id={session_id}")
        except Exception as e:
            # Erro não deve interromper o fluxo do chat
            print(f"[Firestore] Erro ao salvar mensagem do usuário: {e}")
    
    # Chama IA (comportamento original mantido)
    bot_response = chatbot_web.gerar_resposta(user_message)
    
    # Salva resposta do bot no Firestore (se habilitado)
    if AI_FIRESTORE_ENABLED:
        try:
            save_message(session_id, "assistant", bot_response, meta={"source": "web"})
            print(f"[Firestore] Resposta do bot salva: session_id={session_id}")
        except Exception as e:
            # Erro não deve interromper o fluxo do chat
            print(f"[Firestore] Erro ao salvar resposta do bot: {e}")
    
    # Resposta HTTP (retrocompatível: adiciona session_id mas mantém 'response')
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
    
