"""
gemini_live_service.py — Modular voice pipeline for AI Doctor.

Pipeline per turn:
  1. STT  : Groq Whisper API  (audio/webm or raw PCM → transcript)
  2. LLM  : gemini-2.5-flash-preview  (NO thinking, single JSON call)
  3. TTS  : ElevenLabs streaming     (text → MP3 chunks)

Transport: Socket.IO  /voice  namespace (binary-friendly).

WebSocket contract (unchanged from Gemini Live era):
  ← emit  live_session_ready   {session_id}
  ← emit  live_audio_chunk     {session_id, chunk_index, audio_b64, audio_format, sample_rate}
  ← emit  live_turn_complete   {session_id, chunk_count, turn}
  ← emit  voice_error          {detail, session_id}
  → recv  audio_chunk          raw PCM bytes (ArrayBuffer) or {audio_b64}
  → recv  audio_turn_complete  (VAD end-of-speech signal)
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
_GOOGLE_KEY      = os.getenv("GOOGLE_API_KEY", "")
_GROQ_KEY        = os.getenv("GROQ_API_KEY", "")
_ELEVEN_KEY      = os.getenv("ELEVENLABS_API_KEY", "")
_ELEVEN_VOICE    = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Rachel
_LLM_MODEL       = "gemini-2.5-flash"                            # NO thinking
_SUMMARY_MODEL   = "gemini-2.5-flash"
_CONTEXT_WINDOW  = 4          # max turns kept in rolling context
_MIN_PCM_BYTES   = 512        # ignore tiny/silence-only buffers

# ─── System Prompt ───────────────────────────────────────────────────────────
DOCTOR_SYSTEM_PROMPT = """You are Dr. Janvi, a compassionate, warm, and highly knowledgeable AI doctor for the VitalMind healthcare platform.

You are in a REAL-TIME VOICE CONVERSATION with a patient. Rules:

LANGUAGE:
- Detect the language the patient is speaking (English, Hindi, Tamil, Telugu, etc.)
- Always respond in the SAME language as the patient
- Support Hinglish (mixed Hindi+English) naturally

CONVERSATION PHASES:
- Turns 0-2 (INTAKE): Greet patient by name on very first turn only. Ask one open-ended question about their main complaint.
- Turns 3-5 (INTERVIEW): Ask ONE targeted OPQRST follow-up per turn. Never repeat questions already answered.
- Turn 6+ (DIAGNOSIS): STOP asking questions. Give: likely diagnosis (2-3 options), specific tests needed (CBC, ECG etc.), urgency level (ROUTINE/URGENT/EMERGENCY), which specialist to see, safe home care steps.

CLOSING: If patient says thank you / bye / shukriya / goodbye → respond warmly and end the conversation.

EMERGENCY: If patient mentions chest pain, can't breathe, stroke symptoms → immediately give emergency instructions.

STYLE:
- Keep responses short and conversational (under 80 words for follow-ups, under 150 words for diagnosis)
- Be warm, empathetic, and professional
- Ask ONE question at a time, never multiple"""


# ─── JSON schema the LLM must return ────────────────────────────────────────
_RESPONSE_SCHEMA = """{
  "language": "<ISO 639-1 code, e.g. en|hi|ta|te|mr>",
  "patient_transcript": "<verbatim or cleaned-up transcript of what the patient said>",
  "spoken_response": "<Dr. Janvi's full reply, TTS-ready, no markdown>",
  "entities": {
    "symptoms": ["<symptom>"],
    "medications": ["<medication>"],
    "urgency": "<routine|moderate|urgent|emergency>"
  },
  "phase": "<initial_intake|followup_interview|diagnose|emergency_triage>"
}"""


# ─────────────────────────────────────────────────────────────────────────────
# ModularVoiceSession  (drop-in replacement for GeminiLiveSession)
# ─────────────────────────────────────────────────────────────────────────────

class ModularVoiceSession:
    """
    Manages one modular STT→LLM→TTS voice session.

    Public API is identical to the old GeminiLiveSession:
        session = ModularVoiceSession(session_id, patient_name, patient_context, emit_fn, turn_count)
        session.start()
        session.send_audio(pcm_bytes)
        session.end_turn()
        session.close()
        session.get_transcript()
    """

    def __init__(
        self,
        session_id: str,
        patient_name: str,
        patient_context: dict,
        emit_fn: Callable,
        turn_count: int = 0,
        language: str = "en",
    ):
        self.session_id      = session_id
        self.patient_name    = patient_name
        self.patient_context = patient_context
        self.emit_fn         = emit_fn          # socketio.emit partially applied to sid
        self.turn_count      = turn_count
        self.language        = language

        self._audio_buffer: list[bytes] = []    # accumulate PCM chunks per turn
        self._cmd_queue: deque = deque()         # "END_TURN" | None (close sentinel)
        self._closed   = False
        self._lock     = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Rolling context: list of {"role": "patient"|"doctor", "text": "..."}
        self._history: list[dict] = []
        self._history_summary: str = ""

        # Transcript parts for DB save
        self._transcript_parts: list[str] = []

        # Build patient context string once
        ctx_lines = []
        if patient_name:
            ctx_lines.append(f"Patient name: {patient_name}")
        if age := patient_context.get("age"):
            ctx_lines.append(f"Age: {age}")
        if conds := patient_context.get("chronic_conditions"):
            ctx_lines.append(f"Known conditions: {', '.join(conds) if isinstance(conds, list) else conds}")
        if meds := patient_context.get("current_medications"):
            m_str = ', '.join([m.get('name', str(m)) if isinstance(m, dict) else str(m) for m in meds]) if isinstance(meds, list) else str(meds)
            ctx_lines.append(f"Current medications: {m_str}")
        if allgs := patient_context.get("allergies"):
            ctx_lines.append(f"Allergies: {', '.join(allgs) if isinstance(allgs, list) else allgs}")
        self._patient_ctx_str = "\n".join(ctx_lines) if ctx_lines else "No patient profile available"

        # Out-event queue (background thread → Socket.IO drain thread)
        self._out_events: list[tuple] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Start background threads: event-drain thread + main async loop thread."""
        threading.Thread(target=self._drain_events, daemon=True, name=f"voice-drain-{self.session_id[:8]}").start()
        threading.Thread(target=self._run_loop,     daemon=True, name=f"voice-loop-{self.session_id[:8]}").start()
        logger.info("ModularVoice: session %s started", self.session_id)

    def send_audio(self, pcm_bytes: bytes):
        """Append PCM audio chunk to the current-turn buffer."""
        if not self._closed and len(pcm_bytes) >= _MIN_PCM_BYTES:
            with self._lock:
                self._audio_buffer.append(pcm_bytes)

    def end_turn(self):
        """Signal that the user has finished speaking — trigger STT→LLM→TTS."""
        if not self._closed:
            self._cmd_queue.append("END_TURN")

    def close(self):
        """Shut down the session."""
        if not self._closed:
            self._closed = True
            self._cmd_queue.append(None)   # sentinel
            logger.info("ModularVoice: session %s close requested", self.session_id)

    def get_transcript(self) -> list[str]:
        return list(self._transcript_parts)

    # ── Background threads ────────────────────────────────────────────────────

    def _drain_events(self):
        """Forward queued events from background threads → Socket.IO via the captured emit_fn.
        
        IMPORTANT: self.emit_fn is the only correct way to send to this specific client.
        Using socketio.emit() without 'to=sid' broadcasts to ALL /voice clients.
        The emit_fn closure captures the SID string at session creation time.
        """
        import time
        try:
            while not self._closed:
                while self._out_events:
                    event, data = self._out_events.pop(0)
                    try:
                        self.emit_fn(event, data)
                    except Exception as exc:
                        logger.error("ModularVoice: emit failed for %s: %s", event, exc)
                time.sleep(0.01)
        except Exception as exc:
            logger.error("ModularVoice: drain thread crashed: %s", exc)

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._main_loop())
        except Exception as exc:
            logger.error("ModularVoice: loop error for session %s: %s", self.session_id, exc)
            self._safe_emit("voice_error", {"detail": f"Voice session error: {exc}", "session_id": self.session_id})
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def _main_loop(self):
        """Main async loop: wait for END_TURN commands, then run pipeline."""
        # Signal frontend immediately — session is ready
        self._safe_emit("live_session_ready", {"session_id": self.session_id})
        logger.info("ModularVoice: session %s ready (STT+LLM+TTS pipeline)", self.session_id)

        while not self._closed:
            # Poll command queue
            if not self._cmd_queue:
                await asyncio.sleep(0.02)
                continue

            cmd = self._cmd_queue.popleft()
            if cmd is None:
                # Close sentinel
                break

            if cmd == "END_TURN":
                # Drain audio buffer
                with self._lock:
                    audio_chunks = list(self._audio_buffer)
                    self._audio_buffer.clear()

                if not audio_chunks:
                    logger.debug("ModularVoice: END_TURN with empty buffer — skipping")
                    continue

                pcm_bytes = b"".join(audio_chunks)
                logger.info(
                    "ModularVoice: END_TURN — %d bytes PCM, turn %d",
                    len(pcm_bytes), self.turn_count,
                )

                try:
                    await self._run_pipeline(pcm_bytes)
                except Exception as exc:
                    logger.error("ModularVoice: pipeline error: %s", exc)
                    self._safe_emit("voice_error", {
                        "detail": "Processing error. Please try again.",
                        "session_id": self.session_id,
                    })

        logger.info("ModularVoice: session %s main loop exited", self.session_id)
        self._safe_emit("live_session_ended", {"session_id": self.session_id})

    # ── Pipeline stages ───────────────────────────────────────────────────────

    async def _run_pipeline(self, pcm_bytes: bytes):
        """STT → LLM → TTS for one turn."""
        import time

        # ── Stage 1: STT (Groq Whisper) ───────────────────────────────────────
        t0 = time.time()
        transcript = await self._stt_groq(pcm_bytes)
        t_stt = time.time() - t0
        
        if not transcript or not transcript.strip():
            logger.info("ModularVoice: STT returned empty transcript — skipping turn (STT time: %.2fs)", t_stt)
            self._safe_emit("turn_skipped", {"session_id": self.session_id})
            return
        logger.info("ModularVoice: STT → %r (time: %.2fs)", transcript[:80], t_stt)

        # ── Stage 2: LLM (Gemini Flash, no thinking) ──────────────────────────
        t1 = time.time()
        llm_result = await self._llm_gemini(transcript)
        t_llm = time.time() - t1
        
        spoken_response = llm_result.get("spoken_response", "")
        language        = llm_result.get("language", "en")
        patient_text    = llm_result.get("patient_transcript", transcript)
        phase           = llm_result.get("phase", "initial_intake")

        if not spoken_response:
            logger.warning("ModularVoice: LLM returned no spoken_response (time: %.2fs)", t_llm)
            self._safe_emit("turn_skipped", {"session_id": self.session_id})
            return

        logger.info("ModularVoice: LLM → %r (time: %.2fs)", spoken_response[:80], t_llm)

        # Save transcripts for DB
        self._transcript_parts.append(f"Patient: {patient_text}")
        self._transcript_parts.append(f"Dr. Janvi: {spoken_response}")

        # Update rolling history
        self._history.append({"role": "patient", "text": patient_text})
        self._history.append({"role": "doctor",  "text": spoken_response})

        # Trim context window (keep last N*2 messages)
        if len(self._history) > _CONTEXT_WINDOW * 2:
            self._history = self._history[-((_CONTEXT_WINDOW) * 2):]

        # Emit text turn to frontend (populates chat feed)
        self._safe_emit("voice_turn_text", {
            "session_id":       self.session_id,
            "turn":             self.turn_count,
            "patient_text":     patient_text,
            "doctor_text":      spoken_response,
            "language":         language,
            "phase":            phase,
            "entities":         llm_result.get("entities", {}),
        })

        # ── Stage 3: TTS — delegated to browser (frontend calls ElevenLabs) ────
        # The browser receives tts_request, calls ElevenLabs with its own IP
        # (not Render's datacenter IP), and plays the audio directly.
        # This bypasses ElevenLabs Free Tier datacenter IP blocks.
        t2 = time.time()
        self._safe_emit("tts_request", {
            "session_id": self.session_id,
            "text":       spoken_response,
            "turn":       self.turn_count,
            "voice_id":   _ELEVEN_VOICE,
        })
        t_tts = time.time() - t2  # just event emit time (negligible)

        t_total = t_stt + t_llm + t_tts
        logger.info("ModularVoice: Turn %d completed in %.2fs (STT: %.2fs, LLM: %.2fs, TTS: browser)",
                    self.turn_count, t_total, t_stt, t_llm)

        # Signal turn complete — audio is playing in browser, backend is done
        self._safe_emit("live_turn_complete", {
            "session_id": self.session_id,
            "chunk_count": 0,   # browser owns audio now
            "turn":        self.turn_count,
            "latency_ms":  int(t_total * 1000),
        })
        self.turn_count += 1

    async def _stt_groq(self, pcm_bytes: bytes) -> str:
        """Transcribe PCM audio via Groq Whisper. Returns transcript string."""
        try:
            from groq import AsyncGroq

            client = AsyncGroq(api_key=_GROQ_KEY)

            # Groq Whisper accepts audio files — wrap PCM in a WAV container
            wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate=16000, channels=1, bit_depth=16)

            # Use language from session config to force Whisper out of misdetecting echo
            transcription = await client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
                response_format="text",
                language=self.language,
                temperature=0.0,
            )
            # Groq returns a plain string when response_format="text"
            if isinstance(transcription, str):
                return transcription.strip()
            # Some versions return an object
            return getattr(transcription, "text", str(transcription)).strip()

        except Exception as exc:
            logger.error("ModularVoice: STT error: %s", exc)
            return ""

    async def _llm_gemini(self, transcript: str) -> dict:
        """
        Single Gemini Flash call returning structured JSON.
        No thinking mode (thinking_budget=0).
        Includes rolling conversation context.
        """
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=_GOOGLE_KEY)

            # Build conversation history block
            history_block = ""
            if self._history:
                lines = []
                for msg in self._history:
                    role = "Patient" if msg["role"] == "patient" else "Dr. Janvi"
                    lines.append(f"{role}: {msg['text']}")
                history_block = "\n".join(lines)
                if self._history_summary:
                    history_block = f"[Earlier summary: {self._history_summary}]\n\n" + history_block
                history_block = f"\n\nCONVERSATION HISTORY (last {_CONTEXT_WINDOW} turns):\n{history_block}"

            turn_label = (
                "initial_intake"     if self.turn_count < 3 else
                "followup_interview" if self.turn_count < 6 else
                "diagnose"
            )

            prompt = f"""{DOCTOR_SYSTEM_PROMPT}

PATIENT PROFILE:
{self._patient_ctx_str}
{history_block}

CURRENT TURN: {self.turn_count}  |  PHASE: {turn_label}

Patient just said: "{transcript}"

Respond as Dr. Janvi following the conversation phase rules above.
CRITICAL: You MUST respond in the language corresponding to language code: "{self.language}".
Return ONLY valid JSON matching this schema exactly:
{_RESPONSE_SCHEMA}"""

            response = await client.aio.models.generate_content(
                model=_LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=512,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    response_mime_type="application/json",
                ),
            )

            raw = response.text or "{}"
            # Strip markdown fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            return json.loads(raw)

        except json.JSONDecodeError as exc:
            logger.error("ModularVoice: LLM JSON parse error: %s — raw: %s", exc, raw[:200])
            return {"spoken_response": "I'm sorry, I couldn't process that. Could you repeat?", "language": "en"}
        except Exception as exc:
            logger.error("ModularVoice: LLM error: %s", exc)
            return {"spoken_response": "I'm having a technical issue. Please try again.", "language": "en"}

    async def _tts_elevenlabs(self, text: str) -> int:
        """
        Stream ElevenLabs TTS using v2 SDK: client.text_to_speech.stream()
        Emits each MP3 chunk immediately as live_audio_chunk.
        Returns total chunk count emitted.
        """
        chunk_index = 0
        try:
            from elevenlabs.client import AsyncElevenLabs
            try:
                from elevenlabs.types import VoiceSettings
            except ImportError:
                from elevenlabs import VoiceSettings  # older SDK fallback

            client = AsyncElevenLabs(api_key=_ELEVEN_KEY)

            # text_to_speech.stream() returns AsyncIterator[bytes]
            audio_stream = client.text_to_speech.stream(
                voice_id=_ELEVEN_VOICE,
                text=text,
                model_id="eleven_turbo_v2_5",             # lowest-latency model
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True,
                ),
                output_format="pcm_22050",              # Raw PCM for gapless streaming without MP3 artifacts
                optimize_streaming_latency=4,              # max latency optimization (0-4)
            )

            try:
                async for chunk in audio_stream:
                    if self._closed:
                        break
                    if isinstance(chunk, bytes) and len(chunk) > 0:
                        self._safe_emit("live_audio_chunk", {
                            "session_id":  self.session_id,
                            "chunk_index": chunk_index,
                            "audio_b64":   base64.b64encode(chunk).decode(),
                            "audio_format": "pcm16",
                            "sample_rate": 22050,
                            "channels":    1,
                            "bit_depth":   16,
                        })
                        chunk_index += 1
            finally:
                if hasattr(audio_stream, "aclose"):
                    try:
                        await audio_stream.aclose()
                    except Exception:
                        pass


        except Exception as exc:
            err_str = str(exc)
            # ElevenLabs Free Tier blocks datacenter IPs (401 / detected_unusual_activity).
            # Instead of showing an error, emit the text so the frontend can speak it
            # using the browser's built-in Web Speech API (runs client-side, no IP issue).
            if "401" in err_str or "unusual_activity" in err_str or "Free Tier" in err_str:
                logger.warning(
                    "ModularVoice: ElevenLabs blocked (datacenter IP / free-tier limit). "
                    "Falling back to browser TTS."
                )
                self._safe_emit("tts_fallback", {
                    "session_id": self.session_id,
                    "text":       text,
                    "chunk_index": chunk_index,
                })
            else:
                logger.error("ModularVoice: TTS error: %s", exc)
                self._safe_emit("voice_error", {
                    "detail": "Text-to-speech error. Audio synthesis failed.",
                    "session_id": self.session_id,
                })

        return chunk_index

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _safe_emit(self, event: str, data: dict):
        """Thread-safe: queue event for the drain thread."""
        self._out_events.append((event, data))


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat alias (voice_stream.py imports GeminiLiveSession)
# ─────────────────────────────────────────────────────────────────────────────

GeminiLiveSession = ModularVoiceSession   # alias so voice_stream.py needs zero changes


# ─────────────────────────────────────────────────────────────────────────────
# WAV wrapper utility
# ─────────────────────────────────────────────────────────────────────────────

def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, bit_depth: int = 16) -> bytes:
    """Wrap raw PCM bytes in a minimal WAV container (no external deps)."""
    import struct
    num_samples     = len(pcm_bytes) // (bit_depth // 8)
    byte_rate       = sample_rate * channels * bit_depth // 8
    block_align     = channels * bit_depth // 8
    subchunk2_size  = len(pcm_bytes)
    chunk_size      = 36 + subchunk2_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE",
        b"fmt ", 16,
        1,              # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bit_depth,
        b"data", subchunk2_size,
    )
    return header + pcm_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Post-session DB save (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def save_session_to_db(
    session_id: str,
    patient_id: str,
    transcript_parts: list[str],
    patient_context: dict,
) -> dict:
    """
    Called on session end.
    1. Join transcript parts into full text
    2. Run Gemini Flash to extract symptoms + generate summary
    3. Save to conversations table
    Returns the summary dict.
    """
    if not transcript_parts:
        return {}

    full_text = "\n".join(transcript_parts)
    logger.info("ModularVoice: saving session %s (%d chars)", session_id, len(full_text))

    try:
        from google import genai
        client = genai.Client(api_key=_GOOGLE_KEY)

        summary_prompt = f"""You are a medical record assistant. Analyze this AI doctor conversation and extract:

Conversation:
{full_text[:4000]}

Patient profile: {json.dumps(patient_context)}

Return JSON with:
{{
  "summary": "2-3 sentence clinical summary",
  "symptoms": ["list", "of", "symptoms mentioned"],
  "diagnosis_options": ["possible diagnosis 1", "possible diagnosis 2"],
  "recommended_tests": ["test 1", "test 2"],
  "urgency": "routine|urgent|emergency",
  "specialist": "which specialist to see",
  "home_care": "brief home care advice",
  "language": "en|hi|ta|te|..."
}}"""

        resp = client.models.generate_content(
            model=_SUMMARY_MODEL,
            contents=summary_prompt,
            config={"response_mime_type": "application/json", "temperature": 0.1},
        )
        parsed = json.loads(resp.text or "{}")
    except Exception as exc:
        logger.error("ModularVoice: summary generation failed: %s", exc)
        parsed = {"summary": full_text[:200], "symptoms": [], "urgency": "routine"}

    # Persist to DB
    try:
        from app.models.db import db
        from sqlalchemy import text
        now = datetime.now(timezone.utc).isoformat()

        try:
            db.session.execute(text("""
                INSERT INTO conversations
                    (id, patient_id, session_id, summary, symptoms, diagnosis_options,
                     recommended_tests, urgency, specialist, home_care, full_transcript,
                     language, created_at)
                VALUES
                    (:id, :pid, :sid, :summary, :symptoms, :diag, :tests,
                     :urgency, :specialist, :home, :transcript, :lang, :now)
                ON CONFLICT (session_id) DO NOTHING
            """), {
                "id":         session_id,
                "pid":        patient_id,
                "sid":        session_id,
                "summary":    parsed.get("summary", ""),
                "symptoms":   json.dumps(parsed.get("symptoms", [])),
                "diag":       json.dumps(parsed.get("diagnosis_options", [])),
                "tests":      json.dumps(parsed.get("recommended_tests", [])),
                "urgency":    parsed.get("urgency", "routine"),
                "specialist": parsed.get("specialist", ""),
                "home":       parsed.get("home_care", ""),
                "transcript": full_text[:8000],
                "lang":       parsed.get("language", "en"),
                "now":        now,
            })
            db.session.commit()
            logger.info("ModularVoice: conversation saved to DB for session %s", session_id)
        except Exception as db_exc:
            logger.warning("ModularVoice: DB save skipped (table may not exist): %s", db_exc)
            db.session.rollback()

    except Exception as exc:
        logger.warning("ModularVoice: DB save failed: %s", exc)

    return parsed
