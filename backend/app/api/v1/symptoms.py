"""
symptoms.py — Symptoms API Blueprint (Step 9)

Endpoints
---------
POST /api/v1/symptoms/start
    Begin a new symptom interview session.

POST /api/v1/symptoms/<session_id>/respond
    Submit the next patient response in an ongoing symptom interview.

GET  /api/v1/symptoms/<session_id>/summary
    Get the complete interview summary and differential diagnosis (if finalized).
"""

import uuid
import logging

from flask import Blueprint, request, jsonify

from app.middleware.auth_middleware import require_auth
from app.agents.memory.context_manager import ContextManager

logger = logging.getLogger(__name__)

symptoms_bp = Blueprint("symptoms", __name__, url_prefix="/api/v1/symptoms")

# Lazy import to avoid circular imports at module load
def _get_agent():
    from app.agents.symptom_analyst import SymptomAnalystAgent
    return SymptomAnalystAgent(model="gemini-2.0-flash", temperature=0.2)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/symptoms/start
# ─────────────────────────────────────────────────────────────────────────────

@symptoms_bp.route("/start", methods=["POST"])
@require_auth
def start_session():
    """
    Start a new symptom interview session.

    Request JSON (optional)
    -----------------------
    {
        "initial_message": "I've had a headache for 3 days"  // optional opener
    }

    Response JSON
    -------------
    {
        "session_id": "uuid",
        "message": "...",      // AI's first question
        "phase": "initial_intake",
        "urgency": "routine"
    }
    """
    from langchain_core.messages import HumanMessage

    data = request.get_json(silent=True) or {}
    initial_message = (data.get("initial_message") or "").strip()

    patient = getattr(request, "current_user", None)
    patient_id = str(patient.id) if patient else None
    session_id = str(uuid.uuid4())

    try:
        agent = _get_agent()

        messages = []
        if initial_message:
            messages = [HumanMessage(content=initial_message)]

        initial_state = {
            "messages": messages,
            "patient_id": patient_id,
            "session_id": session_id,
            "intent": "symptom_check",
            "context": {"turn_count": 0},
            "tool_outputs": [],
            "final_response": None,
            "error": None,
        }

        result_state = agent.invoke(initial_state)
        final = result_state.get("final_response") or {}

        # Persist to Redis
        ctx = ContextManager(session_id)
        serialized_messages = []
        if initial_message:
            serialized_messages.append({"role": "user", "content": initial_message})
        ai_content = final.get("content", "")
        if ai_content:
            serialized_messages.append({"role": "assistant", "content": ai_content})

        ctx.save({
            "messages": serialized_messages,
            "context": result_state.get("context", {}),
            "intent": "symptom_check",
            "tool_outputs": result_state.get("tool_outputs", []),
        })

        return jsonify({
            "session_id": session_id,
            "message": final.get("content", ""),
            "phase": final.get("phase", "initial_intake"),
            "urgency": final.get("urgency", "routine"),
            "turn": final.get("turn", 1),
        }), 201

    except Exception as exc:
        logger.exception("start_session error: %s", exc)
        return jsonify({"error": "Failed to start symptom session", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/symptoms/<session_id>/respond
# ─────────────────────────────────────────────────────────────────────────────

@symptoms_bp.route("/<session_id>/respond", methods=["POST"])
@require_auth
def respond(session_id: str):
    """
    Submit a patient response in an ongoing symptom interview.

    Request JSON
    ------------
    {
        "message": "The pain is a 7 out of 10 and started suddenly"
    }

    Response JSON
    -------------
    {
        "session_id": "...",
        "message": "...",      // AI's next question or differential
        "phase": "followup_interview|differential_complete|emergency_triage",
        "urgency": "routine|urgent|emergency",
        "turn": 3,
        "differential": {...}  // only when phase == "differential_complete"
    }
    """
    from langchain_core.messages import HumanMessage, AIMessage

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "message field is required"}), 400

    patient = getattr(request, "current_user", None)
    patient_id = str(patient.id) if patient else None

    try:
        # Load existing session
        ctx_manager = ContextManager(session_id)
        session = ctx_manager.load()
        stored_messages = session.get("messages", [])
        context = session.get("context", {"turn_count": 0})

        # Rebuild LangChain message list
        lc_messages = []
        for m in stored_messages:
            if m["role"] == "user":
                lc_messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                lc_messages.append(AIMessage(content=m["content"]))
        lc_messages.append(HumanMessage(content=message))

        agent = _get_agent()
        result_state = agent.invoke({
            "messages": lc_messages,
            "patient_id": patient_id,
            "session_id": session_id,
            "intent": "symptom_check",
            "context": context,
            "tool_outputs": session.get("tool_outputs", []),
            "final_response": None,
            "error": None,
        })

        final = result_state.get("final_response") or {}

        # Persist updated session
        updated_msgs = stored_messages + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": final.get("content", "")},
        ]
        ctx_manager.save({
            "messages": updated_msgs,
            "context": result_state.get("context", {}),
            "intent": "symptom_check",
            "tool_outputs": result_state.get("tool_outputs", []),
        })

        response_body = {
            "session_id": session_id,
            "message": final.get("content", ""),
            "phase": final.get("phase", "followup_interview"),
            "urgency": final.get("urgency", "routine"),
            "turn": final.get("turn"),
        }

        # Include differential if diagnosis is complete
        if final.get("phase") == "differential_complete":
            response_body["differential"] = final.get("differential", {})
            response_body["specialist"] = final.get("specialist")

        return jsonify(response_body), 200

    except Exception as exc:
        logger.exception("respond error for session %s: %s", session_id, exc)
        return jsonify({"error": "Failed to process response", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/symptoms/<session_id>/summary
# ─────────────────────────────────────────────────────────────────────────────

@symptoms_bp.route("/<session_id>/summary", methods=["GET"])
@require_auth
def get_summary(session_id: str):
    """Return the conversation history and any stored differential for a session."""
    try:
        ctx_manager = ContextManager(session_id)
        session = ctx_manager.load()
        context = session.get("context", {})

        return jsonify({
            "session_id": session_id,
            "messages": session.get("messages", []),
            "differential": context.get("differential"),
            "urgency": context.get("urgency_result"),
            "recommended_specialist": context.get("recommended_specialist"),
            "turn_count": context.get("turn_count", 0),
        }), 200

    except Exception as exc:
        logger.error("get_summary error: %s", exc)
        return jsonify({"error": "Could not retrieve session summary"}), 500
