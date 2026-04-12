"""
voice_streaming.py — SSE streaming endpoint for VitalMind AI Doctor.

POST /api/v1/voice/ai-doctor-stream
  → Accepts: multipart/form-data (audio + session_id + language + format)
  → Returns:  text/event-stream (SSE)

Each SSE event is JSON:
  { "type": "chunk",  "chunk_index": 0, "audio_b64": "...", "text": "sentence...", "language": "en" }
  { "type": "done",   "transcript": "...", "spoken_response": "...", "language": "en",
                      "symptom_summary": {...}, "is_emergency": false }
  { "type": "error",  "message": "..." }

The frontend plays chunk 0 while chunks 1, 2, 3 are still synthesising.
Total latency to first audio: ~2s (Flash transcription + language detect + first sentence TTS).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Generator, Optional

from flask import Blueprint, Response, request, stream_with_context, jsonify

from app.middleware.auth_middleware import require_auth
from app.agents.voice_agent import (
    _GEMINI_FLASH, _GEMINI_MODEL, _GOOGLE_KEY,
    _get_tts_client, _extract_text,
    get_voice_agent,
)
from app.agents.prompts.voice_prompts import (
    AI_DOCTOR_SYSTEM_PROMPT,
    VOICE_ROUTING_PROMPT,
    GEMINI_AUDIO_TRANSCRIPTION_PROMPT,
    LANGUAGE_DETECTION_PROMPT,
    get_google_tts_voice,
    DEFAULT_TTS_SPEED,
)

logger = logging.getLogger(__name__)

voice_stream_bp = Blueprint("voice_stream", __name__, url_prefix="/api/v1/voice")

# ─────────────────────────────────────────────────────────────────────────────
# Sentence splitter — handles Indic full-stops (।) + standard punctuation
# ─────────────────────────────────────────────────────────────────────────────

_SENTENCE_RE = re.compile(r'(?<=[.!?।])\s+')
_MIN_SENTENCE_CHARS = 20   # Don't TTS fragments shorter than this


def _split_sentences(text: str) -> list[str]:
    """Split text into TTS-able sentences, merging short fragments."""
    raw = _SENTENCE_RE.split(text.strip())
    sentences: list[str] = []
    buf = ""
    for s in raw:
        buf = (buf + " " + s).strip() if buf else s
        if len(buf) >= _MIN_SENTENCE_CHARS:
            sentences.append(buf)
            buf = ""
    if buf:
        sentences.append(buf)
    return sentences


# ─────────────────────────────────────────────────────────────────────────────
# TTS helper — synthesise one sentence to base64 MP3
# ─────────────────────────────────────────────────────────────────────────────

def _tts_sentence(text: str, lang_code: str, voice_name: str, ssml_gender: str) -> Optional[str]:
    """Return base64-encoded MP3 for a single sentence, or None on failure."""
    try:
        from google.cloud import texttospeech as tts_lib
        client = _get_tts_client()
        if client is None:
            raise RuntimeError("TTS singleton unavailable")

        resp = client.synthesize_speech(
            input=tts_lib.SynthesisInput(text=text[:1000]),
            voice=tts_lib.VoiceSelectionParams(
                language_code=lang_code,
                name=voice_name,
                ssml_gender=getattr(tts_lib.SsmlVoiceGender, ssml_gender, tts_lib.SsmlVoiceGender.FEMALE),
            ),
            audio_config=tts_lib.AudioConfig(
                audio_encoding=tts_lib.AudioEncoding.MP3,
                speaking_rate=DEFAULT_TTS_SPEED,
            ),
        )
        return base64.b64encode(resp.audio_content).decode("utf-8")
    except Exception as exc:
        logger.warning("StreamTTS: sentence TTS failed (%s) — trying REST", exc)
        # REST fallback
        try:
            import requests as _req
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={_GOOGLE_KEY}"
            payload = {
                "input": {"text": text[:1000]},
                "voice": {"languageCode": lang_code, "name": voice_name, "ssmlGender": ssml_gender},
                "audioConfig": {"audioEncoding": "MP3", "speakingRate": DEFAULT_TTS_SPEED},
            }
            r = _req.post(url, json=payload, timeout=8)
            if r.status_code == 200:
                return r.json().get("audioContent")
        except Exception as exc2:
            logger.error("StreamTTS: REST fallback also failed: %s", exc2)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SSE generator
# ─────────────────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _generate_stream(
    audio_data: bytes,
    audio_format: str,
    session_id: str,
    patient_id: str,
    language_hint: Optional[str],
    patient_context: dict,
) -> Generator[str, None, None]:
    """Core SSE generator: transcribe → detect lang → stream LLM → per-sentence TTS."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    from google import genai as google_genai
    from google.genai import types as genai_types

    # ── Step 1: Transcribe audio (Flash, non-streaming) ──────────────────────
    mime_map = {"webm": "audio/webm", "mp4": "audio/mp4", "wav": "audio/wav",
                "ogg": "audio/ogg", "mp3": "audio/mpeg", "m4a": "audio/mp4"}
    mime_type = mime_map.get(audio_format.lower(), f"audio/{audio_format}")
    transcript = ""
    try:
        client = google_genai.Client(api_key=_GOOGLE_KEY)
        audio_part = genai_types.Part.from_bytes(data=audio_data, mime_type=mime_type)
        tr = client.models.generate_content(
            model=_GEMINI_FLASH,
            contents=[GEMINI_AUDIO_TRANSCRIPTION_PROMPT, audio_part],
            config=genai_types.GenerateContentConfig(
                system_instruction=AI_DOCTOR_SYSTEM_PROMPT,
                temperature=0, max_output_tokens=512,
            ),
        )
        transcript = (tr.text or "").strip()
    except Exception as exc:
        logger.error("StreamVoice: transcription failed: %s", exc)
        yield _sse({"type": "error", "message": "Transcription failed. Please try again."})
        return

    if not transcript:
        yield _sse({"type": "error", "message": "Could not hear audio. Please speak clearly and try again."})
        return

    # ── Step 2: Language detection (Flash) ───────────────────────────────────
    detected_language = language_hint or "en"
    try:
        if not language_hint or len(transcript) >= 30:
            llm = ChatGoogleGenerativeAI(model=_GEMINI_FLASH, temperature=0, google_api_key=_GOOGLE_KEY)
            lang_resp = llm.invoke([
                SystemMessage(content="You are a language detection assistant. Respond with JSON only."),
                HumanMessage(content=LANGUAGE_DETECTION_PROMPT.format(transcript=transcript[:500])),
            ])
            lang_result = json.loads(_extract_text(lang_resp))
            detected_language = lang_result.get("primary_language", "en")
    except Exception as exc:
        logger.warning("StreamVoice: lang detect failed: %s — using 'en'", exc)

    lang_code, voice_name, ssml_gender = get_google_tts_voice(detected_language, is_emergency=False)

    # ── Step 3: Load session from Redis ──────────────────────────────────────
    session_history: list[dict] = []
    session_summary = ""
    turn_count = 0
    try:
        import redis as _redis
        r = _redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
            socket_connect_timeout=0.3,
        )
        raw = r.get(f"vitalmind:voice:{session_id}")
        if raw:
            saved = json.loads(raw)
            session_history = saved.get("history", [])
            session_summary = saved.get("summary", "")
        turn_count = len(session_history)
    except Exception:
        pass

    # ── Step 4: Stream Gemini response sentence by sentence ───────────────────
    model = _GEMINI_MODEL if turn_count >= 4 else _GEMINI_FLASH
    
    prompt_transcript = transcript
    if turn_count > 0:
        if "name" in patient_context:
            del patient_context["name"]
        prompt_transcript = f"[SYSTEM: This is turn {turn_count}. DO NOT say Hello/Namaste. DO NOT use the patient's name. Go straight to the medical response. CRITICAL: YOU MUST RESPOND IN THE {detected_language} LANGUAGE.]\n\n{transcript}"

    recent_history_text = "\n".join([f"{m['role'].upper()}: {m['transcript']}" for m in session_history[-6:]])

    prompt = VOICE_ROUTING_PROMPT.format(
        transcript=prompt_transcript,
        entities="[]",
        intent="symptom_report",
        patient_context=json.dumps(patient_context)[:400],
        session_summary=recent_history_text,
        urgency_flags="[]",
        language=detected_language,
    )

    llm_stream_client = google_genai.Client(api_key=_GOOGLE_KEY)
    full_response_text = ""
    sentence_buffer = ""
    chunk_index = 0
    full_json_text = ""

    try:
        response_stream = llm_stream_client.models.generate_content_stream(
            model=model,
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                system_instruction=AI_DOCTOR_SYSTEM_PROMPT,
                temperature=0.3,
            )
        )
        
        for chunk in response_stream:
            if chunk.text:
                full_json_text += chunk.text

        # Parse the complete JSON response
        clean = _extract_text(type("R", (), {"content": full_json_text})())
        result = json.loads(clean)
        full_response_text = result.get("spoken_response", "")

        if not full_response_text:
            full_response_text = "I heard you. Could you tell me more about what you're experiencing?"

        # ── Step 5: Send the entire response as a single TTS chunk to avoid speech gaps ─
        audio_b64 = _tts_sentence(full_response_text, lang_code, voice_name, ssml_gender)
        yield _sse({
            "type": "chunk",
            "chunk_index": 0,
            "text": full_response_text,
            "audio_b64": audio_b64,
            "language": detected_language,
        })
        chunk_index = 1

    except Exception as exc:
        logger.error("StreamVoice: LLM/TTS stream failed: %s", exc)
        yield _sse({"type": "error", "message": "Processing failed. Please try again."})
        return

    # ── Step 6: Send final metadata event ────────────────────────────────────
    yield _sse({
        "type": "done",
        "transcript": transcript,
        "spoken_response": full_response_text,
        "language": detected_language,
        "is_emergency": False,
        "symptom_summary": {
            "symptoms": [],
            "urgency": "routine",
            "differential": None,
            "recommended_tests": [],
            "phase": "initial_intake",
            "turn": turn_count + 1,
        },
        "session_id": session_id,
        "chunk_count": chunk_index,
    })

    # ── Step 7: Persist turn to Redis (async, non-blocking) ──────────────────
    try:
        import threading
        def _save():
            try:
                import redis as _r2
                rc = _r2.Redis(host=os.getenv("REDIS_HOST","localhost"),
                               port=int(os.getenv("REDIS_PORT",6379)),
                               db=int(os.getenv("REDIS_DB",0)),
                               decode_responses=True)
                session_history.append({"role": "patient", "transcript": transcript,
                                        "timestamp": __import__("datetime").datetime.utcnow().isoformat()})
                session_history.append({"role": "assistant", "transcript": full_response_text,
                                        "timestamp": __import__("datetime").datetime.utcnow().isoformat()})
                rc.setex(f"vitalmind:voice:{session_id}", 1800, json.dumps({
                    "history": session_history[-8:], "summary": session_summary,
                    "session_id": session_id, "patient_id": patient_id,
                }))
            except Exception:
                pass
        threading.Thread(target=_save, daemon=True).start()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@voice_stream_bp.route("/ai-doctor-stream", methods=["POST"])
@require_auth
def ai_doctor_stream():
    """
    SSE streaming AI Doctor endpoint.
    Accepts same multipart/form-data as /ai-doctor-conversation.
    Returns text/event-stream — first audio chunk in ~2s.
    """
    current_user = getattr(request, "current_user", None)
    if not current_user:
        return jsonify({"error": "Unauthorized"}), 401

    # Parse audio input (same as non-streaming endpoint)
    audio_bytes = None
    session_id = ""
    language_hint = None
    audio_format = "webm"

    if request.content_type and "multipart" in request.content_type:
        audio_file = request.files.get("audio")
        session_id = (request.form.get("session_id") or "").strip()
        language_hint = request.form.get("language")
        audio_format = request.form.get("format", "webm")
        if not audio_file:
            return jsonify({"error": "audio file required"}), 400
        audio_bytes = audio_file.read()
    else:
        data = request.get_json(silent=True) or {}
        session_id = (data.get("session_id") or "").strip()
        language_hint = data.get("language")
        audio_format = data.get("audio_format", "webm")
        audio_b64_str = (data.get("audio_b64") or "").strip()
        if not audio_b64_str:
            return jsonify({"error": "audio_b64 or audio file required"}), 400
        try:
            import base64 as _b
            audio_bytes = _b.b64decode(audio_b64_str)
        except Exception:
            return jsonify({"error": "Invalid base64 audio"}), 400

    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    if not audio_bytes or len(audio_bytes) < 512:
        return jsonify({"error": "Audio too short"}), 400

    patient_id = str(current_user.id)

    # Load patient context
    patient_context: dict = {}
    try:
        from app.models.patient import PatientProfile
        from app.models.medication import Prescription
        profile = PatientProfile.query.filter_by(user_id=patient_id).first()
        if profile:
            meds = Prescription.query.filter_by(patient_id=profile.id, status="active").all()
            patient_context = {
                "name": f"{profile.user.first_name} {profile.user.last_name}" if profile.user else "Patient",
                "current_medications": [p.medication.name if p.medication else "" for p in meds[:5]],
                "allergies": [a.allergen for a in getattr(profile, "allergies", [])][:5],
            }
    except Exception as e:
        logger.debug("StreamVoice: patient context skipped: %s", e)

    return Response(
        stream_with_context(_generate_stream(
            audio_data=audio_bytes,
            audio_format=audio_format,
            session_id=session_id,
            patient_id=patient_id,
            language_hint=language_hint,
            patient_context=patient_context,
        )),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable nginx buffering
        },
    )
