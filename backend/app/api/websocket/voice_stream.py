import uuid
import base64
import logging
from datetime import datetime, timezone
from app.websocket import socketio

logger = logging.getLogger(__name__)

_voice_sessions = {}  # sid -> meta
_live_sessions = {}   # sid -> GeminiLiveSession

@socketio.on("connect", namespace="/voice")
def handle_voice_connect(auth):
    from flask import request
    from app.services.auth_service import AuthService
    
    sid = request.sid
    token = auth.get("token", "") if auth else ""
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = AuthService.decode_token(token)
        if isinstance(payload, str):
            raise Exception(payload)
        user_id = payload.get("sub")
        role = payload.get("role", "patient")

        _voice_sessions[sid] = {
            "user_id": user_id,
            "role": role,
        }

        logger.info("VoiceWS: user %s (%s) connected SID=%s", user_id, role, request.sid)
        return True

    except Exception as exc:
        logger.warning("VoiceWS: auth failed: %s", exc)
        raise ConnectionRefusedError(str(exc))

@socketio.on("disconnect", namespace="/voice")
def handle_voice_disconnect():
    from flask import request
    sid = request.sid

    # Clean up Live session
    live_session = _live_sessions.pop(sid, None)
    if live_session:
        live_session.close()

    session = _voice_sessions.pop(sid, {})
    logger.info(
        "VoiceWS: disconnected SID=%s user=%s session=%s",
        sid, session.get("user_id"), session.get("session_id"),
    )

@socketio.on("join_voice_session", namespace="/voice")
def handle_join_voice_session(data):
    from flask import request
    from flask_socketio import join_room, emit

    session_meta = _voice_sessions.get(request.sid)
    if not session_meta:
        emit("voice_error", {"detail": "Not authenticated"})
        return

    session_id   = data.get("session_id") or str(uuid.uuid4())
    session_mode = data.get("session_mode", "patient")
    patient_id   = data.get("patient_id") or session_meta["user_id"]

    if session_mode == "ambient" and session_meta["role"] not in ("doctor", "admin"):
        emit("voice_error", {"detail": "Ambient mode requires doctor role"})
        return

    session_meta.update({
        "session_id":    session_id,
        "session_mode":  session_mode,
        "patient_id":    patient_id,
        "language_hint": data.get("language", "en"),
    })

    join_room(f"voice:{session_id}")

    # Load patient context from DB
    patient_context = {}
    patient_name    = "there"
    try:
        from app.models.patient import PatientProfile
        profile = PatientProfile.query.filter_by(user_id=patient_id).first()
        if profile:
            try:
                from app.models.user import User
                user = User.query.filter_by(id=patient_id).first()
                if user:
                    patient_name = getattr(user, 'name', None) or getattr(user, 'username', None) or getattr(user, 'email', '').split('@')[0] or 'there'
            except Exception:
                pass

            age = None
            if getattr(profile, 'date_of_birth', None):
                from datetime import date
                try:
                    dob = profile.date_of_birth
                    today = date.today()
                    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                except Exception:
                    pass

            patient_context = {
                "name":               patient_name,
                "age":                age,
                "blood_type":         getattr(profile, 'blood_type', None),
                "chronic_conditions": getattr(profile, 'chronic_diseases', []) or [],
                "current_medications": [],
                "allergies":          [],
            }
    except Exception as exc:
        logger.warning("VoiceWS: patient profile load failed: %s", exc)

    turn_count = 0
    try:
        import redis as redis_lib, os
        r = redis_lib.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
        raw = r.get(f"vitalmind:voice:{session_id}")
        if raw:
            import json
            existing = json.loads(raw)
            turn_count = len(existing.get("history", []))
    except Exception:
        pass

    from app.services.gemini_live_service import GeminiLiveSession

    _sid = request.sid

    def _emit_to_sid(event, data):
        socketio.emit(event, data, to=_sid, namespace="/voice")

    live_session = GeminiLiveSession(
        session_id=session_id,
        patient_name=patient_name,
        patient_context=patient_context,
        emit_fn=_emit_to_sid,
        turn_count=turn_count,
        language=session_meta.get("language_hint", "en"),
    )
    live_session.start()
    _live_sessions[_sid] = live_session

    logger.info(
        "VoiceWS: Live session %s started (mode=%s patient=%s)",
        session_id, session_mode, patient_id,
    )

    emit("voice_session_joined", {
        "session_id":   session_id,
        "session_mode": session_mode,
        "patient_id":   patient_id,
        "language_hint": data.get("language", "en"),
        "backend":      "modular-stt-llm-tts",
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    })

@socketio.on("update_language", namespace="/voice")
def handle_update_language(data):
    from flask import request
    sid = request.sid
    lang = data.get("language", "en")
    
    session_meta = _voice_sessions.get(sid)
    if session_meta:
        session_meta["language_hint"] = lang
        
    live_session = _live_sessions.get(sid)
    if live_session:
        live_session.language = lang
        logger.info("VoiceWS: Updated session %s language to %s", live_session.session_id, lang)

@socketio.on("audio_chunk", namespace="/voice")
def handle_audio_chunk(data):
    from flask import request
    sid = request.sid
    if type(data) is bytes:
        # direct binary
        chunk = data
    elif type(data) is str:
        # b64
        import base64
        chunk = base64.b64decode(data)
    elif type(data) is dict:
        import base64
        chunk = base64.b64decode(data.get("audio_b64", ""))
    else:
        return

    session = _live_sessions.get(sid)
    if session:
        session.send_audio(chunk)

@socketio.on("audio_turn_complete", namespace="/voice")
def handle_audio_turn_complete(data=None):
    from flask import request
    sid = request.sid
    session = _live_sessions.get(sid)
    if session:
        session.end_turn()

@socketio.on("end_voice_session", namespace="/voice")
def handle_end_voice_session(data=None):
    from flask import request
    sid = request.sid
    session = _live_sessions.get(sid)
    if session:
        session.close()
        _live_sessions.pop(sid, None)

