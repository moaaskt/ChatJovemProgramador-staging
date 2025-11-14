from flask import Blueprint, render_template, jsonify
from services.firestore import (
    get_conversation_counts,
    get_message_counts_by_role,
    get_daily_conversation_counts,
    get_recent_conversations,
    get_all_conversations,
    get_conversation_messages,
    get_leads_count_by_city,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.get("/login")
def login_page():
    return render_template("admin/login.html")

@admin_bp.get("/")
def dashboard():
    return render_template("admin/dashboard.html")

@admin_bp.get("/api/reports")
def api_reports():
    data = {
        "conversation_counts": get_conversation_counts(),
        "message_counts": get_message_counts_by_role(),
        "daily_conversations": get_daily_conversation_counts(days=7),
        "recent_conversations": get_recent_conversations(limit=10),
        "leads_by_city": get_leads_count_by_city(),
    }
    return jsonify(data)

@admin_bp.get("/conversations")
def conversations_page():
    return render_template("admin/conversations.html")

@admin_bp.get("/api/conversations")
def api_conversations():
    data = get_all_conversations(limit=50)
    return jsonify({"conversations": data})

@admin_bp.get("/api/conversations/<session_id>/messages")
def api_conversation_messages(session_id):
    msgs = get_conversation_messages(session_id, limit=200)
    return jsonify({"messages": msgs})
