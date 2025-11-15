from flask import Blueprint, render_template, jsonify, request, redirect, url_for, session
from services.firestore import (
    get_conversation_counts,
    get_message_counts_by_role,
    get_daily_conversation_counts,
    get_recent_conversations,
    get_all_conversations,
    get_conversation_messages,
    get_leads_count_by_city,
    get_leads_count_by_state,
    get_leads_count_by_age_range,
    get_settings,
    update_settings,
    verify_admin_password,
    update_admin_password,
    _is_enabled,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_SESSION_KEY = "admin_logged"


def _get_admin_theme():
    """Helper para carregar o tema do admin do Firestore."""
    global_cfg = get_settings("global") or {}
    return global_cfg.get("admin_theme", "dark")


@admin_bp.before_request
def require_admin_login():
    """Middleware de autenticação para rotas admin."""
    # Rotas públicas do admin (login e API de login)
    if request.endpoint in ("admin.login_page", "admin.api_login") or request.path == "/admin/login":
        return
    
    # Se for API e não autenticado, retorna 401 JSON
    if request.path.startswith("/admin/api/") and session.get(ADMIN_SESSION_KEY) != True:
        return jsonify({"error": "unauthorized"}), 401
    
    # Se não autenticado, redireciona para login
    if session.get(ADMIN_SESSION_KEY) != True:
        return redirect(url_for("admin.login_page"))


@admin_bp.get("/login")
def login_page():
    return render_template("admin/login.html")


@admin_bp.post("/api/login")
def api_login():
    """Endpoint de autenticação do admin."""
    import logging
    logger = logging.getLogger(__name__)
    
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    
    logger.info(f"[DEBUG] Tentativa de login: username='{username}'")
    
    if not username or not password:
        logger.warning(f"[DEBUG] Login falhou: campos vazios")
        return jsonify({"ok": False, "message": "Informe usuário e senha."}), 400
    
    if verify_admin_password(username, password):
        session[ADMIN_SESSION_KEY] = True
        session["admin_username"] = username
        logger.info(f"[DEBUG] Login bem-sucedido para '{username}'")
        return jsonify({"ok": True, "success": True})
    
    logger.warning(f"[DEBUG] Login falhou para '{username}': credenciais inválidas")
    return jsonify({"ok": False, "message": "Usuário ou senha inválidos."}), 401


@admin_bp.post("/logout")
def logout():
    """Logout do admin."""
    session.clear()
    return redirect(url_for("admin.login_page"))

@admin_bp.get("/")
def dashboard():
    """Dashboard principal do admin."""
    admin_theme = _get_admin_theme()
    return render_template("admin/dashboard.html", admin_theme=admin_theme)

@admin_bp.get("/api/reports")
def api_reports():
    data = {
        "conversation_counts": get_conversation_counts(),
        "message_counts": get_message_counts_by_role(),
        "daily_conversations": get_daily_conversation_counts(days=7),
        "recent_conversations": get_recent_conversations(limit=10),
        "leads_by_city": get_leads_count_by_city(),
        "leads_by_state": get_leads_count_by_state(),
        "leads_by_age_range": get_leads_count_by_age_range(),
    }
    return jsonify(data)

@admin_bp.get("/conversations")
def conversations_page():
    """Página de conversas do admin."""
    admin_theme = _get_admin_theme()
    return render_template("admin/conversations.html", admin_theme=admin_theme)

@admin_bp.get("/api/conversations")
def api_conversations():
    data = get_all_conversations(limit=50)
    return jsonify({"conversations": data})

@admin_bp.get("/api/conversations/<session_id>/messages")
def api_conversation_messages(session_id):
    msgs = get_conversation_messages(session_id, limit=200)
    return jsonify({"messages": msgs})


@admin_bp.get("/settings")
def settings_view():
    """Página de configurações do admin."""
    admin_theme = _get_admin_theme()
    chat_cfg = get_settings("chat_config") or {}
    
    return render_template(
        "admin/settings.html",
        admin_theme=admin_theme,
        chat_cfg=chat_cfg,
    )


@admin_bp.get("/api/settings")
def api_get_settings():
    """API para ler configurações."""
    global_cfg = get_settings("global") or {}
    chat_cfg = get_settings("chat_config") or {}
    return jsonify({
        "global": global_cfg,
        "chat": chat_cfg,
    })


@admin_bp.post("/api/settings")
def api_update_settings():
    """API para salvar configurações."""
    payload = request.get_json() or {}
    global_cfg = payload.get("global") or {}
    chat_cfg = payload.get("chat") or {}
    
    # Se não há nada pra salvar (nem global nem chat), apenas retorna ok
    if not global_cfg and not chat_cfg:
        return jsonify({"ok": True})
    
    # Verificar se o Firestore está desabilitado
    firestore_disabled = not _is_enabled()
    
    if firestore_disabled:
        # Não tenta salvar nada, apenas informa que não persistiu
        return jsonify({
            "ok": True,
            "firestore_disabled": True,
            "message": "Firestore desabilitado. Configurações não foram persistidas."
        }), 200
    
    # Fluxo normal quando Firestore está habilitado
    ok_global = True
    ok_chat = True
    
    if global_cfg:
        ok_global = update_settings("global", global_cfg)
    if chat_cfg:
        ok_chat = update_settings("chat_config", chat_cfg)
    
    if not (ok_global and ok_chat):
        return jsonify({"ok": False, "message": "Erro ao salvar configurações."}), 500
    
    return jsonify({"ok": True})


@admin_bp.post("/api/change-password")
def api_change_password():
    """API para trocar senha do admin."""
    data = request.get_json() or {}
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""
    confirm = data.get("confirm_password") or ""
    username = session.get("admin_username") or "admin"
    
    if not current or not new or not confirm:
        return jsonify({"ok": False, "message": "Preencha todos os campos."}), 400
    
    if new != confirm:
        return jsonify({"ok": False, "message": "Confirmação de senha não confere."}), 400
    
    if not verify_admin_password(username, current):
        return jsonify({"ok": False, "message": "Senha atual incorreta."}), 401
    
    if not update_admin_password(username, new):
        return jsonify({"ok": False, "message": "Erro ao atualizar senha."}), 500
    
    return jsonify({"ok": True, "message": "Senha atualizada com sucesso."})
