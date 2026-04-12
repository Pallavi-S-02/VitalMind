"""
chat.py — VitalMind Chat API Blueprint

Endpoints
---------
POST /api/v1/chat/message
    Send a patient message to the AI orchestrator.

POST /api/v1/chat/session/new
    Explicitly create a new chat session.

GET  /api/v1/chat/session/<session_id>/history
    Retrieve conversation history for a session.

DELETE /api/v1/chat/session/<session_id>
    Clear a session from Redis.
"""

import uuid
import logging

from flask import Blueprint, request, jsonify

from app.middleware.auth_middleware import require_auth
from app.agents.memory.context_manager import ContextManager
from app.services.agent_orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/v1/chat")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/chat/message
# ─────────────────────────────────────────────────────────────────────────────

@chat_bp.route("/message", methods=["POST"])
@require_auth
def send_message():
    """
    Send a message to the VitalMind AI Orchestrator.

    Request JSON
    ------------
    {
        "message"    : "I have chest pain and shortness of breath",
        "session_id" : "abc123"   // optional; omit to start a new session
    }

    Response JSON
    -------------
    {
        "response"   : "...",
        "intent"     : "triage",
        "urgency"    : "emergency",
        "session_id" : "abc123",
        "metadata"   : {}
    }
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "message field is required"}), 400

    patient = getattr(request, "current_user", None)
    patient_id = str(patient.id) if patient else None
    session_id = data.get("session_id")

    try:
        result = OrchestratorService.process_message(
            message=message,
            patient_id=patient_id,
            session_id=session_id,
        )
        return jsonify(result), 200

    except Exception as exc:
        logger.exception("Chat endpoint error: %s", exc)
        return jsonify({
            "error": "Internal server error",
            "detail": str(exc),
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/chat/session/new
# ─────────────────────────────────────────────────────────────────────────────

@chat_bp.route("/session/new", methods=["POST"])
@require_auth
def new_session():
    """Create and return a fresh session ID."""
    session_id = str(uuid.uuid4())
    return jsonify({"session_id": session_id}), 201


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/chat/session/<session_id>/history
# ─────────────────────────────────────────────────────────────────────────────

@chat_bp.route("/session/<session_id>/history", methods=["GET"])
@require_auth
def get_history(session_id: str):
    """
    Return the message history for a session.

    Response JSON
    -------------
    {
        "session_id" : "abc123",
        "messages"   : [{"role": "user", "content": "..."}, ...]
    }
    """
    try:
        ctx = ContextManager(session_id)
        messages = ctx.get_messages()
        return jsonify({"session_id": session_id, "messages": messages}), 200
    except Exception as exc:
        logger.error("get_history error: %s", exc)
        return jsonify({"error": "Could not retrieve session history"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/v1/chat/session/<session_id>
# ─────────────────────────────────────────────────────────────────────────────

@chat_bp.route("/session/<session_id>", methods=["DELETE"])
@require_auth
def clear_session(session_id: str):
    """Clear a chat session from Redis."""
    try:
        ctx = ContextManager(session_id)
        ctx.clear()
        return jsonify({"message": f"Session {session_id} cleared"}), 200
    except Exception as exc:
        logger.error("clear_session error: %s", exc)
        return jsonify({"error": "Could not clear session"}), 500
