from flask import Blueprint, render_template, jsonify
from services.firestore import (
    get_conversation_counts,
    get_message_counts_by_role,
    get_daily_conversation_counts,
    get_recent_conversations,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

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
    }
    return jsonify(data)

