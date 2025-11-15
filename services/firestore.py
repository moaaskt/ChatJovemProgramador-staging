"""
Módulo de integração com Firestore para persistência de conversas.
Todas as funções retornam silenciosamente se AI_FIRESTORE_ENABLED=false.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from firebase_admin import initialize_app, credentials, firestore
from firebase_admin.exceptions import FirebaseError
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) 

# Flag global para verificar se Firestore está habilitado
_firestore_enabled = None
_db = None


def _is_enabled():
    """Verifica se Firestore está habilitado via variável de ambiente."""
    global _firestore_enabled
    if _firestore_enabled is None:
        _firestore_enabled = os.getenv("AI_FIRESTORE_ENABLED", "false").lower() == "true"
    return _firestore_enabled


def init_admin():
    """
    Inicializa Firebase Admin SDK usando FIREBASE_CREDENTIALS (JSON string).
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
        credentials_json = os.getenv("FIREBASE_CREDENTIALS")
        if not credentials_json:
            logger.warning("[Firestore] FIREBASE_CREDENTIALS não encontrado. Firestore desabilitado.")
            return
        
        # Parse do JSON string para dict
        cred_dict = json.loads(credentials_json)
        cred = credentials.Certificate(cred_dict)
        
        # Inicializa app (pode ser chamado múltiplas vezes, Firebase gerencia singleton)
        try:
            initialize_app(cred)
        except ValueError:
            # App já inicializado, tudo bem
            pass
        
        _db = firestore.client()
        logger.info("[Firestore] Inicializado com sucesso")
        logger.info(f"[Firestore] Projeto conectado: {_db.project}")
        
    except json.JSONDecodeError as e:
        logger.error(f"[Firestore] Erro ao parsear FIREBASE_CREDENTIALS: {e}")
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
        # Normaliza cidade: tenta usar normalize_city_name, com fallback para texto original
        raw_city = lead_data.get("cidade") or ""
        normalized_city = normalize_city_name(raw_city)
        cidade_final = normalized_city if normalized_city else (raw_city.strip()[:120] if raw_city.strip() else "")
        
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
    Retorna dict { "cidade": count, ... }
    """
    if not _is_enabled() or _db is None:
        return {}
    
    try:
        leads = _db.collection("leads").stream()
        
        counts = {}
        for lead_doc in leads:
            data = lead_doc.to_dict()
            cidade_bruta = data.get("cidade")
            
            # Se não houver cidade, agrupa como "Indefinido"
            if not cidade_bruta:
                counts["Indefinido"] = counts.get("Indefinido", 0) + 1
                continue
            
            # Normaliza a cidade usando normalize_city_name
            cidade_normalizada = normalize_city_name(cidade_bruta)
            
            # Se não conseguiu normalizar, agrupa como "Indefinido"
            if not cidade_normalizada:
                counts["Indefinido"] = counts.get("Indefinido", 0) + 1
            else:
                # Usa a cidade normalizada (já em Title Case) como chave
                counts[cidade_normalizada] = counts.get(cidade_normalizada, 0) + 1
        
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

