// ===== ESTADO DA APLICAÇÃO =====
const AppState = {
    isWidgetOpen: false,
    isMinimized: false,
    currentXP: 150,
    messageHistory: [],
    currentFontSize: 'normal',
    isHighContrast: false,
    isTTSEnabled: false,
    ttsVoice: null,
    welcomeRendered: false
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

let isWaiting = false;

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

// Avatares configuráveis via data-atributos do HTML (serão atualizados por loadChatConfig)
let BOT_AVATAR = '/static/assets/logo.png';
let USER_AVATAR = '/static/assets/logo-user.png';

function setLocked(locked) {
    isWaiting = locked;
    const input = DOMElements.messageInput;
    const send = DOMElements.sendBtn;
    const quick1 = Array.from(DOMElements.quickBtns || []);
    const quick2 = Array.from(document.querySelectorAll('.chatleo-quick-button'));
    const quickAll = [...quick1, ...quick2];
    if (input) {
        input.disabled = locked;
        input.classList.toggle('is-disabled', locked);
        input.setAttribute('aria-disabled', locked ? 'true' : 'false');
    }
    if (send) {
        send.disabled = locked;
        send.classList.toggle('is-disabled', locked);
        send.setAttribute('aria-disabled', locked ? 'true' : 'false');
    }
    quickAll.forEach(btn => {
        btn.disabled = locked;
        btn.classList.toggle('is-disabled', locked);
        btn.setAttribute('aria-disabled', locked ? 'true' : 'false');
    });
}

// ===== CARREGAMENTO DE CONFIGS DO CHAT =====
async function loadChatConfig() {
    try {
        const resp = await fetch("/api/chat-config");
        if (!resp.ok) return null;
        const cfg = await resp.json();
        return cfg;
    } catch (err) {
        console.error("Erro ao carregar chat-config:", err);
        return null;
    }
}

function applyChatConfig(cfg) {
    if (!cfg) return;
    
    const widgetRoot = document.getElementById("chatbot-widget");
    const titleEl = document.getElementById("chat-title");
    
    // Atualizar título
    if (titleEl && cfg.chat_title) {
        titleEl.textContent = cfg.chat_title;
    }
    
    // Atualizar avatares globais
    if (cfg.bot_avatar) {
        BOT_AVATAR = cfg.bot_avatar;
    }
    if (cfg.user_avatar) {
        USER_AVATAR = cfg.user_avatar;
    }
    
    // Aplicar avatares nas imagens existentes
    const bubbleImg = document.querySelector('.chatleo-bubble__avatar img');
    if (bubbleImg) {
        bubbleImg.src = BOT_AVATAR;
        bubbleImg.alt = "Abrir chat";
    }
    
    const widgetMascot = document.querySelector('.widget-mascot img');
    if (widgetMascot) {
        widgetMascot.src = BOT_AVATAR;
    }
    
    // Aplicar cores via CSS variables
    if (widgetRoot) {
        if (cfg.bot_avatar) {
            widgetRoot.dataset.botAvatar = cfg.bot_avatar;
        }
        if (cfg.user_avatar) {
            widgetRoot.dataset.userAvatar = cfg.user_avatar;
        }
        if (cfg.primary_color) {
            widgetRoot.style.setProperty("--chat-primary", cfg.primary_color);
            widgetRoot.dataset.primaryColor = cfg.primary_color;
        }
        if (cfg.secondary_color) {
            widgetRoot.style.setProperty("--chat-secondary", cfg.secondary_color);
            widgetRoot.dataset.secondaryColor = cfg.secondary_color;
        }
        
        // Aplicar papel de parede
        const enabled = cfg.chat_background_enabled !== false; // default: true
        const type = cfg.chat_background_type || 'default';
        const color = cfg.chat_background_color || '';
        const imageUrl = cfg.chat_background_image_url || '';
        
        // Reseta estilos customizados antes
        widgetRoot.style.removeProperty('background-image');
        widgetRoot.style.removeProperty('background-color');
        widgetRoot.removeAttribute('data-has-background');
        
        if (enabled && type !== 'default') {
            widgetRoot.setAttribute('data-has-background', 'true');
            
            if (type === 'image' && imageUrl) {
                widgetRoot.style.backgroundImage = `url("${imageUrl}")`;
                widgetRoot.style.backgroundSize = 'cover';
                widgetRoot.style.backgroundPosition = 'center';
                widgetRoot.style.backgroundRepeat = 'no-repeat';
            } else if (type === 'color' && color) {
                widgetRoot.style.backgroundColor = color;
            }
        }
        
        // Sincronizar o rodapé (.widget-input-container) com o papel de parede
        const inputContainer = widgetRoot.querySelector('.widget-input-container');
        if (inputContainer) {
            // Limpa qualquer estilo inline anterior
            inputContainer.style.removeProperty('background');
            inputContainer.style.removeProperty('background-color');
            
            if (enabled && type !== 'default') {
                // Quando há papel de parede, deixamos o rodapé transparente
                // para o fundo do widget aparecer por trás
                inputContainer.style.backgroundColor = 'transparent';
            }
            // Caso contrário, deixamos o CSS padrão assumir (var(--bg-secondary))
        }
    }
    
    // Renderizar botões rápidos se configurados
    renderQuickActionsFromConfig(cfg);
}

// ===== RENDERIZAR BOTÕES RÁPIDOS DO CONFIG =====
function renderQuickActionsFromConfig(config) {
    const container = document.querySelector('.widget-quick-actions');
    if (!container) return;
    
    const enabled = !!config.quick_actions_enabled;
    const actions = Array.isArray(config.quick_actions) ? config.quick_actions : [];
    
    // Se desativado ou sem ações, não exibir nada
    if (!enabled || actions.length === 0) {
        container.innerHTML = '';
        container.setAttribute('hidden', 'true');
        DOMElements.quickBtns = [];
        return;
    }
    
    // Ativado e com ações: mostrar
    container.removeAttribute('hidden');
    container.innerHTML = '';
    
    actions.forEach(action => {
        const btn = document.createElement('button');
        btn.className = 'quick-btn';
        btn.type = 'button';
        
        const label = action.label || action.message || '';
        const payload = action.message || label;
        
        btn.textContent = label;
        btn.dataset.message = payload;
        btn.setAttribute('tabindex', '0');
        btn.setAttribute('aria-label', label);
        
        container.appendChild(btn);
    });
    
    // Atualiza referência e listeners
    DOMElements.quickBtns = container.querySelectorAll('.quick-btn');
    setupQuickButtonsListeners();
}

// ===== CONFIGURAR LISTENERS DOS BOTÕES RÁPIDOS =====
function setupQuickButtonsListeners() {
    // Recapturar botões (pode ter mudado se foram renderizados dinamicamente)
    DOMElements.quickBtns = document.querySelectorAll('.quick-btn');
    
    if (!DOMElements.quickBtns || DOMElements.quickBtns.length === 0) {
        return;
    }
    
    DOMElements.quickBtns.forEach(btn => {
        // Verificar se já tem listener (usando flag data attribute)
        if (btn.dataset.quickBtnListener === 'true') {
            return; // Já tem listener, pular
        }
        
        // Marcar como tendo listener
        btn.dataset.quickBtnListener = 'true';
        
        // Adicionar listeners
        btn.addEventListener('click', handleQuickAction);
        btn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleQuickAction.call(btn, e);
            }
        });
    });
}

// ===== RENDERIZAR MENSAGEM DE BOAS-VINDAS =====
function renderWelcomeMessage(cfg) {
    // Prevenir duplicação
    if (AppState.welcomeRendered) return;
    if (!DOMElements.widgetMessages) return;
    
    // Verificar se já existe mensagem de boas-vindas no histórico
    const hasWelcomeInHistory = AppState.messageHistory.some(
        msg => msg.sender === 'bot' && msg.isWelcome === true
    );
    if (hasWelcomeInHistory) {
        AppState.welcomeRendered = true;
        return;
    }
    
    // Obter mensagem de boas-vindas da config ou usar padrão
    const welcomeText = (cfg && cfg.welcome_message) 
        ? cfg.welcome_message 
        : 'Olá! 👋 Sou o assistente do Jovem Programador. Como posso te ajudar hoje? 🚀';
    
    // Remover mensagem fixa do HTML se existir
    const welcomeEl = document.querySelector('.welcome-message');
    if (welcomeEl) {
        welcomeEl.remove();
    }
    
    // Criar mensagem de boas-vindas como mensagem normal do bot
    const messageDiv = document.createElement('div');
    messageDiv.className = 'bot-message';
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    const img = document.createElement('img');
    img.src = BOT_AVATAR;
    img.alt = 'Logo do bot';
    img.width = 35;
    img.height = 35;
    avatar.appendChild(img);
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    const frag = linkifyText(welcomeText);
    messageContent.appendChild(frag);
    
    bubble.appendChild(messageContent);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    
    // Inserir no início do container de mensagens
    const firstChild = DOMElements.widgetMessages.firstChild;
    if (firstChild) {
        DOMElements.widgetMessages.insertBefore(messageDiv, firstChild);
    } else {
        DOMElements.widgetMessages.appendChild(messageDiv);
    }
    
    // Salvar no histórico com flag de boas-vindas
    AppState.messageHistory.push({ 
        content: welcomeText, 
        sender: 'bot', 
        timestamp: Date.now(),
        isWelcome: true
    });
    
    // Marcar como renderizada
    AppState.welcomeRendered = true;
    
    // Scroll para baixo
    scrollMessagesToBottom();
    
    // Anunciar para leitores de tela
    announceToScreenReader(`Mensagem de boas-vindas: ${welcomeText}`);
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
    
    // Botões de ação rápida - usar função auxiliar
    setupQuickButtonsListeners();
    
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
    runFontScaleSmokeTest();
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
    if (isWaiting) { e.preventDefault(); return; }
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
    
    document.body.classList.add('chat-open');
    
    // Esconder bolha quando o chat estiver aberto e limpar badge
    const b = bubbleRoot();
    b?.classList.remove('chatleo-bubble--active');
    b?.classList.add('is-hidden');
    b?.setAttribute('aria-expanded', 'true');
    updateNotificationBadge(0);
    
    // Renderizar mensagem de boas-vindas se ainda não foi renderizada
    if (!AppState.welcomeRendered) {
        // Carregar config para obter mensagem de boas-vindas
        loadChatConfig().then(cfg => {
            renderWelcomeMessage(cfg);
        });
    }
    
    // Focar no input de mensagem
    setTimeout(() => {
        if (DOMElements.messageInput) {
            DOMElements.messageInput.focus();
        }
    }, 300);
    
    announceToScreenReader('Chat aberto');
    // if (AppState.messageHistory.length === 0) {
    //     showWelcomeMessage();
    // }
}

function closeWidget() {
    if (!DOMElements.chatbotWidget) return;
    
    AppState.isWidgetOpen = false;
    AppState.isMinimized = false;
    
    DOMElements.chatbotWidget.classList.remove('active', 'minimized');
    
    document.body.classList.remove('chat-open');
    
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
        document.body.classList.remove('chat-open');
        b?.setAttribute('aria-expanded', 'false');
        announceToScreenReader('Chat minimizado');
    } else {
        announceToScreenReader('Chat expandido');
    }
}

// ===== MENSAGENS =====
function sendMessage() {
    if (isWaiting) return;
    const message = DOMElements.messageInput?.value.trim();
    if (!message) return;
    addMessage(message, 'user');
    DOMElements.messageInput.value = '';
    showTypingIndicator();
    setLocked(true);
    (async () => {
        try {
            const botResponse = await sendToBackend(message);
            hideTypingIndicator();
            addMessage(botResponse || 'Desculpe, estou indisponível no momento.', 'bot');
            if (AppState.isTTSEnabled && botResponse) speakText(botResponse);
        } catch (err) {
            hideTypingIndicator();
            addMessage('Erro ao conectar ao assistente. Tente novamente.', 'bot');
        } finally {
            setLocked(false);
        }
    })();
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
    if (isWaiting) return;
    
    const button = this instanceof HTMLElement ? this : (e && e.currentTarget);
    if (!button) return;
    
    const payload = button.dataset.message || button.textContent || '';
    const message = payload.trim();
    if (!message) return;
    
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

// ===== RENDERIZAR MARKDOWN PARA FRAGMENTO DOM (DOM-SAFE) =====
function renderMarkdownToFragment(text) {
    /**
     * Converte texto com markdown simples (**negrito**, *itálico*, \n) em DocumentFragment.
     * NÃO usa innerHTML - apenas DOM API para segurança.
     * 
     * @param {string} text - Texto que pode conter **negrito**, *itálico* e \n
     * @returns {DocumentFragment} Fragmento DOM com TextNodes, <strong>, <em>, <br>
     */
    const fragment = document.createDocumentFragment();
    if (!text) return fragment;
    
    // Primeiro, tratar quebras de linha reais (\n) e literais (\\n)
    // Substituir quebras de linha por um marcador temporário único
    const LINE_BREAK_MARKER = '\uE000'; // Caractere privado não usado
    const processedText = text
        .replace(/\r\n/g, LINE_BREAK_MARKER) // Windows: \r\n
        .replace(/\n/g, LINE_BREAK_MARKER)   // Unix: \n
        .replace(/\\n/g, LINE_BREAK_MARKER); // Literal: \n
    
    // Regex para encontrar tokens de markdown: **texto**, *texto*
    // Ordem: negrito primeiro (para não confundir com itálico), depois itálico
    const markdownRegex = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
    let lastIndex = 0;
    let match;
    
    while ((match = markdownRegex.exec(processedText)) !== null) {
        const matchStart = match.index;
        const matchText = match[0];
        
        // Adicionar texto antes do match (tratando quebras de linha)
        if (matchStart > lastIndex) {
            const segment = processedText.substring(lastIndex, matchStart);
            appendTextWithLineBreaks(fragment, segment, LINE_BREAK_MARKER);
        }
        
        // Processar o token encontrado
        if (matchText.startsWith('**') && matchText.endsWith('**')) {
            // Negrito: **texto** -> <strong>texto</strong>
            const content = matchText.slice(2, -2); // Remove ** do início e fim
            const strong = document.createElement('strong');
            strong.textContent = content;
            fragment.appendChild(strong);
        } else if (matchText.startsWith('*') && matchText.endsWith('*') && matchText.length > 2) {
            // Itálico: *texto* -> <em>texto</em>
            // Verificar que não é parte de um negrito (já processado acima)
            const content = matchText.slice(1, -1); // Remove * do início e fim
            const em = document.createElement('em');
            em.textContent = content;
            fragment.appendChild(em);
        }
        
        lastIndex = matchStart + matchText.length;
    }
    
    // Adicionar texto restante após o último match (tratando quebras de linha)
    // Só executa se encontrou pelo menos um match (lastIndex > 0)
    if (lastIndex > 0 && lastIndex < processedText.length) {
        const tail = processedText.substring(lastIndex);
        appendTextWithLineBreaks(fragment, tail, LINE_BREAK_MARKER);
    }
    
    // Se não encontrou nenhum markdown, retorna apenas TextNode (com quebras de linha tratadas)
    if (lastIndex === 0) {
        appendTextWithLineBreaks(fragment, processedText, LINE_BREAK_MARKER);
    }
    
    return fragment;
}

// Helper para adicionar texto tratando quebras de linha
function appendTextWithLineBreaks(fragment, text, marker) {
    if (!text) return;
    const parts = text.split(marker);
    for (let i = 0; i < parts.length; i++) {
        if (parts[i]) {
            fragment.appendChild(document.createTextNode(parts[i]));
        }
        if (i < parts.length - 1) {
            fragment.appendChild(document.createElement('br'));
        }
    }
}

function linkifyText(text) {
    const urlRegex = /(https?:\/\/[^\s<]+|www\.[^\s<]+)/gi;
    const fragment = document.createDocumentFragment();
    let lastIndex = 0;
    text.replace(urlRegex, (match, offset) => {
        if (offset > lastIndex) {
            // Trecho de texto antes da URL: processar markdown
            const segment = text.substring(lastIndex, offset);
            const mdFrag = renderMarkdownToFragment(segment);
            fragment.appendChild(mdFrag);
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
        // Trecho de texto após a última URL: processar markdown
        const tail = text.substring(lastIndex);
        const mdFrag = renderMarkdownToFragment(tail);
        fragment.appendChild(mdFrag);
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
    runFontScaleSmokeTest();
}

// ===== Teste simples de verificação de escala de fonte =====
function runFontScaleSmokeTest() {
    try {
        const targets = [
            '.chatbot-widget .message-content',
            '.chatbot-widget .message-bubble',
            '.chatbot-widget .widget-messages'
        ];
        const results = targets.map(sel => {
            const el = document.querySelector(sel);
            const fs = el ? window.getComputedStyle(el).fontSize : 'n/a';
            return `${sel}: ${fs}`;
        });
        console.debug('[FontScaleTest]', AppState.currentFontSize, results.join(' | '));
    } catch (_) { /* noop */ }
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
    document.addEventListener('DOMContentLoaded', async () => {
        const cfg = await loadChatConfig();
        applyChatConfig(cfg);
        initializeApp();
        // A mensagem de boas-vindas será renderizada quando o widget for aberto pela primeira vez
    });
} else {
    (async () => {
        const cfg = await loadChatConfig();
        applyChatConfig(cfg);
        initializeApp();
        // A mensagem de boas-vindas será renderizada quando o widget for aberto pela primeira vez
    })();
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
