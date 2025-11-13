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

// ===== SESSION ID MANAGEMENT =====
function getOrCreateSessionId() {
    /**
     * Gera ou recupera session_id do localStorage.
     * Persiste entre recarregamentos da página.
     */
    const STORAGE_KEY = 'chat_session_id';
    let sessionId = localStorage.getItem(STORAGE_KEY);
    
    if (!sessionId) {
        // Gera novo session_id: sess_ + timestamp + random
        const timestamp = Date.now();
        const random = Math.random().toString(36).substring(2, 11);
        sessionId = `sess_${timestamp}_${random}`;
        localStorage.setItem(STORAGE_KEY, sessionId);
    }
    
    return sessionId;
}

// ===== TRANSIÇÃO/LOCK PARA EVITAR FLICKER =====
const CHATLEO_TRANSITION_MS = 240;
let ChatleoLock = false;
function withChatleoLock(fn){
  if (ChatleoLock) return;
  ChatleoLock = true;
  try { fn(); } finally { setTimeout(()=>{ ChatleoLock=false; }, CHATLEO_TRANSITION_MS); }
}

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

// Avatares configuráveis via data-atributos do HTML
const widgetRoot = document.getElementById('chatbot-widget');
const BOT_AVATAR = widgetRoot?.dataset?.botAvatar || '/static/assets/logo.png';
const USER_AVATAR = widgetRoot?.dataset?.userAvatar || '/static/assets/logo-user.png';

const bubbleImg = document.querySelector('.chatleo-bubble__avatar img');
if (bubbleImg) {
    bubbleImg.src = BOT_AVATAR;
    bubbleImg.alt = "Abrir chat";
}

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
    // Mapear bolha raiz (chatleo-bubble)
    DOMElements.chatBubble = document.querySelector('.chatleo-bubble');
    
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

// Seleção consistente da bolha raiz (trigger ou .chatleo-bubble)
const bubbleRoot = () => (DOMElements.chatbotTrigger || DOMElements.chatBubble);

function setupEventListeners() {
    // Root único para abrir/fechar (trigger ou bolha), com lock e sem duplicação
    const root = bubbleRoot();
    if (root) {
        // A11y base
        root.setAttribute('role', 'button');
        root.setAttribute('aria-label', 'Abrir chat');
        root.setAttribute('tabindex', '0');
        
        if (!root.dataset.chatleoBound) {
            root.dataset.chatleoBound = '1';
            root.addEventListener('click', (e) => {
                e.stopPropagation();
                withChatleoLock(toggleWidget);
            });
            root.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    withChatleoLock(toggleWidget);
                }
            });
        }
        // Remover possível binding antigo direto no trigger
        try { DOMElements.chatbotTrigger?.removeEventListener('click', toggleWidget); } catch(_){}
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
    
    // Navegação por teclado global (não-passiva para permitir preventDefault)
    document.addEventListener('keydown', handleGlobalKeydown, { passive: false });
    
    // Clique fora para fechar
    document.addEventListener('click', handleClickOutside);
    
    // Reações nas mensagens
    document.addEventListener('click', handleReactionClick);

    // Onboarding da tooltip: apenas na primeira visita
    (function tipOnce(){
        try{
            if (!localStorage.getItem('chatleo_tip')){
                const b = bubbleRoot();
                b?.classList.add('show-tip');
                setTimeout(()=>{
                    b?.classList.remove('show-tip');
                    localStorage.setItem('chatleo_tip','1');
                }, 4000);
            }
        }catch(_){/* noop */}
    })();
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
        withChatleoLock(closeWidget);
        return;
    }
    
    // Alt + C para abrir/fechar chat
    if (e.altKey && e.key.toLowerCase() === 'c') {
        e.preventDefault();
        withChatleoLock(toggleWidget);
        return;
    }
    
    // Alt + M para minimizar
    if (e.altKey && e.key.toLowerCase() === 'm' && AppState.isWidgetOpen) {
        e.preventDefault();
        withChatleoLock(minimizeWidget);
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
    
    // Esconder bolha quando o chat estiver aberto e limpar badge
    const b = bubbleRoot();
    b?.classList.remove('chatleo-bubble--active');
    b?.classList.add('is-hidden');
    b?.setAttribute('aria-expanded', 'true');
    updateNotificationBadge(0);
    
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
    
    // Mostrar bolha novamente e atualizar ARIA
    const b = bubbleRoot();
    b?.classList.remove('is-hidden');
    b?.classList.remove('chatleo-bubble--active');
    if (b) b.style.animation = '';
    b?.setAttribute('aria-expanded', 'false');
    
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
    
    // Estado visual da bolha
    const b = bubbleRoot();
    b?.classList.remove('is-hidden');
    b?.classList.toggle('chatleo-bubble--active', AppState.isMinimized);
    if (AppState.isMinimized) {
        AppState.isWidgetOpen = false;
        DOMElements.chatbotWidget.classList.remove('active');
        b?.setAttribute('aria-expanded', 'false');
        announceToScreenReader('Chat minimizado');
    } else {
        announceToScreenReader('Chat expandido');
    }
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
    
    // Buscar resposta real no backend
    (async () => {
        try {
            const botResponse = await sendToBackend(message);
            hideTypingIndicator();
            addMessage(botResponse || 'Desculpe, estou indisponível no momento.', 'bot');
            if (AppState.isTTSEnabled && botResponse) speakText(botResponse);
        } catch (err) {
            hideTypingIndicator();
            addMessage('Erro ao conectar ao assistente. Tente novamente.', 'bot');
        }
    })();
    
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
        img.src = BOT_AVATAR;
        img.alt = 'Logo do bot';
        img.width = 35;
        img.height = 35;
        avatar.appendChild(img);
    } else {
        const img = document.createElement('img');
        img.src = USER_AVATAR;
        img.alt = 'Logo do usuário';
        img.width = 20;
        img.height = 23;
        avatar.appendChild(img)
    }
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    if (sender === 'bot') {
        const frag = linkifyText(content);
        messageContent.appendChild(frag);
    } else {
        messageContent.textContent = content;
    }
    
    bubble.appendChild(messageContent);
    
    // Reações desativadas (UI-only): não anexar botões de reação

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    
    DOMElements.widgetMessages.appendChild(messageDiv);
    
    // Salvar no histórico
    AppState.messageHistory.push({ content, sender, timestamp: Date.now() });
    
    // Scroll para baixo (robusto)
    scrollMessagesToBottom();
    
    // Anunciar nova mensagem
    if (sender === 'bot') {
        announceToScreenReader(`Nova mensagem do assistente: ${content}`);
    }
}

// Scroll robusto até o final da lista de mensagens
function scrollMessagesToBottom() {
    const list = document.querySelector('.widget-messages');
    if (!list) return;
    list.scrollTop = list.scrollHeight;
    requestAnimationFrame(() => { list.scrollTop = list.scrollHeight; });
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
    const indicator = document.getElementById('widget-typing-indicator');
    if (!indicator) return;
    if (DOMElements.widgetMessages && DOMElements.typingIndicator) {
        DOMElements.widgetMessages.appendChild(DOMElements.typingIndicator);
    }
    if (DOMElements.typingIndicator) {
        DOMElements.typingIndicator.classList.add('active');
        announceToScreenReader('O assistente está digitando');
    }
    indicator.classList.add('active');
    indicator.removeAttribute('hidden');
    indicator.setAttribute('aria-hidden', 'false');
    scrollMessagesToBottom();
}

function hideTypingIndicator() {
    if (DOMElements.typingIndicator) {
        DOMElements.typingIndicator.classList.remove('active');
    }
    const indicator = document.getElementById('widget-typing-indicator');
    if (!indicator) return;
    indicator.classList.remove('active');
    indicator.setAttribute('hidden', 'true');
    indicator.setAttribute('aria-hidden', 'true');
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

// ===== NOTIFICAÇÕES (BADGE) =====
function updateNotificationBadge(count) {
    const badge = document.getElementById('chatleo-badge') || document.getElementById('chat-notification');
    if (!badge) return;
    const span = badge.querySelector('span') || badge;
    const next = Math.max(0, Number(count) || 0);
    if (span && span.textContent !== undefined) span.textContent = String(next);
    if (next === 0) {
        badge.setAttribute('hidden', '');
    } else {
        badge.removeAttribute('hidden');
    }
}

function notifyIncomingMessage() {
    if (!AppState.isWidgetOpen) {
        const badge = document.getElementById('chatleo-badge') || document.getElementById('chat-notification');
        const current = Number((badge?.textContent || '0').trim()) || 0;
        updateNotificationBadge(current + 1);
        const bubble = DOMElements.chatbotTrigger || DOMElements.chatBubble;
        bubble?.classList.add('chatleo-bubble--active');
    }
}

const FRIENDLY_NAMES = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "tiktok.com": "TikTok",
    "jovemprogramador.com.br": "Site oficial",
    "portal.sc.senac.br": "Portal Senac",
    "programajovemprogramador.com.br": "Programa Jovem Programador",
};

function linkifyText(text) {
    const urlRegex = /(https?:\/\/[^\s<]+|www\.[^\s<]+)/gi;
    const fragment = document.createDocumentFragment();
    let lastIndex = 0;
    text.replace(urlRegex, (match, offset) => {
        if (offset > lastIndex) {
            fragment.appendChild(document.createTextNode(text.substring(lastIndex, offset)));
        }
        let url = match;
        if (url.startsWith('www.')) {
            url = 'https://' + url;
        }
        const a = document.createElement('a');
        a.href = url;
        let label = match;
        try {
            const domain = new URL(url).hostname.replace('www.', '');
            label = FRIENDLY_NAMES[domain] || domain;
        } catch (_) {
            label = match;
        }
        a.textContent = label;
        a.target = '_blank';
        a.rel = 'noopener noreferrer nofollow';
        fragment.appendChild(a);
        lastIndex = offset + match.length;
        return match;
    });
    if (lastIndex < text.length) {
        fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
    }
    return fragment;
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
        const sessionId = getOrCreateSessionId();
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message,
                session_id: sessionId
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            // Atualiza session_id no localStorage se backend retornou um diferente
            if (data.session_id && data.session_id !== sessionId) {
                localStorage.setItem('chat_session_id', data.session_id);
            }
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
    // Garantir que a lista de mensagens esteja alinhada no final ao iniciar
    scrollMessagesToBottom();
    
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
