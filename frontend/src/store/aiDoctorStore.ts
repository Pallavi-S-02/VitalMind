"use client";

import { create } from "zustand";
import { io, Socket } from "socket.io-client";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type AvatarState = "idle" | "listening" | "speaking" | "connecting";
export type ConversationPhase =
  | "idle"
  | "initial_intake"
  | "followup_interview"
  | "diagnose"
  | "differential_complete"
  | "emergency_triage";

export interface SymptomSummary {
  symptoms: string[];
  urgency: "routine" | "moderate" | "urgent" | "emergency";
  differential: string[] | null;
  recommended_tests: string[];
  phase: string;
  specialist?: string;
  summary?: string;
  home_care?: string;
}

export interface AIDoctorTurn {
  role: "patient" | "doctor";
  text: string;
  timestamp: string;
  language?: string;
}

interface AIDoctorState {
  // Session
  sessionId: string | null;
  isSessionActive: boolean;
  language: string;

  // Mic / recording
  isListening: boolean;       // mic is open & streaming to Gemini
  isProcessing: boolean;      // waiting for Gemini first audio chunk
  isSpeaking: boolean;        // Gemini audio is playing

  // Avatar
  avatarState: AvatarState;

  // Conversation
  turns: AIDoctorTurn[];
  conversationPhase: ConversationPhase;
  turnCount: number;

  // Symptoms
  symptomSummary: SymptomSummary | null;

  // Sharing
  isSharingWithDoctor: boolean;
  sharedWithDoctor: boolean;

  // Error
  error: string | null;

  // Actions
  startSession: (token: string, patientId: string) => Promise<void>;
  startListening: () => void;
  stopListening: () => void;
  shareWithDoctor: (token: string, doctorId?: string) => Promise<void>;
  setLanguage: (lang: string) => void;
  endSession: () => void;
  clearError: () => void;

  // Legacy compat
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecordingAndProcess: (token: string) => Promise<void>;
  processVADAudio: (token: string, audioBlob: Blob) => Promise<void>;
  warmup: () => void;
  mediaRecorder: MediaRecorder | null;
  localTranscript: string;
  simliAudioPCM16: Uint8Array | null;
  simliConnected: boolean;
  setSimliConnected: (c: boolean) => void;
  consumeSimliAudio: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Singletons
// ─────────────────────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
const SAMPLE_RATE = 16000;  // mic capture rate (PCM 16kHz sent to Groq Whisper)
// NOTE: output audio is MP3 from ElevenLabs — browser decodes it natively via decodeAudioData

let _socket: Socket | null = null;
let _audioCtx: AudioContext | null = null;
let _micStream: MediaStream | null = null;
let _micSource: MediaStreamAudioSourceNode | null = null;
let _scriptProcessor: ScriptProcessorNode | null = null;
let _currentToken: string | null = null;

// Playback queue for arriving 24kHz PCM chunks
let _playbackStartTime = 0;
let _playbackScheduled = 0;

// ─────────────────────────────────────────────────────────────────────────────
// Audio utilities
// ─────────────────────────────────────────────────────────────────────────────

function getAudioCtx(): AudioContext {
  if (!_audioCtx || _audioCtx.state === "closed") {
    // Default sample rate — browser handles MP3 natively regardless of rate
    _audioCtx = new AudioContext();
  }
  if (_audioCtx.state === "suspended") {
    _audioCtx.resume();
  }
  return _audioCtx;
}

/** Convert Float32 mic samples → Int16 PCM bytes */
function float32ToPCM16(input: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(input.length * 2);
  const view   = new DataView(buffer);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return buffer;
}

/**
 * Decode a base64 PCM16 chunk (from ElevenLabs) and schedule it for gapless playback.
 * Does NOT use decodeAudioData — avoids MP3 padding/overlapping which causes severe echo.
 */
async function playPCM16Chunk(
  audioB64: string,
  set: (s: Partial<AIDoctorState>) => void
): Promise<void> {
  try {
    const ctx = getAudioCtx();

    // Decode base64 → binary string
    const binary = atob(audioB64);
    
    // Ensure even byte length for 16-bit PCM
    const validLen = binary.length - (binary.length % 2);
    const buffer = new ArrayBuffer(validLen);
    const view = new Uint8Array(buffer);
    for (let i = 0; i < validLen; i++) {
        view[i] = binary.charCodeAt(i);
    }
    const pcm16 = new Int16Array(buffer);

    // Convert Int16 PCM to Float32 [-1.0, 1.0] for Web Audio API
    const sampleRate = 22050; // ElevenLabs pcm_22050 format
    const audioBuffer = ctx.createBuffer(1, pcm16.length, sampleRate);
    const channelData = audioBuffer.getChannelData(0);
    for (let i = 0; i < pcm16.length; i++) {
      channelData[i] = pcm16[i] / 32768.0;
    }

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    const now = ctx.currentTime;
    // Add small playback buffer to prevent starvation gaps between websocket chunks
    if (_playbackStartTime < now) {
      _playbackStartTime = now + 0.05;
      set({ avatarState: "speaking", isSpeaking: true, isProcessing: false });
    }

    source.start(_playbackStartTime);
    _playbackStartTime += audioBuffer.duration;
    _playbackScheduled++;

    source.onended = () => {
      _playbackScheduled--;
      if (_playbackScheduled <= 0) {
        _playbackScheduled = 0;
        set({ avatarState: "idle", isSpeaking: false });
      }
    };
  } catch (e) {
    console.error("[VoiceWS] PCM decode error:", e);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Zustand Store
// ─────────────────────────────────────────────────────────────────────────────

export const useAIDoctorStore = create<AIDoctorState>((set, get) => ({
  // ── State ──────────────────────────────────────────────────────────────────
  sessionId:          null,
  isSessionActive:    false,
  language:           "en",
  isListening:        false,
  isProcessing:       false,
  isSpeaking:         false,
  avatarState:        "idle",
  turns:              [],
  conversationPhase:  "idle",
  turnCount:          0,
  symptomSummary:     null,
  isSharingWithDoctor: false,
  sharedWithDoctor:   false,
  error:              null,

  // Legacy compat
  isRecording:    false,
  mediaRecorder:  null,
  localTranscript: "",
  simliAudioPCM16: null,
  simliConnected:  false,

  // ── Helpers (legacy compat no-ops / stubs) ─────────────────────────────────
  warmup: () => {},
  setSimliConnected: (c) => set({ simliConnected: c }),
  consumeSimliAudio: () => set({ simliAudioPCM16: null }),
  clearError: () => set({ error: null }),
  setLanguage: (lang) => {
    set({ language: lang });
    if (_socket?.connected) {
      _socket.emit("update_language", { language: lang });
      console.log(`[VoiceWS] Language dynamically updated to: ${lang}`);
    }
  },

  startRecording: async () => {
    get().startListening();
  },

  stopRecordingAndProcess: async (_token: string) => {
    get().stopListening();
  },

  processVADAudio: async (_token: string, _blob: Blob) => {
    // Not used in Live API mode — VAD sends chunks continuously
  },

  // ── Core: startSession ─────────────────────────────────────────────────────
  startSession: async (token: string, patientId: string) => {
    set({ avatarState: "connecting", error: null, isProcessing: false });
    _currentToken = token;

    // Close any existing socket
    if (_socket?.connected) {
      _socket.disconnect();
    }

    const socket = io(`${API}/voice`, {
      auth: { token: `Bearer ${token}` },
      transports: ["websocket"],
      reconnectionAttempts: 3,
      timeout: 10000,
    });
    _socket = socket;

    // ── Socket event handlers ──────────────────────────────────────────────

    socket.on("connect", () => {
      console.log("[VoiceWS] connected, joining session...");
      socket.emit("join_voice_session", {
        session_mode: "patient",
        patient_id:   patientId,
        language:     get().language || "en",   // ← pass UI language so Whisper + LLM use correct language
      });
    });

    socket.on("connect_error", (err) => {
      console.error("[VoiceWS] connect error:", err.message);
      set({ error: `Connection failed: ${err.message}`, avatarState: "idle", isSessionActive: false, isProcessing: false });
    });

    socket.on("disconnect", () => {
      console.log("[VoiceWS] disconnected");
      set({ 
        isSessionActive: false, 
        avatarState: "idle", 
        isProcessing: false, 
        isSpeaking: false,
        isListening: false
      });
      get().stopListening();
    });

    socket.on("voice_session_joined", (data) => {
      console.log("[VoiceWS] session joined:", data);
      set({
        sessionId:       data.session_id,
        isSessionActive: true,
        avatarState:     "idle",
        conversationPhase: "initial_intake",
        turns:           [],
        turnCount:       0,
        symptomSummary:  null,
      });
    });

    socket.on("live_session_ready", () => {
      console.log("[VoiceWS] AI Doctor pipeline ready — awaiting user input");
      // Do NOT auto-start the mic to prevent picking up background noise immediately.
      // The user must explicitly press "TAP TO SPEAK" to begin.
    });

    // live_audio_chunk: Raw PCM16 chunk from ElevenLabs TTS (base64-encoded)
    socket.on("live_audio_chunk", (data: {
      audio_b64?: string;
      audio_format?: string;   // "pcm16" from new backend
      sample_rate?: number;
      chunk_index: number;
    }) => {
      set({ isProcessing: false }); // ALWAYS clear processing state when we get any audio
      if (!data.audio_b64) return;
      // Decode raw PCM directly to prevent MP3 artifacting + overlapping echoes
      playPCM16Chunk(data.audio_b64, set).catch((e) =>
        console.error("[VoiceWS] PCM playback error:", e)
      );
    });

    // voice_turn_text: transcript + doctor reply for the chat feed
    socket.on("voice_turn_text", (data: {
      patient_text: string;
      doctor_text: string;
      language?: string;
      phase?: string;
      entities?: any;
      turn: number;
    }) => {
      const now = new Date().toISOString();
      set((state) => ({
        turns: [
          ...state.turns,
          { role: "patient", text: data.patient_text, timestamp: now, language: data.language },
          { role: "doctor",  text: data.doctor_text,  timestamp: now, language: data.language },
        ],
        conversationPhase: (
          data.phase === "emergency_triage" ? "emergency_triage" :
          data.phase === "diagnose"         ? "diagnose"         :
          data.phase === "followup_interview" ? "followup_interview" :
          "initial_intake"
        ) as ConversationPhase,
      }));
    });

    socket.on("live_turn_complete", (data) => {
      console.log("[VoiceWS] turn complete, turn:", data.turn);
      const { turnCount } = get();
      const newTurn = turnCount + 1;
      set({
        turnCount: newTurn,
        isProcessing: false,
        conversationPhase: newTurn >= 6 ? "diagnose" : newTurn >= 3 ? "followup_interview" : "initial_intake",
      });
    });

    socket.on("turn_skipped", () => {
      console.log("[VoiceWS] turn skipped (empty audio or noise detected)");
      set({ isProcessing: false, avatarState: "idle" });
    });

    socket.on("voice_error", (data) => {
      console.error("[VoiceWS] error:", data.detail);
      set({
        error:       data.detail || "Voice session error",
        isProcessing: false,
        avatarState:  "idle",
      });
    });

    socket.on("session_ended", () => {
      console.log("[VoiceWS] session ended");
      set({ isSessionActive: false, avatarState: "idle", isListening: false, isSpeaking: false });
      _stopMic();
    });

    socket.on("session_summary", (data) => {
      const summary = data.summary || {};
      set({
        symptomSummary: {
          symptoms:          summary.symptoms || [],
          urgency:           summary.urgency  || "routine",
          differential:      summary.diagnosis_options || null,
          recommended_tests: summary.recommended_tests || [],
          phase:             "closed",
          specialist:        summary.specialist || "",
          summary:           summary.summary   || "",
          home_care:         summary.home_care || "",
        },
      });
    });

    socket.on("disconnect", () => {
      console.log("[VoiceWS] disconnected");
      _stopMic();
      set({ isSessionActive: false, avatarState: "idle", isListening: false });
    });
  },

  // ── startListening ─────────────────────────────────────────────────────────
  startListening: () => {
    if (get().isListening || typeof window === "undefined") return;

    navigator.mediaDevices
      .getUserMedia({ audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true, noiseSuppression: true } })
      .then((stream) => {
        _micStream = stream;

        // Use a separate AudioContext at 16kHz for capture
        const captureCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
        _micSource = captureCtx.createMediaStreamSource(stream);
        
        let _silenceChunks = 0;
        // Echo suppression: mute mic while Dr. Janvi's TTS audio is playing.
        // Without this, the speaker playback gets picked up by the mic and fed
        // back through Groq STT → garbled/wrong-language transcript → bad response.
        let _echoMuted    = false;
        let _echoSettle   = 0;            // countdown frames after TTS ends
        const ECHO_SETTLE = 5;           // 5 × 256ms ≈ 1.3s settling time

        // ScriptProcessor for raw PCM access (4096 samples @ 16kHz = 256ms chunks)
        _scriptProcessor = captureCtx.createScriptProcessor(4096, 1, 1);
        _scriptProcessor.onaudioprocess = (e) => {
          if (!get().isListening || !_socket?.connected) return;

          // ── Echo suppression ────────────────────────────────────────────────
          if (get().isSpeaking) {
            // Dr. Janvi is playing audio from speakers — mute mic completely
            _echoMuted  = true;
            _echoSettle = ECHO_SETTLE;
            _silenceChunks = 3;  // treat as "turn already ended" so we don't fire END_TURN on TTS audio
            return;
          }
          if (_echoSettle > 0) {
            // Brief settling time after TTS stops (speaker reverb / acoustic tail)
            _echoSettle--;
            return;
          }
          _echoMuted = false;
          // ── End echo suppression ─────────────────────────────────────────────

          const raw   = e.inputBuffer.getChannelData(0);
          const pcm16 = float32ToPCM16(raw);

          // Convert raw Float32 mic data to PCM16 binary buffer
          const pcmBytes = new Uint8Array(pcm16);

          // Calculate Voice Activity (RMS)
          const rms = Math.sqrt(raw.reduce((s, x) => s + x * x, 0) / raw.length);

          // Send audio ONLY if there is significant voice activity
          if (rms > 0.015) {
            set({ avatarState: "listening", isProcessing: true });

            // Send binary raw PCM bytes directly — Socket.IO supports ArrayBuffer natively
            _socket.emit("audio_chunk", pcmBytes.buffer);

            // Reset consecutive silence counter
            _silenceChunks = 0;
          } else {
            // Send a few silent chunks to give Whisper context padding, then stop
            if (_silenceChunks < 2) {
                _socket.emit("audio_chunk", pcmBytes.buffer);
                _silenceChunks++;
            } else if (_silenceChunks === 2) {
               _socket.emit("audio_turn_complete");
               _silenceChunks++;
               // isProcessing stays true until the first TTS chunk arrives
               // It will be reset to false when the server starts returning voice chunks!
            } else {
               // still silent, do nothing
            }
          }
        };

        _micSource.connect(_scriptProcessor);
        _scriptProcessor.connect(captureCtx.destination);

        set({ isListening: true, isRecording: true, avatarState: "listening" });
        console.log("[VoiceWS] Mic started — streaming PCM 16kHz to Groq Whisper STT");
      })
      .catch((err) => {
        console.error("[VoiceWS] Mic access error:", err);
        set({ error: "Microphone access denied. Please allow microphone access." });
      });
  },

  // ── stopListening ──────────────────────────────────────────────────────────
  stopListening: () => {
    _stopMic();
    
    // CRITICAL: If the user manually pauses the mic, explicitly tell the backend 
    // the turn is complete. Otherwise the chunks sit in the buffer forever and 
    // the UI stays permanently stuck on 'PROCESSING...' without sending them to STT.
    if (_socket?.connected) {
      _socket.emit("audio_turn_complete");
    }

    set({ isListening: false, isRecording: false, avatarState: get().isSpeaking ? "speaking" : "idle" });
    console.log("[VoiceWS] Mic stopped manually — triggered audio_turn_complete");
  },

  // ── endSession ─────────────────────────────────────────────────────────────
  endSession: () => {
    _stopMic();

    if (_socket?.connected) {
      const { sessionId } = get();
      _socket.emit("end_voice_session", { session_id: sessionId });
      setTimeout(() => _socket?.disconnect(), 500);
    }

    set({
      isSessionActive:  false,
      isListening:      false,
      isRecording:      false,
      isProcessing:     false,
      isSpeaking:       false,
      avatarState:      "idle",
      sessionId:        null,
      conversationPhase: "idle",
      error:            null,
    });
  },

  // ── shareWithDoctor ────────────────────────────────────────────────────────
  shareWithDoctor: async (token: string, _doctorId?: string) => {
    const { symptomSummary, turns, sessionId } = get();
    if (!symptomSummary) return;

    set({ isSharingWithDoctor: true });
    try {
      await fetch(`${API}/api/v1/voice/share-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId, summary: symptomSummary, turns }),
      });
      set({ sharedWithDoctor: true });
    } catch (e) {
      set({ error: "Could not share with doctor. Please try again." });
    } finally {
      set({ isSharingWithDoctor: false });
    }
  },
}));

// ─────────────────────────────────────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────────────────────────────────────

function _stopMic() {
  if (_scriptProcessor) {
    _scriptProcessor.disconnect();
    _scriptProcessor = null;
  }
  if (_micSource) {
    _micSource.disconnect();
    _micSource = null;
  }
  if (_micStream) {
    _micStream.getTracks().forEach((t) => t.stop());
    _micStream = null;
  }
}
