"""
Módulo de integração com Firestore para persistência de conversas.
Todas as funções retornam silenciosamente se AI_FIRESTORE_ENABLED=false.
"""

import os
import json
import logging
from datetime import datetime
from firebase_admin import initialize_app, credentials, firestore
from firebase_admin.exceptions import FirebaseError

logger = logging.getLogger(__name__)

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
        now = datetime.utcnow()
        conv_ref = _db.collection("conversations").document(session_id)
        
        conv_data = {
            "session_id": session_id,
            "ultimaMensagemEm": now
        }
        
        # Se documento não existe, adiciona iniciadoEm
        if not conv_ref.get().exists:
            conv_data["iniciadoEm"] = now
        
        conv_ref.set(conv_data, merge=True)
        logger.debug(f"[Firestore] Conversa {session_id} atualizada")
        return True
        
    except Exception as e:
        logger.error(f"[Firestore] Erro ao salvar conversa {session_id}: {e}")
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
        now = datetime.utcnow()
        message_data = {
            "papel": role,
            "texto": text,
            "criadoEm": now
        }
        
        if meta:
            message_data["meta"] = meta
        
        messages_ref = _db.collection("conversations").document(session_id).collection("messages")
        messages_ref.add(message_data)
        
        logger.debug(f"[Firestore] Mensagem salva: {session_id}/{role}")
        return True
        
    except Exception as e:
        logger.error(f"[Firestore] Erro ao salvar mensagem {session_id}/{role}: {e}")
        return False

