"""
voice_agent.py — VitalMind Voice Interaction Agent (LangGraph)

Full pipeline: STT → language detect → medical NER → intent routing → TTS

Graph topology:
  START
    │
    ▼
  receive_audio_chunk      ← validate + buffer incoming binary audio
    │
    ▼
  transcribe_audio         ← OpenAI Whisper API (STT)
    │
    ▼
  detect_language          ← GPT-4o-mini JSON extraction
    │
    ▼
  extract_medical_entities ← GPT-4o-mini clinical NER
    │
    ▼
  manage_voice_session     ← Redis: load session history, update context
    │
    ▼
  process_voice_command    ← GPT-4o-mini routing + spoken response generation
    │                        Conditionally routes to orchestrator for complex intents
    ├─ is_emergency ───────→ synthesize_speech (immediate TTS, skip further routing)
    │
    └─ normal ─────────────→ synthesize_speech
                                │
                                ▼
                           stream_audio_response ← base64-encode + emit via WS
                                │
                                ▼
                               END

Ambient mode (doctor):
  Audio chunks → transcribe → detect_language → ambient_extract_entities
  (no TTS, real-time SOAP note accumulation sent to frontend)

Key design decisions:
- STT via openai.audio.transcriptions.create (Whisper-1)
- TTS via openai.audio.speech.create — mp3 output, base64-encoded for WS transport
- All LLM calls: gpt-4o-mini for speed
- Redis key: vitalmind:voice:<session_id>
- Session TTL: 30 minutes of inactivity
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_GEMINI_MODEL = "gemini-3.1-pro-preview"   # Deep reasoning — turn 4+ / symptom analysis
_GEMINI_FLASH = "gemini-3-flash-preview"    # Speed-optimised — turns 1-3 (1.7s latency)
_GOOGLE_KEY = __import__("os").getenv("GOOGLE_API_KEY")
from langgraph.graph import StateGraph, END, START

from app.agents.base_agent import BaseAgent, AgentState
from app.agents.prompts.voice_prompts import (
    MEDICAL_NER_PROMPT,
    LANGUAGE_DETECTION_PROMPT,
    VOICE_ROUTING_PROMPT,
    AMBIENT_NER_PROMPT,
    AI_DOCTOR_SYSTEM_PROMPT,
    GEMINI_AUDIO_TRANSCRIPTION_PROMPT,
    DEFAULT_TTS_VOICE,
    DOCTOR_TTS_VOICE,
    EMERGENCY_TTS_VOICE,
    DEFAULT_TTS_SPEED,
    EMERGENCY_TTS_SPEED,
    get_google_tts_voice,
)

logger = logging.getLogger(__name__)

_REDIS_SESSION_TTL = 1800   # 30 minutes
_RESPONSE_CACHE_TTL = 3600  # 1 hour — common symptom query cache
_LLM_TIMEOUT = 10

# ── Pre-warmed TTS singleton — avoids gRPC channel setup (~200-400ms) per request ──
_tts_client_singleton = None

def _get_tts_client():
    """Return a reused Google Cloud TTS client (initialised once per process)."""
    global _tts_client_singleton
    if _tts_client_singleton is None:
        try:
            from google.cloud import texttospeech as _tts
            import json as _json
            import google.oauth2.service_account as _sa

            tts_key_json = os.getenv("GOOGLE_CLOUD_TTS_KEY_JSON")
            if tts_key_json:
                creds_info = _json.loads(tts_key_json)
                creds = _sa.Credentials.from_service_account_info(
                    creds_info,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                _tts_client_singleton = _tts.TextToSpeechClient(credentials=creds)
            else:
                _tts_client_singleton = _tts.TextToSpeechClient()
            logger.info("VoiceAgent: TTS singleton initialised")
        except Exception as exc:
            logger.warning("VoiceAgent: TTS singleton init failed (%s) — will use REST fallback", exc)
            _tts_client_singleton = None
    return _tts_client_singleton


def _get_llm(turn_count: int = 0, temperature: float = 0.0) -> "ChatGoogleGenerativeAI":
    """
    Route LLM calls by conversation turn:
      Turns 1-3 → gemini-3-flash-preview  (~1.7s, no Thinking overhead)
      Turn 4+   → gemini-3.1-pro-preview  (~5s, deeper medical reasoning)
    """
    model = _GEMINI_MODEL if turn_count >= 4 else _GEMINI_FLASH
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=_GOOGLE_KEY,
    )


def _extract_text(response) -> str:
    """
    Extract text from a LangChain Gemini response safely.

    gemini-3.1-pro-preview uses 'thinking mode' and returns response.content
    as a LIST of dicts, e.g.:
        [{'type': 'text', 'text': '```json\\n{...}\\n```', 'extras': {...}}]

    Older models return a plain str.
    This helper normalises both and strips markdown code fences.
    """
    content = response.content

    # Normalise list → str (thinking mode)
    if isinstance(content, list):
        parts = [
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
            if (isinstance(item, dict) and item.get("type") == "text") or not isinstance(item, dict)
        ]
        content = "".join(parts).strip()

    if not isinstance(content, str):
        content = str(content)

    # Strip markdown JSON fences: ```json ... ``` or ``` ... ```
    import re as _re
    content = _re.sub(r"^```(?:json)?\s*\n?", "", content.strip(), flags=_re.IGNORECASE)
    content = _re.sub(r"\n?```\s*$", "", content.strip())
    return content.strip()


# ─────────────────────────────────────────────────────────────────────────────
# VoiceState — extends AgentState with voice-specific fields
# ─────────────────────────────────────────────────────────────────────────────

class VoiceState(AgentState, total=False):
    # Input
    audio_data: Optional[bytes]          # Raw binary audio chunk
    audio_format: str                    # "webm", "mp4", "wav", "ogg"
    session_mode: str                    # "patient" | "ambient"
    language_hint: Optional[str]         # ISO 639-1 hint from client

    # STT result
    transcript: str
    transcript_confidence: float

    # Language detection
    detected_language: str
    language_name: str
    code_switching: bool

    # NER
    entities: list[dict]
    primary_intent: str
    urgency_flags: list[str]
    entity_summary: str

    # Session memory
    session_history: list[dict]
    session_summary: str
    accumulated_soap: dict              # Ambient mode SOAP note accumulation

    # Routing result
    spoken_response: str
    route_action: str
    is_emergency: bool
    orchestrator_response: Optional[dict]

    # TTS output
    audio_response_b64: Optional[str]   # base64-encoded mp3
    audio_response_bytes: Optional[bytes]
    tts_voice: str
    tts_duration_hint: float

    # Consent (ambient mode)
    patient_consent_logged: bool


# ─────────────────────────────────────────────────────────────────────────────
# VoiceAgent
# ─────────────────────────────────────────────────────────────────────────────

class VoiceAgent(BaseAgent):
    """
    Voice Interaction Agent — full STT → NLP → TTS pipeline.

    Supports two modes:
      patient  — interactive voice assistant (default)
      ambient  — passive listening for doctor; builds real-time SOAP notes
    """

    def get_tools(self) -> list:
        return []   # Voice agent uses direct API calls, not LangChain tools

    def build_graph(self) -> StateGraph:
        graph = StateGraph(VoiceState)

        graph.add_node("receive_audio_chunk",       self._receive_audio_chunk)
        graph.add_node("transcribe_audio",          self._transcribe_audio)
        graph.add_node("detect_language",           self._detect_language)
        graph.add_node("extract_medical_entities",  self._extract_medical_entities)
        graph.add_node("manage_voice_session",      self._manage_voice_session)
        graph.add_node("process_voice_command",     self._process_voice_command)
        graph.add_node("synthesize_speech",         self._synthesize_speech)
        graph.add_node("stream_audio_response",     self._stream_audio_response)

        # Linear pipeline
        graph.add_edge(START, "receive_audio_chunk")
        graph.add_edge("receive_audio_chunk", "transcribe_audio")
        graph.add_edge("transcribe_audio", "detect_language")
        graph.add_edge("detect_language", "extract_medical_entities")
        graph.add_edge("extract_medical_entities", "manage_voice_session")

        # Branch: ambient mode skips TTS, patient mode proceeds to process_voice_command
        graph.add_conditional_edges(
            "manage_voice_session",
            self._route_by_session_mode,
            {
                "process": "process_voice_command",
                "ambient_end": END,
            },
        )

        graph.add_edge("process_voice_command", "synthesize_speech")
        graph.add_edge("synthesize_speech", "stream_audio_response")
        graph.add_edge("stream_audio_response", END)

        return graph

    # ─────────────────────────────────────────────────────────────────────
    # Node 1: receive_audio_chunk
    # ─────────────────────────────────────────────────────────────────────

    def _receive_audio_chunk(self, state: VoiceState) -> VoiceState:
        """Validate the incoming audio data and set defaults."""
        ctx = dict(state.get("context", {}))
        audio_data = state.get("audio_data")

        if not audio_data:
            logger.warning("VoiceAgent: no audio_data in state")
            return {**state, "error": "No audio data received", "transcript": ""}

        audio_format = state.get("audio_format", "webm")
        session_mode = state.get("session_mode", "patient")

        ctx["audio_size_bytes"] = len(audio_data)
        ctx["audio_format"] = audio_format

        logger.info(
            "VoiceAgent: received audio chunk %d bytes (format=%s mode=%s) session=%s",
            len(audio_data), audio_format, session_mode, state.get("session_id"),
        )

        return {
            **state,
            "context": ctx,
            "audio_format": audio_format,
            "session_mode": session_mode,
            "transcript": "",
            "entities": [],
            "urgency_flags": [],
            "is_emergency": False,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Node 2: transcribe_audio — Gemini 3.1 Pro native audio input
    # ─────────────────────────────────────────────────────────────────────

    def _transcribe_audio(self, state: VoiceState) -> VoiceState:
        """
        Transcribe audio using Gemini 3.1 Pro native multimodal audio input.
        Sends the raw audio blob directly — no STT service needed.
        Replaces: Groq Whisper / OpenAI Whisper.
        """
        audio_data = state.get("audio_data", b"")
        audio_format = state.get("audio_format", "webm")

        if not audio_data:
            return {**state, "transcript": "", "transcript_confidence": 0.0}

        transcript_text = ""
        confidence = 0.0

        # Map browser recording formats to MIME types Gemini accepts
        mime_map = {
            "webm": "audio/webm",
            "mp4":  "audio/mp4",
            "wav":  "audio/wav",
            "ogg":  "audio/ogg",
            "mp3":  "audio/mpeg",
            "m4a":  "audio/mp4",
            "flac": "audio/flac",
        }
        mime_type = mime_map.get(audio_format.lower(), f"audio/{audio_format}")

        try:
            # Use new google.genai SDK (google.generativeai is deprecated)
            from google import genai as google_genai
            from google.genai import types as genai_types

            client = google_genai.Client(api_key=_GOOGLE_KEY)

            audio_part = genai_types.Part.from_bytes(
                data=audio_data,
                mime_type=mime_type,
            )

            # Use Flash for transcription — same accuracy, ~3x faster than Pro (Thinking)
            response = client.models.generate_content(
                model=_GEMINI_FLASH,
                contents=[GEMINI_AUDIO_TRANSCRIPTION_PROMPT, audio_part],
                config=genai_types.GenerateContentConfig(
                    system_instruction=AI_DOCTOR_SYSTEM_PROMPT,
                    temperature=0,
                    max_output_tokens=512,
                ),
            )

            transcript_text = (response.text or "").strip()
            confidence = 0.95  # Gemini is highly accurate on audio

        except ImportError:
            # Fallback to the older SDK if google.genai not available
            logger.warning("VoiceAgent: google.genai not available, trying google.generativeai")
            try:
                import google.generativeai as genai_legacy  # type: ignore[import]
                genai_legacy.configure(api_key=_GOOGLE_KEY)
                model = genai_legacy.GenerativeModel(model_name=_GEMINI_MODEL)
                audio_part = {"mime_type": mime_type, "data": audio_data}
                response = model.generate_content([GEMINI_AUDIO_TRANSCRIPTION_PROMPT, audio_part])
                transcript_text = (response.text or "").strip()
                confidence = 0.90
            except Exception as exc2:
                logger.error("VoiceAgent: legacy Gemini transcription also failed: %s", exc2)
                transcript_text = ""
                confidence = 0.0
        except Exception as exc:
            logger.error("VoiceAgent: Gemini audio transcription failed: %s", exc)
            transcript_text = ""
            confidence = 0.0


        logger.info(
            "VoiceAgent: Gemini transcript (%d chars, confidence=%.2f): %s",
            len(transcript_text), confidence, transcript_text[:100],
        )

        return {
            **state,
            "transcript": transcript_text,
            "transcript_confidence": confidence,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Node 3: detect_language
    # ─────────────────────────────────────────────────────────────────────

    def _detect_language(self, state: VoiceState) -> VoiceState:
        """Detect language using GPT-4o-mini. Falls back to 'en' on failure."""
        transcript = state.get("transcript", "")

        if not transcript.strip():
            return {**state, "detected_language": "en", "language_name": "English", "code_switching": False}

        # If language_hint provided and transcript is short, trust the hint
        hint = state.get("language_hint")
        if hint and len(transcript) < 30:
            from app.agents.prompts.voice_prompts import SUPPORTED_LANGUAGES
            return {
                **state,
                "detected_language": hint,
                "language_name": SUPPORTED_LANGUAGES.get(hint, hint),
                "code_switching": False,
            }

        try:
            turn_count = len(state.get("session_history", []))
            llm = _get_llm(turn_count=turn_count, temperature=0)
            prompt = LANGUAGE_DETECTION_PROMPT.format(transcript=transcript[:500])
            response = llm.invoke(
                [SystemMessage(content="You are a language detection assistant. Respond with JSON only."),
                 HumanMessage(content=prompt)],
            )
            result = json.loads(_extract_text(response))
            lang = result.get("primary_language", "en")
            name = result.get("language_name", "English")
            switching = result.get("code_switching", False)

        except Exception as exc:
            logger.warning("VoiceAgent: language detection failed: %s — defaulting to 'en'", exc)
            lang, name, switching = "en", "English", False

        logger.debug("VoiceAgent: detected language=%s code_switching=%s", lang, switching)

        return {
            **state,
            "detected_language": lang,
            "language_name": name,
            "code_switching": switching,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Node 4: extract_medical_entities
    # ─────────────────────────────────────────────────────────────────────

    def _extract_medical_entities(self, state: VoiceState) -> VoiceState:
        """
        Run clinical NER on the transcript.
        Ambient mode uses the SOAP-specific prompt.
        Patient mode uses the general medical NER prompt.
        """
        transcript = state.get("transcript", "")
        if not transcript.strip():
            return {
                **state,
                "entities": [],
                "primary_intent": "unknown",
                "urgency_flags": [],
                "entity_summary": "",
            }

        session_mode = state.get("session_mode", "patient")
        language = state.get("detected_language", "en")

        try:
            turn_count = len(state.get("session_history", []))
            llm = _get_llm(turn_count=turn_count, temperature=0)

            if session_mode == "ambient":
                # Ambient: SOAP extraction
                accumulated = state.get("accumulated_soap", {})
                prompt = AMBIENT_NER_PROMPT.format(
                    transcript=transcript,
                    accumulated_context=json.dumps(accumulated, indent=2)[:1000],
                )
            else:
                # Patient: general medical NER
                prompt = MEDICAL_NER_PROMPT.format(
                    transcript=transcript,
                    language=language,
                )

            response = llm.invoke(
                [SystemMessage(content="You are a clinical NLP specialist for medical entity extraction. Respond with JSON only."),
                 HumanMessage(content=prompt)],
            )
            result = json.loads(_extract_text(response))

            if session_mode == "ambient":
                # Merge into accumulated SOAP note
                ctx = dict(state.get("context", {}))
                ctx["latest_soap_segment"] = result
                return {
                    **state,
                    "context": ctx,
                    "accumulated_soap": result,
                    "entities": [],
                    "primary_intent": "ambient_documentation",
                    "urgency_flags": [],
                    "entity_summary": "Ambient segment extracted",
                }

            entities = result.get("entities", [])
            intent = result.get("primary_intent", "unknown")
            flags = result.get("urgency_flags", [])
            summary = result.get("summary", "")

            logger.info(
                "VoiceAgent: NER found %d entities, intent=%s, urgency=%s",
                len(entities), intent, flags,
            )
            return {
                **state,
                "entities": entities,
                "primary_intent": intent,
                "urgency_flags": flags,
                "entity_summary": summary,
            }

        except Exception as exc:
            logger.error("VoiceAgent: NER extraction failed: %s", exc)
            return {
                **state,
                "entities": [],
                "primary_intent": "unknown",
                "urgency_flags": [],
                "entity_summary": "",
            }

    # ─────────────────────────────────────────────────────────────────────
    # Node 5: manage_voice_session
    # ─────────────────────────────────────────────────────────────────────

    def _manage_voice_session(self, state: VoiceState) -> VoiceState:
        """
        Load and update session context from Redis.
        Maintains multi-turn conversation history for coherent responses.
        TTL reset on every update.
        """
        session_id = state.get("session_id") or str(uuid.uuid4())
        patient_id = state.get("patient_id")
        transcript = state.get("transcript", "")
        session_mode = state.get("session_mode", "patient")

        session_history: list[dict] = []
        session_summary = ""
        accumulated_soap: dict = state.get("accumulated_soap", {})

        redis_key = f"vitalmind:voice:{session_id}"

        try:
            import redis as redis_lib
            r = redis_lib.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
            )

            raw = r.get(redis_key)
            if raw:
                saved = json.loads(raw)
                session_history = saved.get("history", [])
                session_summary = saved.get("summary", "")
                if session_mode == "ambient":
                    accumulated_soap = saved.get("accumulated_soap", accumulated_soap)

            # Append current turn to history
            if transcript.strip():
                session_history.append({
                    "role": "patient",
                    "transcript": transcript,
                    "intent": state.get("primary_intent", "unknown"),
                    "entities_count": len(state.get("entities", [])),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # Compact history: keep last 4 turns verbatim, summarise older turns.
            # Reduces tokens sent to Gemini by ~60% for long sessions.
            _FULL_TURNS = 4
            if len(session_history) > _FULL_TURNS:
                older = session_history[:-_FULL_TURNS]
                older_summary = "; ".join(
                    f"{t['role']}: {t['transcript'][:80]}" for t in older
                )
                session_history = session_history[-_FULL_TURNS:]
                # Prepend the summary as a synthetic context marker
                session_history.insert(0, {
                    "role": "summary",
                    "transcript": f"[Earlier context] {older_summary[:400]}",
                    "timestamp": older[0].get("timestamp", ""),
                })

            # Build session summary for the prompt (last 3 human turns)
            recent_human = [t for t in session_history if t.get("role") == "patient"][-3:]
            session_summary = " | ".join(
                f"patient: {t['transcript'][:60]}" for t in recent_human
            )

            # Save back to Redis
            session_data = {
                "session_id": session_id,
                "patient_id": patient_id,
                "session_mode": session_mode,
                "history": session_history,
                "summary": session_summary,
                "accumulated_soap": accumulated_soap,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            r.setex(redis_key, _REDIS_SESSION_TTL, json.dumps(session_data))


        except Exception as exc:
            logger.warning("VoiceAgent: Redis session load/save failed: %s", exc)

        return {
            **state,
            "session_id": session_id,
            "session_history": session_history,
            "session_summary": session_summary,
            "accumulated_soap": accumulated_soap,
        }

    def _route_by_session_mode(self, state: VoiceState) -> str:
        """Conditional edge: ambient mode ends here; patient mode continues to LLM."""
        return "ambient_end" if state.get("session_mode") == "ambient" else "process"

    # ─────────────────────────────────────────────────────────────────────
    # Node 6: process_voice_command
    # ─────────────────────────────────────────────────────────────────────

    def _process_voice_command(self, state: VoiceState) -> VoiceState:
        """
        Generate a spoken response and determine if orchestrator routing is needed.

        Emergency path: urgency_flags present → immediate emergency response.
        Normal path: GPT-4o-mini generates a spoken response + routing decision.
        """
        transcript = state.get("transcript", "")
        urgency_flags = state.get("urgency_flags", [])
        entities = state.get("entities", [])
        intent = state.get("primary_intent", "unknown")
        language = state.get("detected_language", "en")
        session_summary = state.get("session_summary", "")
        patient_ctx = state.get("context", {}).get("patient", {})

        # ── Emergency fast path ──────────────────────────────────────────
        if urgency_flags:
            logger.critical("VoiceAgent: EMERGENCY detected — urgency_flags=%s", urgency_flags)
            emergency_text = (
                "This sounds like a medical emergency. Please call 911 or your local emergency number right now. "
                "Do not wait. If you cannot call, ask someone nearby to call for you immediately. "
                "I'm alerting medical staff."
            )
            # Also trigger triage agent silently
            self._trigger_emergency_triage(state, transcript)

            return {
                **state,
                "spoken_response": emergency_text,
                "route_action": "route_to_triage",
                "is_emergency": True,
            }

        # ── Normal: Gemini AI Doctor response ────────────────────────────
        spoken_response = ""
        route_action = "none"
        orchestrator_response = None
        is_emergency = False

        # Turn count drives Flash (1-3) vs Pro (4+) selection
        session_history = list(state.get("session_history", []))
        turn_count = len(session_history)

        import hashlib as _hashlib
        cache_key = (
            f"vitalmind:voice:cache:"
            f"{_hashlib.md5((transcript[:200] + language).encode()).hexdigest()[:10]}"
        )
        _rc = None
        cache_hit = False
        try:
            import redis as _redis_cache
            _rc = _redis_cache.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
                socket_connect_timeout=0.3,
            )
            cached_json = _rc.get(cache_key)
            if cached_json:
                result = json.loads(cached_json)
                spoken_response = result.get("spoken_response", "")
                route_action    = result.get("action", "none")
                is_emergency    = result.get("is_emergency", False)
                logger.info("VoiceAgent: cache HIT (turn=%d key=%s)", turn_count, cache_key[-10:])
                cache_hit = True
        except Exception:
            pass  # Redis unavailable — fall through to LLM

        if not cache_hit:
            try:
                llm = _get_llm(turn_count=turn_count, temperature=0.3)
                prompt = VOICE_ROUTING_PROMPT.format(
                    transcript=transcript,
                    entities=json.dumps(entities[:10], indent=2),
                    intent=intent,
                    patient_context=json.dumps(patient_ctx, indent=2)[:500],
                    session_summary=session_summary[:300],
                    urgency_flags=json.dumps(urgency_flags),
                    language=language,
                )
                response = llm.invoke(
                    [SystemMessage(content=AI_DOCTOR_SYSTEM_PROMPT),
                     HumanMessage(content=prompt)],
                )
                result = json.loads(_extract_text(response))
                spoken_response = result.get("spoken_response", "")
                route_action = result.get("action", "none")
                is_emergency = result.get("is_emergency", False)

                # Cache for 1 hour — skip LLM on identical future queries
                try:
                    if _rc:
                        _rc.setex(cache_key, _RESPONSE_CACHE_TTL, json.dumps(result))
                except Exception:
                    pass

                # Optionally route to orchestrator for complex intents
                if route_action.startswith("route_to_") and not is_emergency:
                    route_payload = result.get("route_payload", {})
                    orchestrator_response = self._route_to_orchestrator(
                        intent=route_payload.get("intent", intent),
                        transcript=transcript,
                        session_id=state.get("session_id"),
                        patient_id=state.get("patient_id"),
                        context={**route_payload.get("context", {}), "patient": patient_ctx},
                    )
                    if orchestrator_response and orchestrator_response.get("content"):
                        spoken_response = orchestrator_response["content"]

            except Exception as exc:
                logger.error("VoiceAgent: process_voice_command LLM failed: %s", exc)
                spoken_response = (
                    "I'm sorry, I'm having trouble processing that right now. "
                    "Could you please repeat that or try again in a moment?"
                )

        if not spoken_response:
            spoken_response = "I heard you. Could you tell me more about what you're experiencing?"

        # Save spoken response to session history
        session_history.append({
            "role": "assistant",
            "transcript": spoken_response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            **state,
            "spoken_response": spoken_response,
            "route_action": route_action,
            "is_emergency": route_action == "route_to_triage",
            "orchestrator_response": orchestrator_response,
            "session_history": session_history,
        }


    def _route_to_orchestrator(
        self,
        intent: str,
        transcript: str,
        session_id: Optional[str],
        patient_id: Optional[str],
        context: dict,
    ) -> Optional[dict]:
        """Silently invoke the orchestrator for complex intents."""
        try:
            from app.services.agent_orchestrator_service import OrchestratorService
            result = OrchestratorService.process_message(
                message=transcript,
                patient_id=patient_id,
                session_id=session_id,
                context={**context, "intent_override": intent, "source": "voice"},
            )
            return result.get("final_response")
        except Exception as exc:
            logger.warning("VoiceAgent: orchestrator routing failed: %s", exc)
            return None

    def _trigger_emergency_triage(self, state: VoiceState, transcript: str) -> None:
        """Fire-and-forget emergency triage trigger."""
        try:
            from app.agents.triage_agent import run_triage
            import threading
            t = threading.Thread(
                target=run_triage,
                kwargs={
                    "chief_complaint": transcript,
                    "patient_id": state.get("patient_id"),
                    "vital_signs": state.get("context", {}).get("vital_signs"),
                    "patient_context": state.get("context", {}).get("patient", {}),
                    "session_id": state.get("session_id"),
                },
                daemon=True,
            )
            t.start()
        except Exception as exc:
            logger.error("VoiceAgent: background triage trigger failed: %s", exc)

    # ─────────────────────────────────────────────────────────────────────
    # Node 7: synthesize_speech — Google Cloud TTS WaveNet (language-aware)
    # ─────────────────────────────────────────────────────────────────────

    def _synthesize_speech(self, state: VoiceState) -> VoiceState:
        """
        Convert spoken_response text to MP3 audio using Google Cloud Text-to-Speech.
        Automatically selects the correct WaveNet voice based on detected language.
        Replaces: ElevenLabs TTS.
        Output is base64-encoded for WebSocket transport.
        """
        spoken_response = state.get("spoken_response", "")
        is_emergency = state.get("is_emergency", False)
        detected_language = state.get("detected_language", "en")

        if not spoken_response.strip():
            return {**state, "audio_response_b64": None, "audio_response_bytes": None}

        lang_code, voice_name, ssml_gender = get_google_tts_voice(
            detected_language, is_emergency=is_emergency
        )

        audio_bytes = None
        audio_b64 = None

        # ── Primary: Google Cloud TTS client library (pre-warmed singleton) ──
        try:
            from google.cloud import texttospeech as tts_lib

            # Use the module-level singleton — avoids gRPC setup cost per request
            tts_client = _get_tts_client()
            if tts_client is None:
                raise ImportError("TTS singleton unavailable")

            synthesis_input = tts_lib.SynthesisInput(text=spoken_response[:5000])
            voice_params = tts_lib.VoiceSelectionParams(
                language_code=lang_code,
                name=voice_name,
                ssml_gender=getattr(tts_lib.SsmlVoiceGender, ssml_gender, tts_lib.SsmlVoiceGender.FEMALE),
            )
            audio_config = tts_lib.AudioConfig(
                audio_encoding=tts_lib.AudioEncoding.MP3,
                speaking_rate=EMERGENCY_TTS_SPEED if is_emergency else DEFAULT_TTS_SPEED,
                pitch=0.0,
            )

            tts_response = tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )
            audio_bytes = tts_response.audio_content
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            logger.info(
                "VoiceAgent: Google Cloud TTS synthesized %d bytes (lang=%s voice=%s)",
                len(audio_bytes), lang_code, voice_name,
            )

        except ImportError:
            logger.warning("VoiceAgent: google-cloud-texttospeech not installed — falling back to REST API")
            audio_bytes, audio_b64 = self._google_tts_rest(
                spoken_response, lang_code, voice_name, ssml_gender, is_emergency
            )
        except Exception as exc:
            logger.error("VoiceAgent: Google Cloud TTS failed: %s — trying REST fallback", exc)
            audio_bytes, audio_b64 = self._google_tts_rest(
                spoken_response, lang_code, voice_name, ssml_gender, is_emergency
            )

        return {
            **state,
            "audio_response_b64": audio_b64,
            "audio_response_bytes": audio_bytes,
            "tts_voice": voice_name,
        }

    def _google_tts_rest(
        self,
        text: str,
        lang_code: str,
        voice_name: str,
        ssml_gender: str,
        is_emergency: bool,
    ) -> tuple[Optional[bytes], Optional[str]]:
        """
        Fallback: call Google Cloud TTS REST API using GOOGLE_API_KEY.
        Works without a service account when using the Gemini API key.
        """
        import requests as _req, json as _json
        api_key = _GOOGLE_KEY
        if not api_key:
            logger.error("VoiceAgent: no GOOGLE_API_KEY for TTS REST fallback")
            return None, None

        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
        payload = {
            "input": {"text": text[:5000]},
            "voice": {"languageCode": lang_code, "name": voice_name, "ssmlGender": ssml_gender},
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": EMERGENCY_TTS_SPEED if is_emergency else DEFAULT_TTS_SPEED,
            },
        }
        try:
            resp = _req.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                audio_b64 = resp.json().get("audioContent", "")
                audio_bytes = base64.b64decode(audio_b64) if audio_b64 else None
                logger.info(
                    "VoiceAgent: Google TTS REST synthesized %d bytes (voice=%s)",
                    len(audio_bytes) if audio_bytes else 0, voice_name,
                )
                return audio_bytes, audio_b64
            else:
                logger.error("VoiceAgent: Google TTS REST HTTP %s: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.error("VoiceAgent: Google TTS REST failed: %s", exc)
        return None, None

    # ─────────────────────────────────────────────────────────────────────
    # Node 8: stream_audio_response
    # ─────────────────────────────────────────────────────────────────────

    def _stream_audio_response(self, state: VoiceState) -> VoiceState:
        """
        Emit the TTS audio + transcript to the client via Socket.IO.
        The WebSocket handler calls this after graph execution, but we also
        store the result in state so the REST endpoint can return it directly.
        """
        audio_b64 = state.get("audio_response_b64")
        transcript = state.get("transcript", "")
        spoken_response = state.get("spoken_response", "")
        session_id = state.get("session_id")
        is_emergency = state.get("is_emergency", False)
        entities = state.get("entities", [])
        intent = state.get("primary_intent", "unknown")

        # Build the response payload (used by both WS emit and REST return)
        response_payload = {
            "session_id": session_id,
            "transcript": transcript,
            "spoken_response": spoken_response,
            "audio_b64": audio_b64,
            "audio_format": "mp3",
            "language": state.get("detected_language", "en"),
            "intent": intent,
            "entities": entities[:10],   # trim to save bandwidth
            "urgency_flags": state.get("urgency_flags", []),
            "is_emergency": is_emergency,
            "route_action": state.get("route_action", "none"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Emit via Socket.IO if session_id is in an active room
        try:
            from app.websocket import socketio
            socketio.emit(
                "voice_response",
                response_payload,
                room=f"voice:{session_id}",
                namespace="/voice",
            )
            logger.debug("VoiceAgent: voice_response emitted to room voice:%s", session_id)
        except Exception as exc:
            logger.debug("VoiceAgent: Socket.IO emit skipped (not in WS context): %s", exc)

        # Persist turn to DB
        self._persist_voice_turn(state, transcript, spoken_response)

        # Assemble final_response for REST API layer
        final = {
            "type": "voice",
            "session_id": session_id,
            "transcript": transcript,
            "spoken_response": spoken_response,
            "audio_b64": audio_b64,
            "audio_format": "mp3",
            "language": state.get("detected_language", "en"),
            "intent": intent,
            "entities": entities,
            "is_emergency": is_emergency,
            "route_action": state.get("route_action", "none"),
        }

        return {**state, "final_response": final}

    def _persist_voice_turn(
        self, state: VoiceState, transcript: str, response: str
    ) -> None:
        """Write voice turn to the conversations table for history."""
        try:
            from app.models.db import db
            from sqlalchemy import text
            db.session.execute(
                text("""
                    INSERT INTO voice_sessions
                        (id, session_id, patient_id, session_mode, transcript,
                         spoken_response, intent, language, is_emergency, created_at)
                    VALUES
                        (:id, :session_id, :patient_id, :session_mode, :transcript,
                         :spoken_response, :intent, :language, :is_emergency, :created_at)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": state.get("session_id"),
                    "patient_id": state.get("patient_id"),
                    "session_mode": state.get("session_mode", "patient"),
                    "transcript": transcript[:2000],
                    "spoken_response": response[:2000],
                    "intent": state.get("primary_intent", "unknown"),
                    "language": state.get("detected_language", "en"),
                    "is_emergency": state.get("is_emergency", False),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            db.session.commit()
        except Exception as exc:
            logger.debug("VoiceAgent: voice turn persist skipped: %s", exc)
            try:
                from app.models.db import db
                db.session.rollback()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

_voice_agent_instance: Optional[VoiceAgent] = None


def get_voice_agent() -> VoiceAgent:
    """Return the compiled VoiceAgent (singleton)."""
    global _voice_agent_instance
    if _voice_agent_instance is None:
        _voice_agent_instance = VoiceAgent(model=_GEMINI_MODEL, temperature=0)
        logger.info("VoiceAgent: instance compiled (model=%s)", _GEMINI_MODEL)
    return _voice_agent_instance


def process_voice_turn(
    audio_data: bytes,
    session_id: str,
    patient_id: Optional[str] = None,
    audio_format: str = "webm",
    session_mode: str = "patient",
    language_hint: Optional[str] = None,
    patient_context: Optional[dict] = None,
) -> dict:
    """
    Convenience function: process one audio chunk through the full pipeline.
    Returns final_response dict.
    """
    initial_state: VoiceState = {
        "messages": [],
        "patient_id": patient_id or "",
        "session_id": session_id,
        "intent": "voice",
        "context": {"patient": patient_context or {}},
        "tool_outputs": [],
        "final_response": None,
        "error": None,
        # Voice-specific
        "audio_data": audio_data,
        "audio_format": audio_format,
        "session_mode": session_mode,
        "language_hint": language_hint,
        "transcript": "",
        "entities": [],
        "urgency_flags": [],
        "is_emergency": False,
        "session_history": [],
        "session_summary": "",
        "accumulated_soap": {},
    }

    agent = get_voice_agent()
    result = agent.invoke(initial_state)
    return result.get("final_response") or {}


def log_ambient_consent(
    patient_id: str,
    doctor_id: str,
    session_id: str,
    consent_given: bool,
) -> None:
    """Persist ambient mode consent record to DB (required for compliance)."""
    try:
        from app.models.db import db
        from sqlalchemy import text
        db.session.execute(
            text("""
                INSERT INTO ambient_consent_log
                    (id, patient_id, doctor_id, session_id, consent_given, logged_at)
                VALUES (:id, :pid, :did, :sid, :consent, :now)
                ON CONFLICT (session_id) DO UPDATE SET
                    consent_given = EXCLUDED.consent_given,
                    logged_at = EXCLUDED.logged_at
            """),
            {
                "id": str(uuid.uuid4()),
                "pid": patient_id,
                "did": doctor_id,
                "sid": session_id,
                "consent": consent_given,
                "now": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.session.commit()
        logger.info(
            "VoiceAgent: ambient consent logged — patient=%s doctor=%s session=%s consent=%s",
            patient_id, doctor_id, session_id, consent_given,
        )
    except Exception as exc:
        logger.error("VoiceAgent: consent log failed: %s", exc)
        try:
            from app.models.db import db
            db.session.rollback()
        except Exception:
            pass


def process_voice_turn_with_symptom_analysis(
    audio_data: bytes,
    session_id: str,
    patient_id: Optional[str] = None,
    audio_format: str = "webm",
    language_hint: Optional[str] = None,
    patient_context: Optional[dict] = None,
) -> dict:
    """
    AI Doctor pipeline: VoiceAgent (STT + TTS) + SymptomAnalystAgent (medical interview).
    
    Returns enriched response dict with:
      - transcript, spoken_response, audio_b64, language (from VoiceAgent)
      - symptom_summary, differential, recommended_tests, phase (from SymptomAnalyst)
    """
    import json as _json

    # Step 1: Run the full voice pipeline (STT → NER → LLM response → TTS)
    voice_result = process_voice_turn(
        audio_data=audio_data,
        session_id=session_id,
        patient_id=patient_id,
        audio_format=audio_format,
        session_mode="patient",
        language_hint=language_hint,
        patient_context=patient_context,
    )

    transcript = voice_result.get("transcript", "")
    entities = voice_result.get("entities", [])
    detected_language = voice_result.get("language", "en")
    is_emergency = voice_result.get("is_emergency", False)

    # Step 2: Run SymptomAnalyst if we have a real transcript
    symptom_data = {
        "symptoms": [e.get("text", e.get("value", "")) for e in entities if e.get("category") in ("symptom", "symptom_duration", "body_part")],
        "urgency": "emergency" if is_emergency else "routine",
        "differential": None,
        "recommended_tests": [],
        "phase": "intake",
        "turn": 1,
    }

    if transcript.strip() and not is_emergency:
        try:
            from langchain_core.messages import HumanMessage
            from app.agents.symptom_analyst import SymptomAnalystAgent

            # Load Redis history to build multi-turn messages
            redis_history = []
            try:
                import redis as _redis, os as _os
                r = _redis.Redis(
                    host=_os.getenv("REDIS_HOST", "localhost"),
                    port=int(_os.getenv("REDIS_PORT", 6379)),
                    db=int(_os.getenv("REDIS_DB", 0)),
                    decode_responses=True,
                )
                raw = r.get(f"vitalmind:voice:{session_id}")
                if raw:
                    history = _json.loads(raw).get("history", [])
                    for turn in history[-8:]:  # Last 8 turns as context
                        if turn.get("transcript", "").strip():
                            if turn.get("role") == "patient":
                                redis_history.append(HumanMessage(content=turn["transcript"]))
                            else:
                                from langchain_core.messages import AIMessage
                                redis_history.append(AIMessage(content=turn["transcript"]))
            except Exception:
                redis_history = [HumanMessage(content=transcript)]

            if not redis_history:
                redis_history = [HumanMessage(content=transcript)]

            # Gemini strictly requires alternating Human/AI turns. Connect consecutive same-role messages:
            merged_history = []
            for msg in redis_history:
                if not merged_history:
                    merged_history.append(msg)
                elif type(merged_history[-1]) == type(msg):
                    merged_history[-1].content += " " + msg.content
                else:
                    merged_history.append(msg)

            # Select model by turn count: Flash for early conv, Pro for deep diagnosis
            _symptom_turn_count = max(0, len(redis_history) - 1)
            _symptom_model = _GEMINI_MODEL if _symptom_turn_count >= 4 else _GEMINI_FLASH
            symptom_agent = SymptomAnalystAgent(model=_symptom_model, temperature=0.2)
            symptom_state = {
                "messages": merged_history,
                "patient_id": patient_id or "",
                "session_id": session_id,
                "intent": "symptom_check",
                "context": {
                    "patient": patient_context or {},
                    "turn_count": max(0, len(redis_history) - 1),
                    "language": detected_language,
                },
                "tool_outputs": [],
                "final_response": None,
                "error": None,
            }

            symptom_result = symptom_agent.invoke(symptom_state)
            fr = symptom_result.get("final_response") or {}
            ctx = symptom_result.get("context", {})

            differential = ctx.get("differential")
            phase = fr.get("phase", "intake")

            # Extract recommended tests from differential
            tests = []
            if differential:
                tests = differential.get("recommended_tests", [])
                if not tests:
                    tests = differential.get("investigations", [])

            # Always use the Symptom Analyst's specialized medical response if available
            agent_response_text = fr.get("content", "")
            if agent_response_text and agent_response_text.strip():
                voice_result["spoken_response"] = agent_response_text
                # Re-run TTS using Google Cloud TTS for the specialist response
                try:
                    import base64 as _b64
                    lang = detected_language or "en"
                    lang_code, voice_name, ssml_gender = get_google_tts_voice(lang, is_emergency=False)
                    agent = get_voice_agent()
                    tts_bytes, tts_b64 = agent._google_tts_rest(
                        agent_response_text[:3000], lang_code, voice_name, ssml_gender, False
                    )
                    if tts_b64:
                        voice_result["audio_b64"] = tts_b64
                        logger.info("AI Doctor: Google TTS re-synthesis OK (voice=%s)", voice_name)
                except Exception as tts_exc:
                    logger.warning("AI Doctor: Google TTS re-synthesis skipped: %s", tts_exc)

            symptom_data = {
                "symptoms": symptom_data["symptoms"],
                "urgency": fr.get("urgency", "routine"),
                "differential": differential,
                "recommended_tests": tests,
                "phase": phase,
                "turn": fr.get("turn", 1),
                "specialist": ctx.get("recommended_specialist"),
            }

        except Exception as exc:
            logger.warning("AI Doctor: SymptomAnalyst chain failed (non-fatal): %s", exc)

    # Merge and return unified response
    return {
        **voice_result,
        "symptom_summary": symptom_data,
        "is_ai_doctor": True,
    }
