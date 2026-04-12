"""
voice_stream.py — Socket.IO WebSocket handler for real-time voice interaction.

Namespace: /voice

Events (client → server):
  join_voice_session    — Join or create a voice session room
  audio_chunk           — Binary audio chunk (base64 encoded WebM/MP4)
  end_voice_session     — Signal end of session; triggers final summary
  ambient_consent       — Record patient consent for ambient listening

Events (server → client):
  voice_session_joined  — Session joined, ready for audio
  voice_response        — Full response: transcript + spoken_text + audio_b64
  voice_transcript      — Partial transcript (real-time streaming placeholder)
  ambient_update        — Accumulated SOAP note update (doctor ambient mode)
  voice_error           — Error with detail
  session_ended         — Session closure confirmation

Binary audio pipeline (per chunk):
  client (MediaRecorder → base64)
    → socket "audio_chunk" event
      → decode base64 → raw audio bytes
        → VoiceAgent.invoke()
          → Whisper STT → language detect → NER → GPT response → TTS
            → "voice_response" event (transcript + spoken text + mp3 b64)
              → client plays audio
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import datetime, timezone

from app.websocket import socketio

logger = logging.getLogger(__name__)

# sid → { user_id, session_id, session_mode, patient_id }
_voice_sessions: dict[str, dict] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on("connect", namespace="/voice")
def handle_voice_connect(auth):
    """Authenticate voice WebSocket connection."""
    from app.services.auth_service import AuthService

    if not auth or "token" not in auth:
        logger.warning("VoiceWS: connection refused — no token")
        return False

    try:
        token = auth["token"]
        if token.startswith("Bearer "):
            token = token[7:]

        decoded = AuthService.decode_token(token)
        if isinstance(decoded, str):
            raise ValueError(decoded)
        user_id = decoded.get("sub")
        role = decoded.get("role", "patient")

        if not user_id:
            return False

        from flask import request
        _voice_sessions[request.sid] = {
            "user_id": user_id,
            "role": role,
            "session_id": None,
            "session_mode": "patient",
            "patient_id": None,
        }

        logger.info("VoiceWS: user %s (%s) connected SID=%s", user_id, role, request.sid)
        return True

    except Exception as exc:
        logger.warning("VoiceWS: auth failed: %s", exc)
        return False


@socketio.on("disconnect", namespace="/voice")
def handle_voice_disconnect():
    from flask import request
    session = _voice_sessions.pop(request.sid, {})
    logger.info(
        "VoiceWS: disconnected SID=%s user=%s session=%s",
        request.sid, session.get("user_id"), session.get("session_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Session management
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on("join_voice_session", namespace="/voice")
def handle_join_voice_session(data):
    """
    Join or create a voice session.

    Data:
        session_id   (str, optional)  — resume existing; new UUID created if absent
        session_mode (str)            — "patient" | "ambient"
        patient_id   (str, optional)  — for ambient mode (doctor listening to patient)
        language     (str, optional)  — ISO 639-1 language hint
    """
    from flask import request
    from flask_socketio import join_room, emit

    session_meta = _voice_sessions.get(request.sid)
    if not session_meta:
        emit("voice_error", {"detail": "Not authenticated"})
        return

    session_id = data.get("session_id") or str(uuid.uuid4())
    session_mode = data.get("session_mode", "patient")
    patient_id = data.get("patient_id") or session_meta["user_id"]

    # Ambient mode: only doctors can start
    if session_mode == "ambient" and session_meta["role"] not in ("doctor", "admin"):
        emit("voice_error", {"detail": "Ambient mode requires doctor role"})
        return

    session_meta["session_id"] = session_id
    session_meta["session_mode"] = session_mode
    session_meta["patient_id"] = patient_id
    session_meta["language_hint"] = data.get("language")

    join_room(f"voice:{session_id}")

    logger.info(
        "VoiceWS: session %s joined (mode=%s patient=%s)",
        session_id, session_mode, patient_id,
    )

    emit("voice_session_joined", {
        "session_id": session_id,
        "session_mode": session_mode,
        "patient_id": patient_id,
        "language_hint": data.get("language"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Audio chunk processing
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on("audio_chunk", namespace="/voice")
def handle_audio_chunk(data):
    """
    Process an incoming audio chunk.

    Data:
        audio_b64    (str) — base64-encoded audio bytes
        format       (str) — "webm" | "mp4" | "wav" | "ogg"
        chunk_id     (int) — sequential chunk index (for ordering)
        final        (bool)— True if this is the last chunk in an utterance

    Response emits:
        voice_response — when processing is complete
        voice_error    — on failure
    """
    from flask import request
    from flask_socketio import emit

    session_meta = _voice_sessions.get(request.sid)
    if not session_meta or not session_meta.get("session_id"):
        emit("voice_error", {"detail": "No active voice session. Call join_voice_session first."})
        return

    audio_b64 = data.get("audio_b64", "")
    audio_format = data.get("format", "webm")
    is_final = data.get("final", True)

    if not audio_b64:
        emit("voice_error", {"detail": "audio_b64 is required"})
        return

    # Decode base64 audio
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as exc:
        emit("voice_error", {"detail": f"Invalid base64 audio data: {exc}"})
        return

    # Minimum chunk size check (< 1KB is likely silence)
    if len(audio_bytes) < 1024:
        logger.debug("VoiceWS: very small chunk (%d bytes) — skipping", len(audio_bytes))
        return

    session_id = session_meta["session_id"]
    patient_id = session_meta["patient_id"]
    session_mode = session_meta["session_mode"]
    language_hint = session_meta.get("language_hint")

    logger.info(
        "VoiceWS: audio_chunk %d bytes session=%s final=%s",
        len(audio_bytes), session_id, is_final,
    )

    # Only process on final chunk (complete utterance)
    if not is_final:
        emit("voice_transcript", {"status": "streaming", "session_id": session_id})
        return

    try:
        from app.agents.voice_agent import process_voice_turn
        from app.models.patient import PatientProfile

        # Load patient context if available
        patient_context = {}
        if patient_id:
            try:
                from app.models.db import db
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
            emit("voice_error", {"detail": "Voice processing returned no result"})
            return

        # For ambient mode, emit the SOAP note update
        if session_mode == "ambient":
            emit("ambient_update", {
                "session_id": session_id,
                "transcript": result.get("transcript", ""),
                "soap_segment": result.get("entities", []),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        else:
            # voice_response is emitted inside stream_audio_response node
            # but we also emit here as fallback if the room emit didn't fire
            if not result.get("audio_b64"):
                emit("voice_response", {
                    **result,
                    "note": "TTS unavailable — text response provided",
                })

        # Emergency: additionally emit a high-priority alert
        if result.get("is_emergency"):
            emit("voice_emergency", {
                "session_id": session_id,
                "patient_id": patient_id,
                "transcript": result.get("transcript", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, room="ward:all", namespace="/monitoring")

    except Exception as exc:
        logger.exception("VoiceWS: audio_chunk processing failed: %s", exc)
        emit("voice_error", {
            "detail": "Voice processing failed. Please try again.",
            "session_id": session_id,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Session end
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on("end_voice_session", namespace="/voice")
def handle_end_voice_session(data):
    """
    End the current voice session.
    For ambient mode, triggers final SOAP note consolidation.
    """
    from flask import request
    from flask_socketio import leave_room, emit

    session_meta = _voice_sessions.get(request.sid, {})
    session_id = session_meta.get("session_id") or data.get("session_id")
    session_mode = session_meta.get("session_mode", "patient")
    patient_id = session_meta.get("patient_id")

    if session_id:
        leave_room(f"voice:{session_id}")
        session_meta["session_id"] = None

    # Clean up Redis session
    if session_id:
        try:
            import redis as redis_lib, os
            r = redis_lib.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
            )
            # Don't delete — let TTL expire so history remains available briefly
            r.expire(f"vitalmind:voice:{session_id}", 300)  # 5 min grace
        except Exception:
            pass

    logger.info("VoiceWS: session %s ended (mode=%s)", session_id, session_mode)

    emit("session_ended", {
        "session_id": session_id,
        "session_mode": session_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Ambient consent
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on("ambient_consent", namespace="/voice")
def handle_ambient_consent(data):
    """
    Record explicit patient consent for ambient listening mode.
    REQUIRED before ambient mode can begin — compliance mandate.

    Data:
        session_id    (str)
        patient_id    (str)
        consent_given (bool)
    """
    from flask import request
    from flask_socketio import emit

    session_meta = _voice_sessions.get(request.sid, {})
    doctor_id = session_meta.get("user_id")

    session_id = data.get("session_id") or session_meta.get("session_id")
    patient_id = data.get("patient_id") or session_meta.get("patient_id")
    consent_given = bool(data.get("consent_given", False))

    if not session_id or not patient_id:
        emit("voice_error", {"detail": "session_id and patient_id required for consent logging"})
        return

    try:
        from app.agents.voice_agent import log_ambient_consent
        log_ambient_consent(
            patient_id=patient_id,
            doctor_id=doctor_id or "unknown",
            session_id=session_id,
            consent_given=consent_given,
        )
        emit("ambient_consent_logged", {
            "session_id": session_id,
            "consent_given": consent_given,
            "patient_id": patient_id,
        })
        logger.info(
            "VoiceWS: ambient consent logged session=%s patient=%s consent=%s",
            session_id, patient_id, consent_given,
        )
    except Exception as exc:
        logger.error("VoiceWS: consent logging failed: %s", exc)
        emit("voice_error", {"detail": "Consent logging failed"})
