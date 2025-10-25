// ===== ESTADO DA APLICAÇÃO =====
const AppState = {
    isWidgetOpen: false,
    isMinimized: false,
    currentXP: 150,
    messageHistory: [],
    currentFontSize: 'normal',
    isHighContrast: false,
    isTTSEnabled: false,
    ttsVoice: null
};

// ===== ELEMENTOS DOM =====
const DOMElements = {
    // Trigger do chatbot
    chatbotTrigger: null,
    chatBubble: null,
    
    // Widget principal
    chatbotWidget: null,
    widgetHeader: null,
    widgetContent: null,
    widgetMessages: null,
    
    // Controles do header
    minimizeBtn: null,
    closeBtn: null,
    
    // Controles de acessibilidade
    fontSizeBtn: null,
    contrastBtn: null,
    ttsBtn: null,
    
    // Input e mensagens
    messageInput: null,
    sendBtn: null,
    quickBtns: null,
    
    // Indicadores
    typingIndicator: null,
    xpDisplay: null
};

// ===== INICIALIZAÇÃO =====
function initializeApp() {
    mapDOMElements();
    setupEventListeners();
    initializeAccessibility();
    initializeTTS();
    initializeWidget();
    loadUserPreferences();
    
    console.log('🤖 Chatbot Widget inicializado com acessibilidade completa!');
}

function mapDOMElements() {
    // Trigger do chatbot
    DOMElements.chatbotTrigger = document.getElementById('chatbot-trigger');
    DOMElements.chatBubble = document.querySelector('.chat-bubble');
    
    // Widget principal
    DOMElements.chatbotWidget = document.getElementById('chatbot-widget');
    DOMElements.widgetHeader = document.querySelector('.widget-header');
    DOMElements.widgetContent = document.querySelector('.widget-content');
    DOMElements.widgetMessages = document.getElementById('widget-messages');
    
    // Controles do header
    DOMElements.minimizeBtn = document.getElementById('widget-minimize');
    DOMElements.closeBtn = document.getElementById('widget-close');
    
    // Controles de acessibilidade
    DOMElements.fontSizeBtn = document.getElementById('font-size-btn');
    DOMElements.contrastBtn = document.getElementById('contrast-btn');
    DOMElements.ttsBtn = document.getElementById('tts-btn');
    
    // Input e mensagens
    DOMElements.messageInput = document.getElementById('widget-message-input');
    DOMElements.sendBtn = document.getElementById('widget-send-btn');
    DOMElements.quickBtns = document.querySelectorAll('.quick-btn');
    
    // Indicadores
    DOMElements.typingIndicator = document.getElementById('widget-typing-indicator');
    DOMElements.xpDisplay = document.querySelector('.widget-xp');
}

function setupEventListeners() {
    // Trigger do chatbot
    if (DOMElements.chatbotTrigger) {
        DOMElements.chatbotTrigger.addEventListener('click', toggleWidget);
        DOMElements.chatbotTrigger.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleWidget();
            }
        });
    }
    
    // Controles do header
    if (DOMElements.minimizeBtn) {
        DOMElements.minimizeBtn.addEventListener('click', minimizeWidget);
    }
    
    if (DOMElements.closeBtn) {
        DOMElements.closeBtn.addEventListener('click', closeWidget);
    }
    
    // Controles de acessibilidade
    if (DOMElements.fontSizeBtn) {
        DOMElements.fontSizeBtn.addEventListener('click', cycleFontSize);
    }
    
    if (DOMElements.contrastBtn) {
        DOMElements.contrastBtn.addEventListener('click', toggleHighContrast);
    }
    
    if (DOMElements.ttsBtn) {
        DOMElements.ttsBtn.addEventListener('click', toggleTTS);
    }
    
    // Input de mensagem
    if (DOMElements.messageInput) {
        DOMElements.messageInput.addEventListener('keydown', handleInputKeydown);
        DOMElements.messageInput.addEventListener('input', handleInputChange);
    }
    
    if (DOMElements.sendBtn) {
        DOMElements.sendBtn.addEventListener('click', sendMessage);
    }
    
    // Botões de ação rápida
    DOMElements.quickBtns.forEach(btn => {
        btn.addEventListener('click', handleQuickAction);
        btn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleQuickAction.call(btn);
            }
        });
    });
    
    // Navegação por teclado global
    document.addEventListener('keydown', handleGlobalKeydown);
    
    // Clique fora para fechar
    document.addEventListener('click', handleClickOutside);
    
    // Reações nas mensagens
    document.addEventListener('click', handleReactionClick);
}

// ===== FUNCIONALIDADES DE ACESSIBILIDADE =====
function initializeAccessibility() {
    // Adicionar ARIA labels
    addAriaLabels();
    
    // Configurar navegação por teclado
    setupKeyboardNavigation();
    
    // Configurar anúncios para leitores de tela
    setupScreenReaderAnnouncements();
}

function addAriaLabels() {
    if (DOMElements.chatbotWidget) {
        DOMElements.chatbotWidget.setAttribute('role', 'dialog');
        DOMElements.chatbotWidget.setAttribute('aria-labelledby', 'widget-title');
        DOMElements.chatbotWidget.setAttribute('aria-describedby', 'widget-description');
    }
    
    if (DOMElements.widgetMessages) {
        DOMElements.widgetMessages.setAttribute('aria-live', 'polite');
        DOMElements.widgetMessages.setAttribute('aria-atomic', 'false');
    }
}

function setupKeyboardNavigation() {
    // Tornar elementos focáveis
    const focusableElements = [
        DOMElements.chatbotTrigger,
        DOMElements.minimizeBtn,
        DOMElements.closeBtn,
        DOMElements.fontSizeBtn,
        DOMElements.contrastBtn,
        DOMElements.ttsBtn,
        DOMElements.messageInput,
        DOMElements.sendBtn,
        ...DOMElements.quickBtns
    ].filter(el => el);
    
    focusableElements.forEach(el => {
        if (!el.hasAttribute('tabindex')) {
            el.setAttribute('tabindex', '0');
        }
    });
}

function setupScreenReaderAnnouncements() {
    // Criar elemento para anúncios
    const announcer = document.createElement('div');
    announcer.id = 'accessibility-announcer';
    announcer.className = 'sr-only';
    announcer.setAttribute('aria-live', 'polite');
    announcer.setAttribute('aria-atomic', 'true');
    document.body.appendChild(announcer);
}

function announceToScreenReader(message) {
    const announcer = document.getElementById('accessibility-announcer');
    if (announcer) {
        announcer.textContent = message;
        setTimeout(() => {
            announcer.textContent = '';
        }, 1000);
    }
}

// ===== FUNCIONALIDADES TTS =====
function initializeTTS() {
    if ('speechSynthesis' in window) {
        // Carregar vozes disponíveis
        loadTTSVoices();
        
        // Atualizar vozes quando carregarem
        speechSynthesis.addEventListener('voiceschanged', loadTTSVoices);
    } else {
        console.warn('TTS não suportado neste navegador');
        if (DOMElements.ttsBtn) {
            DOMElements.ttsBtn.style.display = 'none';
        }
    }
}

function loadTTSVoices() {
    const voices = speechSynthesis.getVoices();
    // Preferir voz em português
    AppState.ttsVoice = voices.find(voice => 
        voice.lang.startsWith('pt') || voice.lang.startsWith('pt-BR')
    ) || voices[0];
}

function toggleTTS() {
    AppState.isTTSEnabled = !AppState.isTTSEnabled;
    
    if (DOMElements.ttsBtn) {
        DOMElements.ttsBtn.classList.toggle('active', AppState.isTTSEnabled);
        DOMElements.ttsBtn.setAttribute('aria-pressed', AppState.isTTSEnabled);
    }
    
    const status = AppState.isTTSEnabled ? 'ativada' : 'desativada';
    announceToScreenReader(`Leitura de voz ${status}`);
    
    saveUserPreferences();
}

function speakText(text) {
    if (!AppState.isTTSEnabled || !('speechSynthesis' in window)) return;
    
    // Parar qualquer fala anterior
    speechSynthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    if (AppState.ttsVoice) {
        utterance.voice = AppState.ttsVoice;
    }
    utterance.rate = 0.9;
    utterance.pitch = 1;
    utterance.volume = 0.8;
    
    // Adicionar indicador visual
    if (DOMElements.ttsBtn) {
        DOMElements.ttsBtn.classList.add('tts-speaking');
    }
    
    utterance.onend = () => {
        if (DOMElements.ttsBtn) {
            DOMElements.ttsBtn.classList.remove('tts-speaking');
        }
    };
    
    speechSynthesis.speak(utterance);
}

// ===== CONTROLE DE FONTE =====
function cycleFontSize() {
    const sizes = ['small', 'normal', 'large', 'extra-large'];
    const currentIndex = sizes.indexOf(AppState.currentFontSize);
    const nextIndex = (currentIndex + 1) % sizes.length;
    AppState.currentFontSize = sizes[nextIndex];
    
    // Aplicar tamanho da fonte
    document.body.className = document.body.className.replace(/font-\w+/g, '');
    document.body.classList.add(`font-${AppState.currentFontSize}`);
    
    // Atualizar botão
    if (DOMElements.fontSizeBtn) {
        const icon = DOMElements.fontSizeBtn.querySelector('.font-icon');
        if (icon) {
            const sizeLabels = {
                'small': 'Aa',
                'normal': 'Aa',
                'large': 'AA',
                'extra-large': 'AA'
            };
            icon.textContent = sizeLabels[AppState.currentFontSize];
        }
    }
    
    announceToScreenReader(`Tamanho da fonte alterado para ${AppState.currentFontSize}`);
    saveUserPreferences();
}

// ===== CONTROLE DE CONTRASTE =====
function toggleHighContrast() {
    AppState.isHighContrast = !AppState.isHighContrast;
    
    document.body.classList.toggle('high-contrast', AppState.isHighContrast);
    
    if (DOMElements.contrastBtn) {
        DOMElements.contrastBtn.classList.toggle('active', AppState.isHighContrast);
        DOMElements.contrastBtn.setAttribute('aria-pressed', AppState.isHighContrast);
    }
    
    const status = AppState.isHighContrast ? 'ativado' : 'desativado';
    announceToScreenReader(`Alto contraste ${status}`);
    
    saveUserPreferences();
}

// ===== NAVEGAÇÃO POR TECLADO =====
function handleGlobalKeydown(e) {
    // ESC para fechar widget
    if (e.key === 'Escape' && AppState.isWidgetOpen) {
        closeWidget();
        return;
    }
    
    // Alt + C para abrir/fechar chat
    if (e.altKey && e.key.toLowerCase() === 'c') {
        e.preventDefault();
        toggleWidget();
        return;
    }
    
    // Alt + M para minimizar
    if (e.altKey && e.key.toLowerCase() === 'm' && AppState.isWidgetOpen) {
        e.preventDefault();
        minimizeWidget();
        return;
    }
    
    // Tab navigation dentro do widget
    if (e.key === 'Tab' && AppState.isWidgetOpen) {
        handleTabNavigation(e);
    }
}

function handleTabNavigation(e) {
    const focusableElements = DOMElements.chatbotWidget.querySelectorAll(
        'button, input, [tabindex="0"]'
    );
    
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    
    if (e.shiftKey) {
        // Shift + Tab (navegação reversa)
        if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
        }
    } else {
        // Tab (navegação normal)
        if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
        }
    }
}

function handleInputKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// ===== FUNCIONALIDADES DO WIDGET =====
function toggleWidget() {
    if (AppState.isWidgetOpen) {
        closeWidget();
    } else {
        openWidget();
    }
}

function openWidget() {
    if (!DOMElements.chatbotWidget) return;
    
    AppState.isWidgetOpen = true;
    AppState.isMinimized = false;
    
    DOMElements.chatbotWidget.classList.add('active');
    DOMElements.chatbotWidget.classList.remove('minimized');
    
    // Focar no input de mensagem
    setTimeout(() => {
        if (DOMElements.messageInput) {
            DOMElements.messageInput.focus();
        }
    }, 300);
    
    announceToScreenReader('Chat aberto');
    
    // // Mostrar mensagem de boas-vindas se for a primeira vez
    // if (AppState.messageHistory.length === 0) {
    //     showWelcomeMessage();
    // }
}

function closeWidget() {
    if (!DOMElements.chatbotWidget) return;
    
    AppState.isWidgetOpen = false;
    AppState.isMinimized = false;
    
    DOMElements.chatbotWidget.classList.remove('active', 'minimized');
    
    // Focar no trigger
    if (DOMElements.chatbotTrigger) {
        DOMElements.chatbotTrigger.focus();
    }
    
    announceToScreenReader('Chat fechado');
}

function minimizeWidget() {
    if (!DOMElements.chatbotWidget) return;
    
    AppState.isMinimized = !AppState.isMinimized;
    DOMElements.chatbotWidget.classList.toggle('minimized', AppState.isMinimized);
    
    const status = AppState.isMinimized ? 'minimizado' : 'expandido';
    announceToScreenReader(`Chat ${status}`);
}

// ===== MENSAGENS =====
function sendMessage() {
    const message = DOMElements.messageInput?.value.trim();
    if (!message) return;
    
    // Adicionar mensagem do usuário
    addMessage(message, 'user');
    
    // Limpar input
    DOMElements.messageInput.value = '';
    
    // Mostrar indicador de digitação
    showTypingIndicator();
    
    // Simular resposta do bot
    setTimeout(() => {
        hideTypingIndicator();
        const botResponse = getBotResponse(message);
        addMessage(botResponse, 'bot');
        
        // TTS para resposta do bot
        if (AppState.isTTSEnabled) {
            speakText(botResponse);
        }
    }, 1500);
    
    // Adicionar XP
    addXP(10);
}

function addMessage(content, sender) {
    if (!DOMElements.widgetMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `${sender}-message`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';

    if (sender === 'bot') {
        const img = document.createElement('img');
        img.src = 'assets/logo.png'; // Caminho da tua imagem
        img.alt = 'Logo do bot';
        img.width = 35;
        img.height = 35;
        avatar.appendChild(img);
    } else {
        const img = document.createElement('img');
        img.src = 'assets/logo-user.png'; // Caminho da tua imagem
        img.alt = 'Logo do usuário';
        img.width = 20;
        img.height = 23;
        avatar.appendChild(img)
    }
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.textContent = content;
    
    bubble.appendChild(messageContent);
    
    // Adicionar reações apenas para mensagens do bot
    if (sender === 'bot') {
        const reactions = document.createElement('div');
        reactions.className = 'message-reactions';
        
        const reactionEmojis = ['👍', '❤️', '😊', '🤔'];
        reactionEmojis.forEach(emoji => {
            const reactionBtn = document.createElement('button');
            reactionBtn.className = 'reaction-btn';
            reactionBtn.textContent = emoji;
            reactionBtn.setAttribute('aria-label', `Reagir com ${emoji}`);
            reactionBtn.setAttribute('tabindex', '0');
            reactions.appendChild(reactionBtn);
        });
        
        bubble.appendChild(reactions);
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    
    DOMElements.widgetMessages.appendChild(messageDiv);
    
    // Salvar no histórico
    AppState.messageHistory.push({ content, sender, timestamp: Date.now() });
    
    // Scroll para baixo
    scrollToBottom();
    
    // Anunciar nova mensagem
    if (sender === 'bot') {
        announceToScreenReader(`Nova mensagem do assistente: ${content}`);
    }
}

function getBotResponse(userMessage) {
    const responses = {
        'oi': 'Olá! Como posso te ajudar hoje? 😊',
        'i ae': 'Olá... Como posso te ajudar hoje?',
        'olá': 'Oi! Estou aqui para te ajudar! 👋',
        'como começar': 'Para começar na programação, recomendo aprender lógica de programação primeiro, depois escolher uma linguagem como Python ou JavaScript!',
        'carreira': 'A área de tecnologia oferece muitas oportunidades! Foque em aprender constantemente e construir um portfólio sólido.',
        'ferramentas': 'Algumas ferramentas essenciais: VS Code, Git, GitHub, e dependendo da área, frameworks específicos.',
        'estudo': 'Recomendo plataformas como freeCodeCamp, Coursera, e documentações oficiais. A prática é fundamental!',
        'default': 'Interessante! Posso te ajudar com dúvidas sobre programação, carreira em tech, ferramentas e recursos de estudo. O que você gostaria de saber?',
        'default': 'Posso te ajudar com dúvidas sobre programação, carreira em tech, ferramentas e recursos de estudo. O que você gostaria de saber?'
    };
    
    const lowerMessage = userMessage.toLowerCase();
    
    for (const [key, response] of Object.entries(responses)) {
        if (key !== 'default' && lowerMessage.includes(key)) {
            return response;
        }
    }
    
    return responses.default;
}

function showWelcomeMessage() {
    setTimeout(() => {
        addMessage('Olá! 👋 Bem-vindo ao Jovem Programador! Como posso te ajudar hoje?', 'bot');
    }, 500);
}

// ===== AÇÕES RÁPIDAS =====
function handleQuickAction(e) {
    const button = e.target.closest('.quick-btn');
    if (!button) return;
    
    const message = button.textContent.trim();
    
    // Simular clique no input e envio
    if (DOMElements.messageInput) {
        DOMElements.messageInput.value = message;
        sendMessage();
    }
}

// ===== INDICADORES =====
function showTypingIndicator() {
    if (DOMElements.typingIndicator) {
        DOMElements.typingIndicator.classList.add('active');
        announceToScreenReader('O assistente está digitando');
    }
}

function hideTypingIndicator() {
    if (DOMElements.typingIndicator) {
        DOMElements.typingIndicator.classList.remove('active');
    }
}

// ===== SISTEMA XP =====
function addXP(amount) {
    AppState.currentXP += amount;
    updateXPDisplay();
}

function updateXPDisplay() {
    if (DOMElements.xpDisplay) {
        DOMElements.xpDisplay.textContent = `${AppState.currentXP} XP`;
    }
}

// ===== UTILITÁRIOS =====
function scrollToBottom() {
    if (DOMElements.widgetMessages) {
        DOMElements.widgetMessages.scrollTop = DOMElements.widgetMessages.scrollHeight;
    }
}

function handleClickOutside(e) {
    if (AppState.isWidgetOpen && 
        !DOMElements.chatbotWidget?.contains(e.target) && 
        !DOMElements.chatbotTrigger?.contains(e.target)) {
        closeWidget();
    }
}

function handleReactionClick(e) {
    if (e.target.classList.contains('reaction-btn')) {
        e.target.style.transform = 'scale(1.3)';
        setTimeout(() => {
            e.target.style.transform = '';
        }, 200);
        
        announceToScreenReader(`Reação ${e.target.textContent} adicionada`);
    }
}

function handleInputChange() {
    // Feedback visual para input ativo
    if (DOMElements.messageInput?.value.length > 0) {
        DOMElements.sendBtn?.classList.add('active');
    } else {
        DOMElements.sendBtn?.classList.remove('active');
    }
}

// ===== PERSISTÊNCIA =====
function saveUserPreferences() {
    const preferences = {
        fontSize: AppState.currentFontSize,
        highContrast: AppState.isHighContrast,
        ttsEnabled: AppState.isTTSEnabled
    };
    
    localStorage.setItem('chatbot-preferences', JSON.stringify(preferences));
}

function loadUserPreferences() {
    try {
        const saved = localStorage.getItem('chatbot-preferences');
        if (saved) {
            const preferences = JSON.parse(saved);
            
            // Aplicar preferências salvas
            if (preferences.fontSize) {
                AppState.currentFontSize = preferences.fontSize;
                document.body.classList.add(`font-${preferences.fontSize}`);
            }
            
            if (preferences.highContrast) {
                AppState.isHighContrast = true;
                document.body.classList.add('high-contrast');
                if (DOMElements.contrastBtn) {
                    DOMElements.contrastBtn.classList.add('active');
                }
            }
            
            if (preferences.ttsEnabled) {
                AppState.isTTSEnabled = true;
                if (DOMElements.ttsBtn) {
                    DOMElements.ttsBtn.classList.add('active');
                }
            }
        }
    } catch (error) {
        console.warn('Erro ao carregar preferências:', error);
    }
}

// ===== INTEGRAÇÃO COM BACKEND =====
async function sendToBackend(message) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message })
        });
        
        if (response.ok) {
            const data = await response.json();
            return data.response;
        }
    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
    }
    
    return null;
}

function initializeWidget() {
    // Configurações iniciais do widget
    updateXPDisplay();
    
    // Adicionar atributos de acessibilidade dinâmicos
    if (DOMElements.chatbotTrigger) {
        DOMElements.chatbotTrigger.setAttribute('aria-label', 'Abrir chat do Jovem Programador');
        DOMElements.chatbotTrigger.setAttribute('title', 'Clique para abrir o chat (Alt+C)');
    }
}

// ===== INICIALIZAÇÃO QUANDO DOM ESTIVER PRONTO =====
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

// ===== EXPORTS PARA DEBUG =====
window.ChatbotDebug = {
    AppState,
    DOMElements,
    toggleWidget,
    addMessage,
    speakText,
    toggleHighContrast,
    cycleFontSize,
    toggleTTS
};