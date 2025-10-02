from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Dados simulados para teste da interface
dados_simulados = {
    "sobre": "O JOVEM PROGRAMADOR é um PROGRAMA de capacitação tecnológica para formação de pessoas, a partir de 16 anos, em situação de vulnerabilidade social, com foco em programação e desenvolvimento de software.\n\nO programa oferece cursos gratuitos de:\n• Lógica de Programação\n• Desenvolvimento Web (HTML, CSS, JavaScript)\n• Python para Iniciantes\n• Banco de Dados\n• Git e GitHub\n\nAo final do programa, os participantes recebem certificação e apoio para inserção no mercado de trabalho.",
    
    "duvidas": [
        {
            "pergunta": "Quem pode participar do programa?",
            "resposta": "Pessoas a partir de 16 anos, em situação de vulnerabilidade social, que tenham interesse em aprender programação. É necessário ter concluído ou estar cursando o ensino médio."
        },
        {
            "pergunta": "O programa tem algum custo?",
            "resposta": "O Jovem Programador é totalmente gratuito para pessoas com renda familiar de até 3 salários mínimos. Todos os materiais e certificados são fornecidos sem custo."
        },
        {
            "pergunta": "Quando começam as aulas?",
            "resposta": "As aulas estão previstas para começar na segunda quinzena de março de 2024. As inscrições ficam abertas até o final de fevereiro."
        },
        {
            "pergunta": "Como me inscrever?",
            "resposta": "As inscrições podem ser feitas através do site oficial ou presencialmente nos pontos de atendimento nas cidades participantes. É necessário apresentar documentos pessoais e comprovante de renda."
        },
        {
            "pergunta": "Preciso ter conhecimento prévio em programação?",
            "resposta": "Não! O programa foi desenvolvido para iniciantes. Começamos do zero, ensinando desde os conceitos básicos até projetos práticos."
        }
    ],
    
    "cidades": [
        "Araranguá", "Blumenau", "Biguaçu", "Brusque", "Caçador", "Chapecó", 
        "Criciúma", "Florianópolis", "Itajaí", "Joinville", "Lages", "Palhoça", 
        "São José", "Tubarão", "Balneário Camboriú", "Concórdia", "Jaraguá do Sul", 
        "Navegantes", "Rio do Sul", "São Bento do Sul"
    ]
}

# Respostas simuladas do chatbot
respostas_chatbot = [
    "Olá! Sou o assistente do programa Jovem Programador! 🚀 Como posso te ajudar hoje?",
    "O programa Jovem Programador é uma iniciativa incrível para formar novos programadores! 💻",
    "Que legal que você tem interesse em programação! O programa oferece cursos gratuitos em várias tecnologias. 🎯",
    "As inscrições estão abertas! Você pode se inscrever através do site oficial ou nos pontos de atendimento. 📝",
    "O programa é totalmente gratuito e voltado para pessoas em situação de vulnerabilidade social. 🤝",
    "Não precisa ter conhecimento prévio! Começamos do básico e te levamos até projetos avançados! 🌟",
    "Temos vagas em mais de 20 cidades de Santa Catarina! Veja se sua cidade participa. 🏙️",
    "Além dos cursos, oferecemos certificação e apoio para inserção no mercado de trabalho! 💼",
    "O programa tem duração de 6 meses, com aulas presenciais e práticas em laboratório. ⏰",
    "Que pergunta interessante! O programa Jovem Programador realmente transforma vidas através da tecnologia! ✨"
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '')
    free_mode = request.json.get('free_mode', False)
    
    # Simular diferentes tipos de resposta baseado na mensagem
    if 'curso' in user_message.lower() or 'inscrição' in user_message.lower():
        response = "🎓 O programa oferece cursos gratuitos de programação! Você pode se inscrever através do site oficial. Os cursos incluem Lógica de Programação, Desenvolvimento Web, Python e muito mais!"
    elif 'cidade' in user_message.lower() or 'local' in user_message.lower():
        response = "📍 O programa está presente em mais de 20 cidades de Santa Catarina! Algumas das principais são: Florianópolis, Joinville, Blumenau, Chapecó, Criciúma e muitas outras."
    elif 'gratuito' in user_message.lower() or 'custo' in user_message.lower():
        response = "💰 Sim! O programa Jovem Programador é totalmente gratuito para pessoas com renda familiar de até 3 salários mínimos. Todos os materiais e certificados são fornecidos sem custo!"
    elif 'idade' in user_message.lower() or 'participar' in user_message.lower():
        response = "👥 Podem participar pessoas a partir de 16 anos que estejam em situação de vulnerabilidade social e tenham interesse em aprender programação!"
    elif free_mode:
        response = "🧠 Modo Gemini ativado! Posso conversar sobre qualquer assunto relacionado à programação e tecnologia. O que você gostaria de saber?"
    else:
        # Resposta aleatória das respostas simuladas
        import random
        response = random.choice(respostas_chatbot)
    
    return jsonify({'response': response})

@app.route('/api/data')
def get_data():
    return jsonify(dados_simulados)

if __name__ == '__main__':
    print("🚀 Iniciando servidor de teste da interface...")
    print("📱 Interface disponível em: http://localhost:5000")
    print("⚠️  Modo de teste - usando dados simulados")
    app.run(debug=True, port=5000, host='0.0.0.0')