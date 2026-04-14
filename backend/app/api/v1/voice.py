"""
voice.py — VitalMind Voice Interaction API Blueprint (Step 18)

Endpoints
---------
POST /api/v1/voice/start-session
    Create (or resume) a voice interaction session.

POST /api/v1/voice/process
    REST-based audio processing endpoint.

POST /api/v1/voice/ai-doctor-conversation
    AI Doctor: accepts raw audio → Groq Whisper STT → SymptomAnalyst → ElevenLabs TTS
    Returns transcript + spoken_response + audio + symptom_summary.

GET  /api/v1/voice/session/<session_id>
GET  /api/v1/voice/sessions
DELETE /api/v1/voice/session/<session_id>/end
"""

import logging
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from app.middleware.auth_middleware import require_auth

logger = logging.getLogger(__name__)

voice_bp = Blueprint("voice", __name__, url_prefix="/api/v1/voice")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/voice/ai-doctor-conversation
# ─────────────────────────────────────────────────────────────────────────────

@voice_bp.route("/ai-doctor-conversation", methods=["POST"])
@require_auth
def ai_doctor_conversation():
    """
    AI Doctor: multipart audio upload → STT → SymptomAnalyst → TTS.

    Accepts multipart/form-data:
      audio     : audio file (webm, wav, mp4, ogg)
      session_id: string (required)
      language  : ISO 639-1 hint (optional, default 'en')

    Returns JSON:
      transcript, spoken_response, audio_b64, audio_format,
      language, entities, is_emergency, symptom_summary, session_id
    """
    current_user = getattr(request, "current_user", None)
    if not current_user:
        return jsonify({"error": "Unauthorized"}), 401

    # Accept both multipart (file upload) and JSON (base64)
    session_id = None
    language_hint = None
    audio_bytes = None
    audio_format = "webm"

    if request.content_type and "multipart" in request.content_type:
        audio_file = request.files.get("audio")
        session_id = request.form.get("session_id", "").strip()
        language_hint = request.form.get("language")
        audio_format = request.form.get("format", "webm")
        if not audio_file:
            return jsonify({"error": "audio file is required"}), 400
        audio_bytes = audio_file.read()
    else:
        data = request.get_json(silent=True) or {}
        session_id = (data.get("session_id") or "").strip()
        language_hint = data.get("language")
        audio_format = data.get("audio_format", "webm")
        audio_b64 = (data.get("audio_b64") or "").strip()
        if not audio_b64:
            return jsonify({"error": "audio_b64 or audio file is required"}), 400
        try:
            import base64 as _b64
            audio_bytes = _b64.b64decode(audio_b64)
        except Exception as exc:
            return jsonify({"error": f"Invalid base64 audio: {exc}"}), 400

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    if not audio_bytes or len(audio_bytes) < 512:
        return jsonify({"error": "Audio too short — minimum 512 bytes required"}), 400

    patient_id = str(current_user.id)

    # Load patient context
    patient_context = {}
    try:
        from app.models.patient import PatientProfile
        from app.models.medication import Prescription
        profile = PatientProfile.query.filter_by(user_id=patient_id).first()
        if profile:
            meds = Prescription.query.filter_by(patient_id=profile.id, status="active").all()
            allergies = [a.allergen for a in getattr(profile, "allergies", [])]
            conditions = [h.condition_name for h in getattr(profile, "medical_history", [])]
            patient_context = {
                "name": f"{profile.user.first_name} {profile.user.last_name}" if profile.user else "Patient",
                "chronic_conditions": conditions[:5],
                "current_medications": [p.medication.name if p.medication else "" for p in meds[:5]],
                "allergies": allergies[:5],
            }
    except Exception as e:
        logger.debug("AI Doctor: patient context load skipped: %s", e)

    try:
        from app.agents.voice_agent import process_voice_turn_with_symptom_analysis
        result = process_voice_turn_with_symptom_analysis(
            audio_data=audio_bytes,
            session_id=session_id,
            patient_id=patient_id,
            audio_format=audio_format,
            language_hint=language_hint,
            patient_context=patient_context,
        )
        return jsonify(result), 200

    except Exception as exc:
        logger.exception("AI Doctor: conversation endpoint failed: %s", exc)
        return jsonify({
            "error": "AI Doctor processing failed",
            "detail": str(exc),
            "spoken_response": "I'm having a moment of trouble. Please try speaking again.",
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/voice/warmup  (no auth — safe, returns no user data)
# ─────────────────────────────────────────────────────────────────────────────

@voice_bp.route("/warmup", methods=["GET"])
def warmup():
    """
    Pre-warm Gemini client and TTS singleton on Render's server.
    Call this on page load so the first real voice request is cold-start-free.
    No auth required — returns no patient data.
    """
    import os as _os
    status = {"gemini": "cold", "tts": "cold"}

    try:
        from app.agents.voice_agent import _get_tts_client
        tts = _get_tts_client()
        status["tts"] = "warm" if tts else "unavailable"
    except Exception:
        status["tts"] = "unavailable"

    try:
        from google import genai as _genai
        _genai.Client(api_key=_os.getenv("GOOGLE_API_KEY", ""))
        status["gemini"] = "warm"
    except Exception:
        status["gemini"] = "unavailable"

    logger.info("VoiceAPI: warmup called — %s", status)
    return jsonify({"status": "warm", "components": status}), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/voice/start-session
# ─────────────────────────────────────────────────────────────────────────────

@voice_bp.route("/start-session", methods=["POST"])
@require_auth
def start_session():
    """
    Create or resume a voice interaction session.

    Request JSON
    ------------
    {
        "session_mode":  "patient" | "ambient",   // default: "patient"
        "patient_id":    "<uuid>",                // required for ambient mode
        "language":      "en",                    // ISO 639-1 hint (optional)
        "resume_session_id": "<uuid>"             // optional: resume an existing session
    }

    Response JSON
    -------------
    {
        "session_id": "uuid",
        "session_mode": "patient",
        "ws_namespace": "/voice",
        "ws_events": {
            "send": ["join_voice_session", "audio_chunk", "end_voice_session", "ambient_consent"],
            "receive": ["voice_session_joined", "voice_response", "ambient_update", "voice_error"]
        },
        "tts_voices": ["nova", "alloy", "echo", "fable", "onyx", "shimmer"],
        "supported_audio_formats": ["webm", "mp4", "wav", "ogg"],
        "max_chunk_duration_ms": 5000,
        "created_at": "ISO8601"
    }
    """
    data = request.get_json(silent=True) or {}
    session_mode = data.get("session_mode", "patient")
    language_hint = data.get("language")
    resume_id = data.get("resume_session_id")

    current_user = getattr(request, "current_user", None)
    user_id = str(current_user.id) if current_user else None
    role = getattr(current_user, "role", "patient") if current_user else "patient"

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # Validate ambient mode (doctors only)
    if session_mode == "ambient" and role not in ("doctor", "admin"):
        return jsonify({"error": "Ambient listening mode requires doctor role"}), 403

    # For ambient mode, patient_id is required (the patient being listened to)
    patient_id = None
    if session_mode == "ambient":
        patient_id = data.get("patient_id")
        if not patient_id:
            return jsonify({"error": "patient_id is required for ambient mode"}), 400
    else:
        patient_id = user_id

    # Resume existing session or create new
    session_id = resume_id or str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # Persist session record to DB
    try:
        from app.models.db import db
        from sqlalchemy import text
        db.session.execute(
            text("""
                INSERT INTO voice_session_meta
                    (id, user_id, patient_id, session_mode, language_hint, status, created_at)
                VALUES (:id, :uid, :pid, :mode, :lang, 'active', :created_at)
                ON CONFLICT (id) DO UPDATE SET status = 'active'
            """),
            {
                "id": session_id,
                "uid": user_id,
                "pid": patient_id,
                "mode": session_mode,
                "lang": language_hint,
                "created_at": created_at,
            },
        )
        db.session.commit()
    except Exception as exc:
        logger.warning("VoiceAPI: session meta persist failed (non-fatal): %s", exc)
        try:
            from app.models.db import db
            db.session.rollback()
        except Exception:
            pass

    logger.info(
        "VoiceAPI: session started — id=%s mode=%s user=%s patient=%s",
        session_id, session_mode, user_id, patient_id,
    )

    return jsonify({
        "session_id": session_id,
        "session_mode": session_mode,
        "patient_id": patient_id,
        "language_hint": language_hint,
        "ws_namespace": "/voice",
        "ws_connect_url": "/socket.io",
        "ws_events": {
            "send": [
                "join_voice_session",
                "audio_chunk",
                "end_voice_session",
                "ambient_consent",
            ],
            "receive": [
                "voice_session_joined",
                "voice_response",
                "voice_transcript",
                "ambient_update",
                "voice_emergency",
                "session_ended",
                "voice_error",
            ],
        },
        "tts_voices": ["nova", "alloy", "echo", "fable", "onyx", "shimmer"],
        "supported_audio_formats": ["webm", "mp4", "wav", "ogg"],
        "max_chunk_duration_ms": 5000,
        "created_at": created_at,
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/voice/process
# ─────────────────────────────────────────────────────────────────────────────

@voice_bp.route("/process", methods=["POST"])
@require_auth
def process_audio():
    """
    REST-based audio processing (alternative to WebSocket).
    Best for single-shot audio uploads (e.g. after recording stops).

    Request JSON
    ------------
    {
        "session_id":    "<uuid>",
        "audio_b64":     "<base64-encoded audio bytes>",
        "audio_format":  "webm" | "mp4" | "wav" | "ogg",
        "session_mode":  "patient" | "ambient",
        "language":      "en"
    }

    Response JSON
    -------------
    {
        "session_id":       "uuid",
        "transcript":       "I have been having chest pain for two days",
        "spoken_response":  "I heard you're experiencing chest pain. How severe is it on a scale of 1 to 10?",
        "audio_b64":        "<base64 MP3>",
        "audio_format":     "mp3",
        "language":         "en",
        "intent":           "symptom_report",
        "entities":         [...],
        "is_emergency":     false,
        "route_action":     "route_to_symptom_check"
    }
    """
    data = request.get_json(silent=True) or {}

    session_id = (data.get("session_id") or "").strip()
    audio_b64 = (data.get("audio_b64") or "").strip()
    audio_format = data.get("audio_format", "webm")
    session_mode = data.get("session_mode", "patient")
    language_hint = data.get("language")

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    if not audio_b64:
        return jsonify({"error": "audio_b64 is required"}), 400

    current_user = getattr(request, "current_user", None)
    patient_id = str(current_user.id) if current_user else None

    # Decode base64 audio
    try:
        import base64 as b64_lib
        audio_bytes = b64_lib.b64decode(audio_b64)
    except Exception as exc:
        return jsonify({"error": f"Invalid base64 audio: {exc}"}), 400

    if len(audio_bytes) < 512:
        return jsonify({"error": "Audio too short — minimum 512 bytes required"}), 400

    try:
        from app.agents.voice_agent import process_voice_turn

        # Load patient context
        patient_context = {}
        if patient_id:
            try:
                from app.models.patient import PatientProfile
                profile = PatientProfile.query.filter_by(user_id=patient_id).first()
                if profile:
                    patient_context = {
                        "name": f"{profile.first_name} {profile.last_name}",
                        "age": getattr(profile, "age", None),
                        "chronic_conditions": getattr(profile, "chronic_conditions", []),
                        "current_medications": getattr(profile, "current_medications", []),
                        "allergies": getattr(profile, "allergies", []),
                    }
            except Exception:
                pass

        result = process_voice_turn(
            audio_data=audio_bytes,
            session_id=session_id,
            patient_id=patient_id,
            audio_format=audio_format,
            session_mode=session_mode,
            language_hint=language_hint,
            patient_context=patient_context,
        )

        if not result:
            return jsonify({"error": "Voice processing returned no result"}), 500

        status_code = 201 if result.get("is_emergency") else 200
        return jsonify(result), status_code

    except Exception as exc:
        logger.exception("VoiceAPI: REST process failed: %s", exc)
        return jsonify({
            "error": "Voice processing failed",
            "detail": str(exc),
            "spoken_response": (
                "I'm having trouble processing your voice right now. "
                "Please try again in a moment or use text chat if the issue persists."
            ),
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/voice/session/<session_id>
# ─────────────────────────────────────────────────────────────────────────────

@voice_bp.route("/session/<session_id>", methods=["GET"])
@require_auth
def get_session(session_id: str):
    """
    Retrieve session metadata + conversation history from Redis cache.

    Response JSON
    -------------
    {
        "session_id": "uuid",
        "session_mode": "patient",
        "turns": [
            { "role": "patient", "transcript": "...", "timestamp": "..." },
            { "role": "assistant", "transcript": "...", "timestamp": "..." }
        ],
        "turn_count": 4,
        "last_active": "ISO8601",
        "accumulated_soap": null
    }
    """
    try:
        import redis as redis_lib
        import os
        import json as json_lib

        r = redis_lib.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
        raw = r.get(f"vitalmind:voice:{session_id}")
        if not raw:
            return jsonify({"error": "Session not found or expired"}), 404

        session_data = json_lib.loads(raw)
        history = session_data.get("history", [])
        soap = session_data.get("accumulated_soap", {}) if session_data.get("session_mode") == "ambient" else None

        return jsonify({
            "session_id": session_id,
            "patient_id": session_data.get("patient_id"),
            "session_mode": session_data.get("session_mode", "patient"),
            "turns": history,
            "turn_count": len(history),
            "last_active": session_data.get("updated_at"),
            "accumulated_soap": soap,
        }), 200

    except Exception as exc:
        logger.error("VoiceAPI: get_session failed: %s", exc)
        return jsonify({"error": "Could not retrieve session"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/v1/voice/session/<session_id>/end
# ─────────────────────────────────────────────────────────────────────────────

@voice_bp.route("/session/<session_id>/end", methods=["DELETE"])
@require_auth
def end_session(session_id: str):
    """
    End a voice session. For ambient mode, returns the consolidated SOAP note.

    Response JSON
    -------------
    {
        "session_id": "uuid",
        "ended_at": "ISO8601",
        "turn_count": 6,
        "soap_note": { ... }   // only for ambient mode
    }
    """
    try:
        import redis as redis_lib
        import os, json as json_lib
        from app.models.db import db
        from sqlalchemy import text

        ended_at = datetime.now(timezone.utc).isoformat()

        r = redis_lib.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
        raw = r.get(f"vitalmind:voice:{session_id}")
        session_data = json_lib.loads(raw) if raw else {}

        history = session_data.get("history", [])
        session_mode = session_data.get("session_mode", "patient")
        patient_id = session_data.get("patient_id")
        
        # Mark session as ended in DB
        try:
            db.session.execute(
                text("""
                    UPDATE voice_session_meta
                    SET status = 'ended', ended_at = :ended_at
                    WHERE id = :id
                """),
                {"ended_at": ended_at, "id": session_id},
            )
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

        # If ambient, generate the final clinical note synchronously
        report_id = None
        if session_mode == "ambient" and history and patient_id:
            try:
                from app.services.clinical_note_service import ClinicalNoteService
                current_user = getattr(request, "current_user", None)
                doctor_id = str(current_user.id) if current_user and current_user.role in ("doctor", "admin") else None
                
                report_id = ClinicalNoteService.generate_note_from_voice_session(
                    session_id=session_id,
                    patient_id=patient_id,
                    history=history,
                    doctor_id=doctor_id
                )
            except Exception as e:
                logger.error("Failed to generate clinical note during session end: %s", e)

        # Let TTL expire naturally; but reduce to 60s to free memory
        try:
            r.expire(f"vitalmind:voice:{session_id}", 60)
        except Exception:
            pass

        logger.info("VoiceAPI: session %s ended (mode=%s turns=%d)", session_id, session_mode, len(history))

        return jsonify({
            "session_id": session_id,
            "session_mode": session_mode,
            "ended_at": ended_at,
            "turn_count": len(history),
            "generated_report_id": report_id
        }), 200

    except Exception as exc:
        logger.exception("VoiceAPI: end_session failed: %s", exc)
        return jsonify({"error": "Could not end session", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/voice/sessions
# ─────────────────────────────────────────────────────────────────────────────

@voice_bp.route("/sessions", methods=["GET"])
@require_auth
def list_sessions():
    """
    List recent voice sessions for the authenticated user.
    Doctors see sessions they participated in (ambient or started).

    Query params:
        limit       (int, default=20)
        mode        (str) — filter by session_mode
    """
    current_user = getattr(request, "current_user", None)
    user_id = str(current_user.id) if current_user else None
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    limit = min(50, int(request.args.get("limit", 20)))
    mode_filter = request.args.get("mode", "").strip()

    try:
        from app.models.db import db
        from sqlalchemy import text

        where = "WHERE user_id = :uid"
        params: dict = {"uid": user_id, "limit": limit}
        if mode_filter:
            where += " AND session_mode = :mode"
            params["mode"] = mode_filter

        rows = db.session.execute(
            text(f"""
                SELECT id, patient_id, session_mode, language_hint, status, created_at, ended_at
                FROM voice_session_meta
                {where}
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            params,
        ).fetchall()

        sessions = [dict(r._mapping) for r in rows]
        return jsonify({"sessions": sessions, "count": len(sessions)}), 200

    except Exception as exc:
        logger.error("VoiceAPI: list_sessions failed: %s", exc)
        return jsonify({"sessions": [], "count": 0}), 200
