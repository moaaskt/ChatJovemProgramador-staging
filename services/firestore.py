"""
Módulo de integração com Firestore para persistência de conversas.
Todas as funções retornam silenciosamente se AI_FIRESTORE_ENABLED=false.
"""

import os
import json
import logging
import base64
from datetime import datetime, timedelta
from firebase_admin import initialize_app, credentials, firestore
from firebase_admin.exceptions import FirebaseError
from werkzeug.security import generate_password_hash, check_password_hash
import difflib
import unicodedata

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) 

# Flag global para verificar se Firestore está habilitado
_firestore_enabled = None
_db = None

# Lista completa de TODAS as cidades de Santa Catarina (295 municípios)
CIDADES_SANTA_CATARINA = [
    "Abdon Batista", "Abelardo Luz", "Agrolândia", "Agronômica", "Água Doce",
    "Águas de Chapecó", "Águas Frias", "Águas Mornas", "Alfredo Wagner",
    "Alto Bela Vista", "Anchieta", "Angelina", "Anita Garibaldi",
    "Anitápolis", "Antônio Carlos", "Apiúna", "Arabutã", "Araquari",
    "Araranguá", "Armazém", "Arroio Trinta", "Arvoredo", "Ascurra",
    "Atalanta", "Aurora", "Balneário Arroio do Silva", "Balneário Barra do Sul",
    "Balneário Camboriú", "Balneário Gaivota", "Bandeirante", "Barra Bonita",
    "Barra Velha", "Bela Vista do Toldo", "Belmonte", "Benedito Novo",
    "Biguaçu", "Blumenau", "Bocaina do Sul", "Bom Jardim da Serra",
    "Bom Jesus", "Bom Jesus do Oeste", "Bom Retiro", "Botuverá",
    "Braço do Norte", "Braço do Trombudo", "Brunópolis", "Brusque",
    "Caçador", "Caibi", "Calmon", "Camboriú", "Campo Alegre",
    "Campo Belo do Sul", "Campo Erê", "Campos Novos", "Canelinha",
    "Canoinhas", "Capão Alto", "Capinzal", "Capivari de Baixo",
    "Catanduvas", "Caxambu do Sul", "Celso Ramos", "Cerro Negro",
    "Chapadão do Lageado", "Chapecó", "Cocal do Sul", "Concórdia",
    "Cordilheira Alta", "Coronel Freitas", "Coronel Martins", "Correia Pinto",
    "Corupá", "Criciúma", "Cunha Porã", "Cunhataí", "Curitibanos",
    "Descanso", "Dionísio Cerqueira", "Dona Emma", "Doutor Pedrinho",
    "Entre Rios", "Ermo", "Erval Velho", "Faxinal dos Guedes",
    "Flor do Sertão", "Florianópolis", "Formosa do Sul", "Forquilhinha",
    "Fraiburgo", "Frei Rogério", "Galvão", "Garopaba", "Garuva",
    "Gaspar", "Governador Celso Ramos", "Grão Pará", "Gravatal",
    "Guabiruba", "Guaraciaba", "Guaramirim", "Guarujá do Sul",
    "Guatambú", "Herval d'Oeste", "Ibiam", "Ibicaré", "Ibirama",
    "Içara", "Ilhota", "Imaruí", "Imbituba", "Imbuia", "Indaial",
    "Iomerê", "Ipira", "Iporã do Oeste", "Ipuaçu", "Ipumirim",
    "Iraceminha", "Irani", "Irati", "Irineópolis", "Itá", "Itaiópolis",
    "Itajaí", "Itapema", "Itapiranga", "Itapoá", "Ituporanga", "Jaborá",
    "Jacinto Machado", "Jaguaruna", "Jaraguá do Sul", "Jardinópolis",
    "Joaçaba", "Joinville", "José Boiteux", "Jupiá", "Lacerdópolis",
    "Lages", "Laguna", "Lajeado Grande", "Laurentino", "Lauro Muller",
    "Lebon Régis", "Leoberto Leal", "Lindóia do Sul", "Lontras",
    "Luiz Alves", "Luzerna", "Macieira", "Mafra", "Major Gercino",
    "Major Vieira", "Maracajá", "Maravilha", "Marema", "Massaranduba",
    "Matos Costa", "Meleiro", "Mirim Doce", "Modelo", "Mondaí",
    "Monte Carlo", "Monte Castelo", "Morro da Fumaça", "Morro Grande",
    "Navegantes", "Nova Erechim", "Nova Itaberaba", "Nova Trento",
    "Nova Veneza", "Novo Horizonte", "Orleans", "Otacílio Costa",
    "Ouro", "Ouro Verde", "Paial", "Painel", "Palhoça", "Palma Sola",
    "Palmeira", "Palmitos", "Papanduva", "Paraíso", "Passo de Torres",
    "Passos Maia", "Paulo Lopes", "Pedras Grandes", "Penha", "Peritiba",
    "Petrolândia", "Piçarras", "Pinhalzinho", "Pinheiro Preto",
    "Piratuba", "Planalto Alegre", "Pomerode", "Ponte Alta",
    "Ponte Alta do Norte", "Ponte Serrada", "Porto Belo", "Porto União",
    "Pouso Redondo", "Praia Grande", "Presidente Castelo Branco",
    "Presidente Getúlio", "Presidente Nereu", "Princesa", "Quilombo",
    "Rancho Queimado", "Rio das Antas", "Rio do Campo", "Rio do Oeste",
    "Rio do Sul", "Rio dos Cedros", "Rio Fortuna", "Rio Negrinho",
    "Rio Rufino", "Riqueza", "Rodeio", "Romelândia", "Salete",
    "Saltinho", "Salto Veloso", "Sangão", "Santa Cecília",
    "Santa Helena", "Santa Rosa de Lima", "Santa Rosa do Sul",
    "Santa Terezinha", "Santa Terezinha do Progresso", "Santiago do Sul",
    "Santo Amaro da Imperatriz", "São Bento do Sul", "São Bernardino",
    "São Bonifácio", "São Carlos", "São Cristóvão do Sul", "São Domingos",
    "São Francisco do Sul", "São João Batista", "São João do Itaperiú",
    "São João do Oeste", "São João do Sul", "São Joaquim", "São José",
    "São José do Cedro", "São José do Cerrito", "São Lourenço do Oeste",
    "São Ludgero", "São Martinho", "São Miguel da Boa Vista",
    "São Miguel do Oeste", "São Pedro de Alcântara", "Saudades",
    "Schroeder", "Seara", "Serra Alta", "Siderópolis", "Sombrio",
    "Sul Brasil", "Taió", "Tangará", "Tigrinhos", "Tijucas",
    "Timbé do Sul", "Timbó", "Timbó Grande", "Três Barras", "Treviso",
    "Treze de Maio", "Treze Tílias", "Trombudo Central", "Tubarão",
    "Tunápolis", "Turvo", "União do Oeste", "Urubici", "Urupema",
    "Urussanga", "Vargeão", "Vargem", "Vargem Bonita", "Vidal Ramos",
    "Videira", "Vitor Meireles", "Witmarsum", "Xanxerê", "Xavantina",
    "Xaxim", "Zortéa"
]

# Mapa de equivalências para cidades com variações de acentos/cedilha
# Mapeia versões sem acentos/cedilha para o nome oficial correto
CITY_EQUIVALENCE_MAP = {
    # Cidades com cedilha (ç) - Palhoça
    "palhoca": "Palhoça",
    "palhoça": "Palhoça",
    "palhoca_sc": "Palhoça",
    "palhoça_sc": "Palhoça",
    "palhocá": "Palhoça",  # Com acento agudo
    "Palhoca": "Palhoça",  # Primeira letra maiúscula
    "PalhocA": "Palhoça",  # Mistura maiúsculas/minúsculas
    "palhoca sc": "Palhoça",  # Com espaço antes de SC
    "palhoça sc": "Palhoça",  # Com espaço antes de SC
    # Cidades com acentos comuns que podem ter variações
    "itajai": "Itajaí",
    "itajai_sc": "Itajaí",
    "florianopolis": "Florianópolis",
    "florianopolis_sc": "Florianópolis",
    "sao jose": "São José",
    "sao jose_sc": "São José",
    "sao bento do sul": "São Bento do Sul",
    "sao bento do sul_sc": "São Bento do Sul",
    "sao miguel do oeste": "São Miguel do Oeste",
    "sao miguel do oeste_sc": "São Miguel do Oeste",
    # Adicionar outras cidades conforme necessário
}


def _is_enabled():
    """Verifica se Firestore está habilitado via variável de ambiente."""
    global _firestore_enabled
    if _firestore_enabled is None:
        _firestore_enabled = os.getenv("AI_FIRESTORE_ENABLED", "false").lower() == "true"
    return _firestore_enabled


def _load_firebase_credentials():
    """
    Carrega credenciais do Firebase de forma robusta, suportando múltiplos formatos:
    1. JSON direto na variável de ambiente (começa com '{')
    2. Caminho para arquivo JSON
    3. Base64 codificado
    
    Returns:
        dict: Dicionário com as credenciais do Firebase ou None se não conseguir carregar
    """
    credentials_value = os.getenv("FIREBASE_CREDENTIALS")
    
    if not credentials_value:
        logger.warning("[Firestore] FIREBASE_CREDENTIALS não encontrado na variável de ambiente.")
        return None
    
    # Remove espaços extras
    credentials_value = credentials_value.strip()
    
    # Caso 1: JSON direto (começa com '{')
    if credentials_value.startswith('{'):
        try:
            logger.debug("[Firestore] Tentando carregar credenciais como JSON direto...")
            cred_dict = json.loads(credentials_value)
            logger.info("[Firestore] Credenciais carregadas como JSON direto com sucesso.")
            return cred_dict
        except json.JSONDecodeError as e:
            logger.warning(f"[Firestore] Erro ao parsear JSON direto: {e}")
            # Continua para tentar outros métodos
    
    # Caso 2: Caminho para arquivo
    if os.path.exists(credentials_value):
        try:
            logger.debug(f"[Firestore] Tentando carregar credenciais do arquivo: {credentials_value}")
            with open(credentials_value, 'r', encoding='utf-8') as f:
                cred_dict = json.load(f)
            logger.info(f"[Firestore] Credenciais carregadas do arquivo '{credentials_value}' com sucesso.")
            return cred_dict
        except json.JSONDecodeError as e:
            logger.error(f"[Firestore] Erro ao parsear JSON do arquivo '{credentials_value}': {e}")
            return None
        except Exception as e:
            logger.error(f"[Firestore] Erro ao ler arquivo '{credentials_value}': {e}")
            return None
    
    # Caso 3: Base64 codificado
    try:
        logger.debug("[Firestore] Tentando decodificar credenciais como Base64...")
        decoded = base64.b64decode(credentials_value, validate=True)
        cred_dict = json.loads(decoded.decode('utf-8'))
        logger.info("[Firestore] Credenciais decodificadas de Base64 com sucesso.")
        return cred_dict
    except (ValueError, UnicodeDecodeError) as e:
        logger.debug(f"[Firestore] Não é Base64 válido: {e}")
    except json.JSONDecodeError as e:
        logger.warning(f"[Firestore] Erro ao parsear JSON decodificado de Base64: {e}")
    except Exception as e:
        logger.debug(f"[Firestore] Erro ao processar Base64: {e}")
    
    # Se chegou aqui, não conseguiu carregar de nenhuma forma
    logger.error("[Firestore] Não foi possível carregar credenciais. Verifique FIREBASE_CREDENTIALS.")
    logger.error("[Firestore] Formatos suportados:")
    logger.error("  1. JSON direto: FIREBASE_CREDENTIALS='{\"type\":\"service_account\",...}'")
    logger.error("  2. Caminho para arquivo: FIREBASE_CREDENTIALS='./service-account.json'")
    logger.error("  3. Base64: FIREBASE_CREDENTIALS='eyJ0eXBlIjoic2VydmljZV9hY2NvdW50In0='")
    return None


def init_admin():
    """
    Inicializa Firebase Admin SDK usando FIREBASE_CREDENTIALS.
    Suporta múltiplos formatos: JSON direto, caminho para arquivo, ou Base64.
    Deve ser chamado uma única vez no bootstrap da aplicação.
    """
    global _db
    
    if not _is_enabled():
        logger.info("[Firestore] Desabilitado (AI_FIRESTORE_ENABLED=false)")
        return
    
    if _db is not None:
        logger.info("[Firestore] Já inicializado")
        return
    
    try:
        # Carrega credenciais usando função auxiliar robusta
        cred_dict = _load_firebase_credentials()
        
        if not cred_dict:
            logger.warning("[Firestore] Não foi possível carregar credenciais. Firestore desabilitado.")
            return
        
        # Cria objeto de credenciais
        cred = credentials.Certificate(cred_dict)
        
        # Inicializa app (pode ser chamado múltiplas vezes, Firebase gerencia singleton)
        try:
            initialize_app(cred)
        except ValueError:
            # App já inicializado, tudo bem
            pass
        
        # Atualiza a variável global _db
        _db = firestore.client()
        logger.info("[Firestore] Inicializado com sucesso")
        logger.info(f"[Firestore] Projeto conectado: {_db.project}")
        
    except FirebaseError as e:
        logger.error(f"[Firestore] Erro ao inicializar Firebase Admin: {e}")
    except Exception as e:
        logger.error(f"[Firestore] Erro inesperado na inicialização: {e}")


def get_or_create_conversation(session_id):
    """
    Cria ou atualiza documento de conversa em conversations/{session_id}.
    
    Args:
        session_id: ID da sessão de conversa
        
    Returns:
        bool: True se sucesso, False caso contrário (silencioso)
    """
    if not _is_enabled() or _db is None:
        return False
    
    try:
        conv_ref = _db.collection("conversations").document(session_id)
        logger.info(f"[Firestore] Salvando conversa em: {conv_ref.path}")

        doc = conv_ref.get()
        if not doc.exists:
            # Documento novo: definir campos completos (mantendo compatibilidade)
            conv_ref.set({
                "session_id": session_id,
                # campos legados
                "iniciadoEm": firestore.SERVER_TIMESTAMP,
                "ultimaMensagemEm": firestore.SERVER_TIMESTAMP,
                # campos padronizados para analytics
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "total_user_messages": 0,
                "total_bot_messages": 0,
                "channel": "web",
                "status": "open",
            }, merge=True)
        else:
            # Documento existente: atualizar última atividade
            conv_ref.update({
                "ultimaMensagemEm": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })

        logger.debug(f"[Firestore] Conversa {session_id} atualizada")
        return True

    except Exception as e:
        logger.error(f"[Firestore] Erro ao salvar conversa {session_id}: {e}")
        return False


def get_conversation(session_id):
    """
    Retorna o documento da conversa em conversations/{session_id} como dict.
    Se Firestore estiver desabilitado ou ocorrer erro, retorna {}.
    """
    if not _is_enabled() or _db is None:
        return {}

    try:
        conv_ref = _db.collection("conversations").document(session_id)
        doc = conv_ref.get()
        if not doc.exists:
            return {}
        return doc.to_dict() or {}
    except Exception as e:
        logger.error(f"[Firestore] Erro em get_conversation({session_id}): {e}")
        return {}


def update_conversation(session_id, updates: dict):
    """
    Atualiza campos específicos da conversa em conversations/{session_id}.
    Não lança exceções para não quebrar o fluxo do chat.
    """
    if not _is_enabled() or _db is None:
        return False

    if not updates:
        return False

    try:
        conv_ref = _db.collection("conversations").document(session_id)
        conv_ref.set(updates, merge=True)
        logger.debug(f"[Firestore] Conversa {session_id} atualizada com {list(updates.keys())}")
        return True
    except Exception as e:
        logger.error(f"[Firestore] Erro em update_conversation({session_id}): {e}")
        return False


def save_message(session_id, role, text, meta=None):
    """
    Salva mensagem em conversations/{session_id}/messages.
    
    Args:
        session_id: ID da sessão
        role: 'user' ou 'assistant'
        text: Texto da mensagem
        meta: Dict opcional com metadados adicionais
        
    Returns:
        bool: True se sucesso, False caso contrário (silencioso)
    """
    if not _is_enabled() or _db is None:
        return False
    
    if role not in ["user", "assistant"]:
        logger.warning(f"[Firestore] Role inválido: {role}. Deve ser 'user' ou 'assistant'")
        return False
    
    try:
        # Normalizar role
        normalized_role = role
        if role == "assistant":
            normalized_role = "bot"
        elif role == "user":
            normalized_role = "user"

        # Montar dados da mensagem (novos + compatibilidade)
        message_data = {
            # novos campos padronizados
            "role": normalized_role,
            "content": text,
            "created_at": firestore.SERVER_TIMESTAMP,
            # campos antigos (compatibilidade)
            "papel": normalized_role,
            "texto": text,
            "criadoEm": firestore.SERVER_TIMESTAMP,
        }

        if meta is not None:
            message_data["metadata"] = meta

        conversation_ref = _db.collection("conversations").document(session_id)
        messages_ref = conversation_ref.collection("messages")

        logger.info(f"[Firestore] Salvando mensagem em: conversations/{session_id}/messages")
        messages_ref.add(message_data)
        logger.info(f"[Firestore] Mensagem gravada com sucesso no Firestore")

        # Atualizar contadores e timestamps da conversa
        updates = {
            "ultimaMensagemEm": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if normalized_role == "user":
            updates["total_user_messages"] = firestore.Increment(1)
        elif normalized_role == "bot":
            updates["total_bot_messages"] = firestore.Increment(1)

        conversation_ref.update(updates)

        logger.debug(f"[Firestore] Mensagem salva: {session_id}/{normalized_role}")
        return True

    except Exception as e:
        logger.error(f"[Firestore] Erro ao salvar mensagem {session_id}/{role}: {e}")
        return False


def get_conversation_counts(
    days: int | None = None,
    date_start: datetime | None = None,
    date_end: datetime | None = None,
):
    """
    Conta conversas na coleção 'conversations'.
    
    - Se date_start e date_end forem fornecidos, usa o intervalo [date_start, date_end].
    - Caso contrário, se days > 0, usa os últimos 'days' dias.
    - Se nada for informado, conta todas as conversas.
    """
    try:
        query = _db.collection("conversations")
        
        # Prioridade: intervalo manual
        if date_start and date_end:
            query = (
                query.where("created_at", ">=", date_start)
                     .where("created_at", "<=", date_end)
            )
        elif days and days > 0:
            today = datetime.utcnow()
            start = today - timedelta(days=days)
            query = query.where("created_at", ">=", start)
        
        convs = query.stream()
        total = 0
        
        for doc in convs:
            data = doc.to_dict() or {}
            
            # Se usamos filtro por intervalo manual, podemos ignorar docs sem created_at
            if (date_start or days) and not data.get("created_at"):
                continue
            
            total += 1
        
        return {"total_conversations": total}
    except Exception as e:
        logger.error(f"[Firestore] Erro ao contar conversas: {e}")
        return {"total_conversations": 0}


def get_message_counts_by_role():
    try:
        user_count = 0
        bot_count = 0

        messages = _db.collection_group("messages").stream()
        for msg in messages:
            data = msg.to_dict()
            role = data.get("role")
            if role == "user":
                user_count += 1
            elif role == "bot":
                bot_count += 1

        return {
            "user_messages": user_count,
            "bot_messages": bot_count,
        }
    except Exception as e:
        logger.error(f"[Firestore] Erro ao agrupar mensagens: {e}")
        return {
            "user_messages": 0,
            "bot_messages": 0,
        }


def get_daily_conversation_counts(
    days: int = 7,
    date_start: datetime | None = None,
    date_end: datetime | None = None,
):
    """
    Retorna contagem de conversas por dia.
    
    - Se date_start e date_end forem fornecidos, usa o intervalo [date_start, date_end].
    - Caso contrário, usa os últimos 'days' dias (comportamento padrão atual).
    """
    try:
        if date_start and date_end:
            start = date_start
            end = date_end
        else:
            today = datetime.utcnow()
            start = today - timedelta(days=days)
            end = None  # sem limite superior explícito (mantém comportamento antigo)

        query = _db.collection("conversations").where("created_at", ">=", start)
        if end:
            query = query.where("created_at", "<=", end)

        convs = query.stream()

        stats: dict[str, int] = {}
        for doc in convs:
            data = doc.to_dict() or {}
            ts = data.get("created_at")
            if not ts:
                continue

            d = ts.date().isoformat() if hasattr(ts, "date") else str(ts)
            stats[d] = stats.get(d, 0) + 1

        return stats
    except Exception as e:
        logger.error(f"[Firestore] Erro em daily_conversation_counts: {e}")
        return {}


def get_recent_conversations(limit=10):
    try:
        convs = (
            _db.collection("conversations")
               .order_by("updated_at", direction=firestore.Query.DESCENDING)
               .limit(limit)
               .stream()
        )

        results = []
        for c in convs:
            d = c.to_dict()
            results.append({
                "session_id": d.get("session_id"),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
                "total_user_messages": d.get("total_user_messages", 0),
                "total_bot_messages": d.get("total_bot_messages", 0),
            })

        return results
    except Exception as e:
        logger.error(f"[Firestore] Erro em recent_conversations: {e}")
        return []


def get_all_conversations(limit=50, filters=None):
    """
    Busca conversas com filtros opcionais.
    
    Args:
        limit: Número máximo de resultados (padrão: 50)
        filters: Dict opcional com filtros {
            "search": str  # Busca por session_id (filtro em memória)
        }
    
    Returns:
        Lista de dicionários com dados das conversas
    """
    # Garantir que filters seja um dict (ou vazio)
    filters = filters or {}
    search = (filters.get("search") or "").strip().lower()
    
    try:
        # Query Firestore mantida como está (ordenada por updated_at DESC e com limit)
        convs_query = (
            _db.collection("conversations")
               .order_by("updated_at", direction=firestore.Query.DESCENDING)
               .limit(limit)
        )
        
        convs = convs_query.stream()
        
        # Serializar documentos
        results = []
        for c in convs:
            d = c.to_dict()
            results.append({
                "session_id": d.get("session_id"),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
                "total_user_messages": d.get("total_user_messages", 0),
                "total_bot_messages": d.get("total_bot_messages", 0),
                "channel": d.get("channel"),
                "status": d.get("status"),
            })
        
        # Aplicar filtro de busca em memória (se fornecido)
        if search:
            filtered = []
            for conv in results:
                session_id = str(conv.get("session_id", "")).lower()
                if search in session_id:
                    filtered.append(conv)
            results = filtered
        
        return results
    except Exception as e:
        logger.error(f"[Firestore] Erro em get_all_conversations: {e}")
        return []


def get_conversation_messages(session_id, limit=200):
    try:
        msgs = (
            _db.collection("conversations").document(session_id)
               .collection("messages")
               .order_by("created_at", direction=firestore.Query.ASCENDING)
               .limit(limit)
               .stream()
        )

        results = []
        for m in msgs:
            data = m.to_dict()
            role_raw = data.get("role") or data.get("papel")
            normalized_role = role_raw
            if role_raw == "assistant":
                normalized_role = "bot"
            elif role_raw == "user":
                normalized_role = "user"
            elif role_raw == "bot":
                normalized_role = "bot"

            content = data.get("content") or data.get("texto")
            created = data.get("created_at") or data.get("criadoEm")

            results.append({
                "role": normalized_role,
                "content": content,
                "created_at": created,
            })

        return results
    except Exception as e:
        logger.error(f"[Firestore] Erro em get_conversation_messages({session_id}): {e}")
        return []


def sanitize_and_map_city(city_input: str) -> str:
    """
    Sanitiza e mapeia cidade para versão normalizada (sem acentos, lowercase).
    Usado para comparação interna, mas sempre retorna o nome oficial da lista.
    
    Args:
        city_input: Nome da cidade (pode ter acentos, cedilha, etc.)
    
    Returns:
        String normalizada (lowercase, sem acentos) para comparação
    """
    def strip_accents(s: str) -> str:
        """Remove acentos e diacríticos, incluindo cedilha."""
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    
    if not city_input:
        return ""
    
    # Limpeza inicial
    text = city_input.strip().lower()
    
    # Remove prefixos comuns
    prefixes = [
        "eu sou de", "eu moro em", "eu falo de", "sou de", "moro em",
        "falo de", "sou", "moro", "falo", "cidade de", "município de",
        "cidade", "município"
    ]
    
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    # Remove estado após vírgula ou hífen
    if "," in text:
        text = text.split(",")[0].strip()
    if "-" in text and not text.startswith("são"):  # Preserva "São" no início
        # Só remove hífen se não for parte do nome (ex: "São Bento do Sul")
        parts = text.split("-")
        if len(parts) > 1 and len(parts[-1]) <= 3:  # Provavelmente estado (SC, SP, etc)
            text = "-".join(parts[:-1]).strip()
    
    # Remove espaços extras
    text = " ".join(text.split())
    text = text.strip()
    
    # Remove acentos e diacríticos (incluindo cedilha)
    text_normalized = strip_accents(text)
    
    return text_normalized


def normalize_city_name(city: str) -> str | None:
    """
    Normaliza o nome da cidade removendo prefixos comuns, estados e validando.
    - Se for cidade de SC: retorna nome oficial da lista (ex: "Palhoça" com cedilha)
    - Se não for de SC: retorna None (para aceitar como texto livre e não travar o fluxo)
    Usa matching aproximado para reconhecer variações e erros de digitação.
    Garante que dados antigos como "Palhoca" (sem cedilha) retornem "Palhoça" (com cedilha).
    """
    # Retorna None se vazio, None ou só espaços
    if not city or not str(city).strip():
        return None

    def strip_accents(s: str) -> str:
        """Remove acentos e diacríticos, incluindo cedilha."""
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

    # Sinônimos conhecidos (apenas para SC)
    synonyms = {
        "floripa": "Florianópolis",
        "itajai": "Itajaí",
        "itaja": "Itajaí",
        "gv": "Gaspar",  # comum em SC
    }

    # Limpeza inicial: converte para lowercase e remove espaços
    text = city.strip().lower()
    
    if not text:
        return None
    
    # CRÍTICO: Criar versão auxiliar original ANTES de qualquer limpeza
    # Esta versão será usada para matching reverso antes de remover vírgulas
    text_clean_original = text.strip()
    text_original_no_accents = strip_accents(text_clean_original)
    
    # Normaliza lista de cidades de SC (cria tuplas: (nome_oficial, nome_sem_acentos))
    cidades_norm = [(c, strip_accents(c.lower())) for c in CIDADES_SANTA_CATARINA]
    
    # Normaliza lista de cidades de SC (cria tuplas: (nome_oficial, nome_sem_acentos))
    # Criado aqui para uso no matching reverso com texto original
    cidades_norm_original = [(c, strip_accents(c.lower())) for c in CIDADES_SANTA_CATARINA]
    
    # MATCHING REVERSO COM TEXTO ORIGINAL (ANTES DE QUALQUER LIMPEZA)
    # Isso garante que "rua x, palhoca" seja reconhecido antes de remover a vírgula
    # CORREÇÃO: Verifica se a cidade aparece como palavra isolada para evitar falsos positivos
    # Exemplo: "itajaí" não deve matchar com "itá" dentro de "itajaí"
    # CORREÇÃO: Rejeita cidades muito curtas (< 4 chars) no matching reverso também
    for original, norm in cidades_norm_original:
        # Pula cidades muito curtas no matching reverso (evita "ita" → "Itá")
        if len(norm) < 4:
            continue
        # Verifica se a cidade aparece como palavra isolada (com espaços ou no início/fim)
        if f" {norm} " in f" {text_original_no_accents} " or text_original_no_accents.startswith(f"{norm} ") or text_original_no_accents.endswith(f" {norm}"):
            return original  # Retorna nome OFICIAL imediatamente
    
    # Remove prefixos comuns no início da frase
    prefixes = [
        "eu sou de", "eu moro em", "eu falo de", "sou de", "moro em",
        "falo de", "sou", "moro", "falo", "cidade de", "município de",
        "cidade", "município"
    ]
    
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    # Corta tudo após vírgula ou hífen (geralmente estado)
    if "," in text:
        text = text.split(",")[0].strip()
    if "-" in text:
        # Só remove hífen se parecer ser estado (2-3 letras no final)
        parts = text.split("-")
        if len(parts) > 1 and len(parts[-1].strip()) <= 3:
            text = "-".join(parts[:-1]).strip()
    
    # Remove espaços extras e faz strip final
    text = " ".join(text.split())
    text = text.strip()
    
    # Validação: se ficou com menos de 2 caracteres, retorna None
    if len(text) < 2:
        return None
    
    # Limita a 50 caracteres
    if len(text) > 50:
        text = text[:50]
    
    # Verifica mapa de equivalências PRIMEIRO (para casos como "palhoca" -> "Palhoça")
    text_lower = text.lower()
    if text_lower in CITY_EQUIVALENCE_MAP:
        candidate = CITY_EQUIVALENCE_MAP[text_lower]
        if candidate in CIDADES_SANTA_CATARINA:
            return candidate
    
    # Remove acentos para comparação
    text_no_accents = strip_accents(text)

    # Verifica sinônimos
    if text in synonyms:
        candidate = synonyms[text]
        if candidate in CIDADES_SANTA_CATARINA:
            return candidate

    # Normaliza lista de cidades de SC (cria tuplas: (nome_oficial, nome_sem_acentos))
    cidades_norm = [(c, strip_accents(c.lower())) for c in CIDADES_SANTA_CATARINA]

    # CORREÇÃO: Para entradas muito curtas (< 4 caracteres), verifica match exato com nome oficial
    # Isso permite "Itá" (nome oficial) mas rejeita "ita" (sem acento, pode ser erro)
    if len(text_no_accents) < 4:
        # Verifica se o texto original (com acentos) matcha exatamente com alguma cidade oficial
        text_original_lower = city.strip().lower() if city else ""
        for cidade_oficial in CIDADES_SANTA_CATARINA:
            if cidade_oficial.lower() == text_original_lower:
                return cidade_oficial  # Match exato com nome oficial, permite
        # Se não matchou com nome oficial, rejeita (pode ser erro de digitação)
        return None

    # 1. Igualdade exata (mais preciso) - compara versões sem acentos
    for original, norm in cidades_norm:
        if norm == text_no_accents:
            return original  # Retorna nome OFICIAL (com acentos/cedilha)

    # 2. Texto contido na cidade normalizada (mas só se for match significativo)
    # Evita falsos positivos como "curitiba" -> "curitibanos"
    for original, norm in cidades_norm:
        if text_no_accents in norm:
            # Só aceita se:
            # - O texto for pelo menos 70% do tamanho da cidade, OU
            # - For match exato de substring no início da cidade, OU
            # - For match exato no final da cidade (para casos como "são josé")
            if (len(text_no_accents) >= len(norm) * 0.7 or 
                norm.startswith(text_no_accents) or 
                norm.endswith(text_no_accents)):
                return original  # Retorna nome OFICIAL

    # 3. MATCH REVERSO APÓS LIMPEZA: cidade oficial dentro do texto informado
    # Aceita qualquer posição (início, meio ou fim)
    # Exemplo: "centro de palhoca" → reconhece "palhoca" → retorna "Palhoça"
    # CORREÇÃO: Verifica se a cidade aparece como palavra isolada para evitar falsos positivos
    # CORREÇÃO: Rejeita cidades muito curtas (< 4 chars) no matching reverso também
    for original, norm in cidades_norm:
        # Pula cidades muito curtas no matching reverso (evita "ita" → "Itá")
        if len(norm) < 4:
            continue
        # Verifica se a cidade aparece como palavra isolada (com espaços ou no início/fim)
        if f" {norm} " in f" {text_no_accents} " or text_no_accents.startswith(f"{norm} ") or text_no_accents.endswith(f" {norm}"):
            return original  # Retorna nome OFICIAL

    # 4. Matching aproximado com difflib
    choices = [norm for _, norm in cidades_norm]
    match = difflib.get_close_matches(text_no_accents, choices, n=1, cutoff=0.8)
    if match:
        for original, norm in cidades_norm:
            if norm == match[0]:
                return original  # Retorna nome OFICIAL

    # 5. MATCH POR TOKENS — capturar qualquer token parecido com a cidade
    # CORREÇÃO: Aumentado limite para 4 letras e ratio para 0.80 para evitar falsos positivos
    # Exemplo: "itá" não deve matchar com "itajaí" (ratio ~0.50, mas token muito curto)
    tokens = [t for t in text_no_accents.replace('-', ' ').replace(',', ' ').split() if len(t) >= 4]
    for token in tokens:
        for original, norm in cidades_norm:
            ratio = difflib.SequenceMatcher(None, token, norm).ratio()
            # Requer token com pelo menos 4 caracteres E ratio >= 0.80
            if len(token) >= 4 and ratio >= 0.80:
                return original  # Retorna nome OFICIAL

    # Não é cidade de SC reconhecida - retorna None
    # (será aceita como texto livre em normalize_lead_answer)
    return None


def save_lead_from_conversation(session_id: str, lead_data: dict):
    """
    Salva um lead completo na coleção 'leads', a partir dos dados de uma conversa.
    Espera que lead_data contenha: nome, cidade, estado, idade, email, interesse.
    """
    if not _is_enabled() or _db is None:
        return False

    if not lead_data:
        return False

    try:
        # Normaliza cidade: tenta usar normalize_city_name para SC, senão mantém texto original
        raw_city = lead_data.get("cidade") or ""
        normalized_city = normalize_city_name(raw_city)
        # Se normalizou como cidade de SC, usa a normalizada; senão, mantém o texto original
        if normalized_city:
            cidade_final = normalized_city
        elif raw_city and str(raw_city).strip():
            cidade_final = str(raw_city).strip()[:100]
        else:
            # Garantir que nunca salve "" ou None
            cidade_final = "Outras cidades do Brasil"
        
        doc = {
            "session_id": session_id,
            "nome": (lead_data.get("nome") or "").strip(),
            "email": (lead_data.get("email") or "").strip(),
            "cidade": cidade_final,
            "estado": (lead_data.get("estado") or "").strip().upper(),
            "idade": lead_data.get("idade"),
            "interesse": (lead_data.get("interesse") or "").strip(),
            "createdAt": firestore.SERVER_TIMESTAMP,
        }

        # remove campos completamente vazios
        doc = {k: v for k, v in doc.items() if v not in (None, "", {})}

        _db.collection("leads").add(doc)
        logger.info(f"[Firestore] Lead salvo a partir da conversa {session_id}")
        return True
    except Exception as e:
        logger.error(f"[Firestore] Erro em save_lead_from_conversation({session_id}): {e}")
        return False


def get_leads_count_by_city():
    """
    Conta leads agrupados por cidade.
    Cidades de SC são normalizadas e agrupadas individualmente.
    Cidades de outros estados ou não reconhecidas são agrupadas como "Outras cidades do Brasil".
    Garante que dados antigos como "Palhoca" (sem cedilha) sejam normalizados para "Palhoça" (com cedilha).
    Retorna dict { "cidade": count, ... } onde as chaves são sempre os nomes oficiais da lista.
    """
    if not _is_enabled() or _db is None:
        return {}
    
    try:
        leads = _db.collection("leads").stream()
        
        counts = {}
        for lead_doc in leads:
            data = lead_doc.to_dict()
            cidade_bruta = data.get("cidade")
            
            # Tratar cidade vazia, None ou espaços
            if not cidade_bruta or not str(cidade_bruta).strip():
                counts["Outras cidades do Brasil"] = counts.get("Outras cidades do Brasil", 0) + 1
                continue
            
            # Tenta normalizar como cidade de SC
            # normalize_city_name sempre retorna o nome OFICIAL da lista (com acentos/cedilha)
            cidade_normalizada = normalize_city_name(cidade_bruta)
            
            # Proteção extra: tentar normalizar novamente após limpeza profunda
            if not cidade_normalizada:
                # Remove acentos e converte para lowercase para tentar novamente
                def strip_accents_helper(s: str) -> str:
                    """Remove acentos e diacríticos, incluindo cedilha."""
                    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
                
                cidade_limpa = strip_accents_helper(str(cidade_bruta).lower())
                cidade_normalizada = normalize_city_name(cidade_limpa)
            
            # Log temporário para debug (remover depois)
            if cidade_normalizada is None:
                logger.debug(f"[DEBUG][Cidade não reconhecida]: '{cidade_bruta}'")
            
            # Se normalizou e está na lista de cidades de SC, agrupa individualmente
            # cidade_normalizada já é o nome oficial (ex: "Palhoça" com cedilha)
            if cidade_normalizada and cidade_normalizada in CIDADES_SANTA_CATARINA:
                # Usa o nome oficial como chave (garante consistência no gráfico)
                counts[cidade_normalizada] = counts.get(cidade_normalizada, 0) + 1
            else:
                # Não é cidade de SC ou não foi reconhecida - agrupa como "Outras cidades do Brasil"
                counts["Outras cidades do Brasil"] = counts.get("Outras cidades do Brasil", 0) + 1
        
        # Segurança final: remover chaves vazias
        if "" in counts:
            counts["Outras cidades do Brasil"] = counts.get("Outras cidades do Brasil", 0) + counts[""]
            del counts[""]
        
        return counts
    except Exception as e:
        logger.error(f"[Firestore] Erro em get_leads_count_by_city: {e}")
        return {}


def get_leads_count_by_state():
    """
    Conta leads agrupados por estado (UF).
    Retorna dict { "SC": count, "PR": count, ... }.
    """
    if not _is_enabled() or _db is None:
        return {}

    try:
        leads = _db.collection("leads").stream()
        counts: dict[str, int] = {}

        for lead_doc in leads:
            data = lead_doc.to_dict() or {}
            estado = (data.get("estado") or "").strip().upper()

            # Considera só UF com 2 letras
            if len(estado) != 2:
                continue

            counts[estado] = counts.get(estado, 0) + 1

        return counts
    except Exception as e:
        logger.error(f"[Firestore] Erro em get_leads_count_by_state: {e}")
        return {}


def get_leads_count_by_age_range():
    """
    Conta leads agrupados por faixa etária.
    Retorna dict { "16-18": count, "19-24": count, "25+": count }.
    """
    if not _is_enabled() or _db is None:
        return {}

    try:
        leads = _db.collection("leads").stream()
        counts: dict[str, int] = {}

        for lead_doc in leads:
            data = lead_doc.to_dict() or {}
            idade_raw = data.get("idade")

            # Tenta converter idade para int
            try:
                if isinstance(idade_raw, str):
                    idade = int(idade_raw.strip())
                elif isinstance(idade_raw, int):
                    idade = idade_raw
                else:
                    continue
            except (ValueError, AttributeError):
                # Se não conseguir converter, ignora esse lead
                continue

            # Define faixa etária
            bucket = None
            if 16 <= idade <= 18:
                bucket = "16-18"
            elif 19 <= idade <= 24:
                bucket = "19-24"
            elif idade >= 25:
                bucket = "25+"
            # Idades abaixo de 16 são ignoradas

            if bucket:
                counts[bucket] = counts.get(bucket, 0) + 1

        return counts
    except Exception as e:
        logger.error(f"[Firestore] Erro em get_leads_count_by_age_range: {e}")
        return {}


# ===== HELPERS DE SETTINGS =====

def get_settings(doc_id: str = "global") -> dict:
    """
    Lê as configurações da collection 'settings', doc <doc_id>.
    Se não existir ou Firestore estiver desabilitado, retorna {}.
    """
    if not _is_enabled() or _db is None:
        return {}
    
    try:
        doc_ref = _db.collection("settings").document(doc_id)
        snap = doc_ref.get()
        if not snap.exists:
            return {}
        data = snap.to_dict() or {}
        return data
    except Exception as e:
        logger.error(f"[Firestore] Erro em get_settings({doc_id}): {e}")
        return {}


def update_settings(doc_id: str, data: dict) -> bool:
    """
    Faz merge das configurações em 'settings/<doc_id>'.
    Não levanta exceção; retorna True/False.
    """
    if not _is_enabled() or _db is None:
        return False
    
    try:
        doc_ref = _db.collection("settings").document(doc_id)
        doc_ref.set(data, merge=True)
        logger.debug(f"[Firestore] Settings {doc_id} atualizado")
        return True
    except Exception as e:
        logger.error(f"[Firestore] Erro em update_settings({doc_id}): {e}")
        return False


# ===== HELPERS PARA ADMIN USER =====

def get_admin_user(username: str) -> dict | None:
    """
    Retorna o documento do admin_user em admin_users/{username}.
    Se não existir ou Firestore estiver desabilitado, retorna None.
    """
    if not _is_enabled() or _db is None:
        return None
    
    try:
        doc_ref = _db.collection("admin_users").document(username)
        snap = doc_ref.get()
        if not snap.exists:
            return None
        return snap.to_dict() or None
    except Exception as e:
        logger.error(f"[Firestore] Erro em get_admin_user({username}): {e}")
        return None


def create_admin_user_if_missing(username: str, raw_password: str) -> None:
    """
    Se não existir o admin_user <username>, cria com a senha hash.
    Use para bootstrap inicial (ex.: admin / admin123).
    """
    logger.info(f"[DEBUG] create_admin_user_if_missing chamado para '{username}'")
    
    if not _is_enabled() or _db is None:
        logger.warning(f"[DEBUG] Firestore não habilitado ou _db é None. Não é possível criar admin '{username}'")
        return
    
    try:
        logger.info(f"[DEBUG] Verificando se admin '{username}' já existe...")
        existing = get_admin_user(username)
        if existing:
            logger.info(f"[Firestore] Admin user '{username}' já existe. Não será criado novamente.")
            return
        
        logger.info(f"[DEBUG] Admin '{username}' não existe. Criando novo admin...")
        doc_ref = _db.collection("admin_users").document(username)
        password_hash = generate_password_hash(raw_password)
        logger.info(f"[DEBUG] Hash da senha gerado: {password_hash[:20]}...")
        
        doc_ref.set({
            "username": username,
            "password_hash": password_hash,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
        logger.info(f"[Firestore] Admin user '{username}' criado com sucesso na collection 'admin_users'")
        
        # Verificar se foi criado
        verify_doc = doc_ref.get()
        if verify_doc.exists:
            logger.info(f"[DEBUG] Confirmação: Documento admin_users/{username} existe no Firestore")
        else:
            logger.error(f"[DEBUG] ERRO: Documento admin_users/{username} NÃO foi criado!")
            
    except Exception as e:
        logger.error(f"[Firestore] Erro em create_admin_user_if_missing({username}): {e}", exc_info=True)


def update_admin_password(username: str, raw_password: str) -> bool:
    """
    Atualiza a senha do admin_user <username>.
    Retorna True se sucesso, False caso contrário.
    """
    if not _is_enabled() or _db is None:
        return False
    
    try:
        doc_ref = _db.collection("admin_users").document(username)
        if not doc_ref.get().exists:
            return False
        
        doc_ref.update({
            "password_hash": generate_password_hash(raw_password),
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
        logger.info(f"[Firestore] Senha do admin '{username}' atualizada")
        return True
    except Exception as e:
        logger.error(f"[Firestore] Erro em update_admin_password({username}): {e}")
        return False


def verify_admin_password(username: str, raw_password: str) -> bool:
    """
    Verifica se a senha fornecida corresponde ao hash armazenado.
    - Se Firestore estiver DESABILITADO, usa fallback local: admin / admin123
    - Se Firestore estiver HABILITADO, verifica no banco normalmente.
    """

    # 🔹 Fallback quando Firestore está desabilitado
    if not _is_enabled() or _db is None:
        logger.debug("[AdminAuth] Firestore desabilitado, usando fallback local de login.")
        return username == "admin" and raw_password == "admin123"

    # 🔹 Fluxo normal com Firestore habilitado
    user = get_admin_user(username)
    if not user:
        return False

    pwd_hash = user.get("password_hash")
    if not pwd_hash:
        return False

    try:
        return check_password_hash(pwd_hash, raw_password)
    except Exception as e:
        logger.error(f"[Firestore] Erro em verify_admin_password({username}): {e}")
        return False


def init_default_admin():
    """
    Inicializa o admin padrão se não existir.
    Deve ser chamado após init_admin() e após todas as funções estarem definidas.
    """
    logger.info("[DEBUG] Chamando init_default_admin()")
    logger.info(f"[DEBUG] _is_enabled() = {_is_enabled()}")
    logger.info(f"[DEBUG] _db is None = {_db is None}")
    
    if not _is_enabled():
        logger.warning("[DEBUG] Firestore não está habilitado (AI_FIRESTORE_ENABLED=false). Admin não será criado.")
        return
    
    if _db is None:
        logger.warning("[DEBUG] _db é None. Firestore não foi inicializado corretamente.")
        return
    
    try:
        logger.info("[DEBUG] Criando admin padrão admin/admin123")
        create_admin_user_if_missing("admin", "admin123")
        logger.info("[DEBUG] init_default_admin() concluído com sucesso")
    except Exception as e:
        logger.error(f"[Firestore] Erro ao criar admin padrão: {e}", exc_info=True)

