
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from utils.responder import Chatbot
import textwrap
from datetime import datetime
import os
import logging

logging.basicConfig(
    level=logging.DEBUG if os.getenv("APP_DEBUG") == "1" else logging.INFO,
    format="[%(levelname)s] %(message)s"
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
try:
    chatbot_web = Chatbot()
except Exception as e:
    print(f"CRÍTICO: Não foi possível inicializar o chatbot para a web. Erro: {e}")
    chatbot_web = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    if not chatbot_web:
        return jsonify({'response': "Desculpe, o chatbot está temporariamente fora de serviço."}), 500
    user_message = request.json.get('message', '')
    bot_response = chatbot_web.gerar_resposta(user_message)
    return jsonify({'response': bot_response})


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

# --- Ponto de Entrada do Script ---
if __name__ == '__main__':
    # Executa terminal se APP_TTY=1, caso contrário, inicia servidor web para a demo
    import os
    use_tty = os.getenv('APP_TTY') == '1'
    if use_tty:
        main_terminal()
    else:
        app.run(debug=True, port=5000)
    