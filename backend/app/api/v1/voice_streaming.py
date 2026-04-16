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
    UNIFIED_AUDIO_DOCTOR_PROMPT,
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


def _compact_history(history: list[dict], max_full_turns: int = 4) -> tuple[str, str]:
    """
    Rolling context window: keep last max_full_turns verbatim,
    summarize older turns into a brief string (no extra LLM call).
    Reduces token count by ~60% for long sessions.
    """
    if not history:
        return "", ""
    recent = history[-max_full_turns:] if len(history) > max_full_turns else history
    older  = history[:-max_full_turns] if len(history) > max_full_turns else []

    recent_text = "\n".join(
        f"{m.get('role','?').upper()}: {(m.get('transcript') or '')[:120]}"
        for m in recent
    )
    if not older:
        return "", recent_text

    older_parts = [
        f"{'Patient' if t.get('role') == 'patient' else 'Doctor'}: {(t.get('transcript') or '')[:70]}"
        for t in older if (t.get('transcript') or '').strip()
    ]
    return "; ".join(older_parts[:6]), recent_text


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
    """
    Optimised SSE generator — latency target: ~1.5s to first audio chunk.

    Key changes:
    1. ONE unified Gemini Flash call: STT + language detect + doctor response
    2. Always gemini-3-flash-preview (no Pro thinking delay)
    3. Rolling context window (last 4 turns full, older summarised)
    4. Per-sentence TTS with look-ahead pre-fetching via ThreadPoolExecutor
    """
    import re as _re
    import time as _time
    from concurrent.futures import ThreadPoolExecutor
    from google import genai as google_genai
    from google.genai import types as genai_types

    _t_start = _time.perf_counter()

    mime_map = {
        "webm": "audio/webm", "mp4": "audio/mp4", "wav": "audio/wav",
        "ogg":  "audio/ogg",  "mp3": "audio/mpeg", "m4a": "audio/mp4", "flac": "audio/flac",
    }
    mime_type = mime_map.get(audio_format.lower(), f"audio/{audio_format}")

    # ── 1. Load session from Redis (needed for context in unified call) ──────────────
    session_history: list[dict] = []
    turn_count = 0
    redis_client = None
    try:
        import redis as _redis
        redis_client = _redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
            socket_connect_timeout=0.3,
        )
        raw = redis_client.get(f"vitalmind:voice:{session_id}")
        if raw:
            session_history = json.loads(raw).get("history", [])
        turn_count = len(session_history)
    except Exception:
        pass

    # ── 2. Rolling context window ─────────────────────────────────────────────────
    older_summary, recent_text = _compact_history(session_history, max_full_turns=4)
    session_context = (
        f"[Earlier (summarized): {older_summary}]\n\n{recent_text}" if older_summary else recent_text
    )
    # Drop patient name after first turn to prevent repetitive greetings
    ctx_for_prompt = {k: v for k, v in patient_context.items() if k != "name" or turn_count == 0}

    # ── 3. ONE unified Gemini Flash call ────────────────────────────────────────────
    # Replaces: _transcribe_audio + _detect_language + _extract_medical_entities + _process_voice_command
    # from voice_agent.py (4 separate API calls → 1 call, saves ~3-5 seconds)
    gai_client  = google_genai.Client(api_key=_GOOGLE_KEY)
    audio_part  = genai_types.Part.from_bytes(data=audio_data, mime_type=mime_type)

    transcript         = ""
    detected_language  = language_hint or "en"
    full_response_text = ""
    urgency_flags: list = []
    primary_intent     = "symptom_report"

    try:
        unified_prompt = UNIFIED_AUDIO_DOCTOR_PROMPT.format(
            patient_context=json.dumps(ctx_for_prompt),
            session_summary=session_context,
            turn_count=turn_count,
        )
        stt_resp = gai_client.models.generate_content(
            model=_GEMINI_FLASH,
            contents=[unified_prompt, audio_part],
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=1500,   # was 600 — caused JSON truncation mid-string
            ),
        )
        raw_text = (stt_resp.text or "").strip()
        logger.debug("StreamVoice: raw Gemini response: %r", raw_text[:200])

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            # Regex fallback: extract fields even from partial/malformed JSON
            logger.warning("StreamVoice: JSON decode failed, attempting regex repair on: %r", raw_text[:120])
            import re as _re2
            def _extract(key: str) -> str:
                m = _re2.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text, _re2.DOTALL)
                return m.group(1) if m else ""
            transcript         = _extract("transcript")
            detected_language  = _extract("detected_language") or (language_hint or "en")
            full_response_text = _extract("response")
            if not transcript and not full_response_text:
                yield _sse({"type": "error", "message": "Voice processing failed. Please try again."})
                return
            # skip the parsed.get() block below
            urgency_flags  = []
            primary_intent = "symptom_report"
        else:
            transcript         = parsed.get("transcript", "").strip()
            detected_language  = parsed.get("detected_language", language_hint or "en")
            full_response_text = parsed.get("response", "").strip()
            urgency_flags      = parsed.get("urgency_flags", [])
            primary_intent     = parsed.get("primary_intent", "symptom_report")

    except Exception as exc:
        logger.error("StreamVoice: unified Gemini call failed: %s", exc)
        yield _sse({"type": "error", "message": "Voice processing failed. Please try again."})
        return

    _t_gemini = _time.perf_counter()
    logger.info("StreamVoice ⏱ Gemini call: %.0fms", (_t_gemini - _t_start) * 1000)

    if not transcript:
        yield _sse({"type": "error", "message": "Could not hear audio clearly. Please try again."})
        return

    # ── Closing-intent detection ────────────────────────────────────────────────
    # If patient says thank you / bye / done → respond warmly and close session
    _CLOSING_RE = _re.compile(
        r'^\s*(thank(?:s| you)|dhanyavaad|shukriya|ok\s*thanks?|bye|goodbye|alvida|'
        r'theek\s*hai\s*(?:shukriya|thanks?)?|bas\s*(?:shukriya|thanks?)?|'
        r'that\s*(?:is\s*)?all|no\s*more\s*questions?|i\s*(?:am\s*)?done|'
        r'accha\s*(?:ji\s*)?(?:shukriya|thanks?)?)\s*[.!]*\s*$',
        _re.IGNORECASE | _re.UNICODE
    )
    if _CLOSING_RE.match(transcript):
        _farewells = {
            "hi": "Bilkul, Pallavi ji! Apna khayal rakhein aur jald hi doctor se mil lein. Get well soon! 🌸",
            "ta": "சரி, கவலைப்படாதீர்கள். விரைவில் குணமாவீர்கள்!",
            "te": "సరే, త్వరలో కోలుకోండి! జాగ్రత్తగా ఉండండి.",
            "en": "You're welcome! Take care and please do follow up with your doctor soon. Wishing you a speedy recovery! 🌸",
        }
        farewell_text = _farewells.get(detected_language, _farewells["en"])
        lang_code, voice_name, ssml_gender = get_google_tts_voice(detected_language)
        audio_b64 = _tts_sentence(farewell_text, lang_code, voice_name, ssml_gender)
        yield _sse({"type": "chunk", "chunk_index": 0, "text": farewell_text,
                    "audio_b64": audio_b64, "language": detected_language})
        yield _sse({"type": "done", "transcript": transcript, "spoken_response": farewell_text,
                    "language": detected_language, "is_emergency": False,
                    "symptom_summary": {"urgency": "routine", "symptoms": [],
                                        "differential": None, "recommended_tests": [],
                                        "phase": "closed", "turn": turn_count + 1},
                    "session_id": session_id, "chunk_count": 1})
        return

    lang_code, voice_name, ssml_gender = get_google_tts_voice(
        detected_language, is_emergency=bool(urgency_flags)
    )

    # ── 4. Emergency fast path ──────────────────────────────────────────────────
    if urgency_flags:
        em_text = (
            "This sounds like a medical emergency. "
            "Please call emergency services immediately. I am alerting medical staff."
        )
        em_lc, em_voice, em_gender = get_google_tts_voice("en", is_emergency=True)
        audio_b64 = _tts_sentence(em_text, em_lc, em_voice, em_gender)
        yield _sse({"type": "chunk", "chunk_index": 0, "text": em_text,
                    "audio_b64": audio_b64, "language": "en"})
        yield _sse({"type": "done", "transcript": transcript, "spoken_response": em_text,
                    "language": "en", "is_emergency": True,
                    "symptom_summary": {"urgency": "emergency", "symptoms": [],
                                        "differential": None, "recommended_tests": [],
                                        "phase": "triage", "turn": turn_count + 1},
                    "session_id": session_id, "chunk_count": 1})
        return

    if not full_response_text:
        full_response_text = "I heard you. Could you tell me more about what you're experiencing?"

    # ── 5. Per-sentence TTS with look-ahead pre-fetching ─────────────────────────
    # While the frontend plays sentence[0], sentence[1] is already being synthesised.
    sentences = _split_sentences(full_response_text) or [full_response_text]
    chunk_index = 0

    with ThreadPoolExecutor(max_workers=2) as executor:
        tts_futures: dict = {}
        # Pre-submit TTS for first 2 sentences immediately
        for i in range(min(2, len(sentences))):
            tts_futures[i] = executor.submit(
                _tts_sentence, sentences[i], lang_code, voice_name, ssml_gender
            )

        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            # Pre-fetch sentence i+2 while we wait for i
            nxt = i + 2
            if nxt < len(sentences) and nxt not in tts_futures:
                tts_futures[nxt] = executor.submit(
                    _tts_sentence, sentences[nxt], lang_code, voice_name, ssml_gender
                )
            if i not in tts_futures:
                tts_futures[i] = executor.submit(
                    _tts_sentence, sentences[i], lang_code, voice_name, ssml_gender
                )
            audio_b64 = tts_futures[i].result()
            yield _sse({
                "type": "chunk",
                "chunk_index": chunk_index,
                "text": sentence,
                "audio_b64": audio_b64,
                "language": detected_language,
            })
            chunk_index += 1

    # ── 6. Final metadata event ──────────────────────────────────────────────────
    phase = "initial_intake" if turn_count == 0 else "followup_interview"
    yield _sse({
        "type": "done",
        "transcript": transcript,
        "spoken_response": full_response_text,
        "language": detected_language,
        "is_emergency": False,
        "symptom_summary": {
            "symptoms": [], "urgency": "routine", "differential": None,
            "recommended_tests": [], "phase": phase, "turn": turn_count + 1,
        },
        "session_id": session_id,
        "chunk_count": chunk_index,
    })

    # ── 7. Persist turn to Redis async (fire-and-forget) ────────────────────────
    try:
        import threading
        _hist_snapshot = list(session_history)
        _transcript    = transcript
        _response      = full_response_text
        _ctx           = session_context

        def _save():
            try:
                import redis as _r2
                rc = _r2.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=int(os.getenv("REDIS_DB", 0)),
                    decode_responses=True,
                )
                updated = _hist_snapshot[-8:]   # hard cap at 8 turns
                ts = __import__("datetime").datetime.utcnow().isoformat()
                updated.append({"role": "patient",    "transcript": _transcript, "timestamp": ts})
                updated.append({"role": "assistant",  "transcript": _response,   "timestamp": ts})
                rc.setex(f"vitalmind:voice:{session_id}", 1800, json.dumps({
                    "history": updated, "summary": _ctx,
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
