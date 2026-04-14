"use client";

import { create } from "zustand";

export type AvatarState = "idle" | "listening" | "speaking";
export type ConversationPhase = "idle" | "initial_intake" | "followup_interview" | "diagnose" | "differential_complete" | "emergency_triage";

export interface SymptomSummary {
  symptoms: string[];
  urgency: "routine" | "moderate" | "urgent" | "emergency";
  differential: any | null;
  recommended_tests: string[];
  phase: string;
  specialist?: string;
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

  // Recording
  isRecording: boolean;
  isProcessing: boolean;

  // Avatar
  avatarState: AvatarState;

  // Conversation
  turns: AIDoctorTurn[];
  localTranscript: string;
  conversationPhase: ConversationPhase;

  // Symptoms
  symptomSummary: SymptomSummary | null;

  // Sharing
  isSharingWithDoctor: boolean;
  sharedWithDoctor: boolean;

  // Error
  error: string | null;

  // Media
  mediaRecorder: MediaRecorder | null;

  // Actions
  startSession: (token: string, patientId: string) => Promise<void>;
  startRecording: () => Promise<void>;
  stopRecordingAndProcess: (token: string) => Promise<void>;
  processVADAudio: (token: string, audioBlob: Blob) => Promise<void>; // VAD auto-submit
  warmup: () => void;                                                  // pre-warm backend
  shareWithDoctor: (token: string, doctorId?: string) => Promise<void>;
  setLanguage: (lang: string) => void;
  endSession: () => void;
  clearError: () => void;
  
  // Simli SDK
  simliAudioPCM16: Uint8Array | null;
  simliConnected: boolean;
  setSimliConnected: (connected: boolean) => void;
  consumeSimliAudio: () => void;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

let audioCtx: AudioContext | null = null;
let currentAudio: HTMLAudioElement | null = null;
let audioChunks: Blob[] = [];

function fallbackToWebSpeech(text: string, lang: string, set: any) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    set({ avatarState: "idle" });
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang || "en-US";
  set({ avatarState: "speaking" });
  utterance.onend = () => set({ avatarState: "idle" });
  utterance.onerror = () => set({ avatarState: "idle" });
  window.speechSynthesis.speak(utterance);
}

// Decode Base64 MP3 to 16kHz 16-bit PCM for Simli
async function decodeToPCM16(b64: string): Promise<Uint8Array> {
  const binaryStr = atob(b64);
  const len = binaryStr.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = binaryStr.charCodeAt(i);
  
  const ctx = new window.AudioContext({ sampleRate: 16000 });
  const audioBuffer = await ctx.decodeAudioData(bytes.buffer);
  
  const channelData = audioBuffer.getChannelData(0);
  const pcm16 = new Int16Array(channelData.length);
  for (let i = 0; i < channelData.length; i++) {
    const s = Math.max(-1, Math.min(1, channelData[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return new Uint8Array(pcm16.buffer);
}

/** Encode Float32Array PCM (from @ricky0123/vad-react) to a WAV Blob the backend accepts. */
export function encodeToWAV(samples: Float32Array, sampleRate = 16000): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const w = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true);
  w(8, "WAVE"); w(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, "data"); v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buf], { type: "audio/wav" });
}

export const useAIDoctorStore = create<AIDoctorState>((set, get) => ({
  sessionId: null,
  isSessionActive: false,
  language: "en",
  isRecording: false,
  isProcessing: false,
  avatarState: "idle",
  turns: [],
  localTranscript: "",
  conversationPhase: "idle",
  symptomSummary: null,
  isSharingWithDoctor: false,
  sharedWithDoctor: false,
  error: null,
  mediaRecorder: null,
  simliAudioPCM16: null,
  simliConnected: false,
  
  setSimliConnected: (connected: boolean) => set({ simliConnected: connected }),
  consumeSimliAudio: () => set({ simliAudioPCM16: null }),

  startSession: async (token: string, patientId: string) => {
    try {
      const res = await fetch(`${API}/api/v1/voice/start-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_mode: "patient", patient_id: patientId }),
      });
      if (!res.ok) throw new Error("Failed to start session");
      const data = await res.json();
      set({
        sessionId: data.session_id,
        isSessionActive: true,
        turns: [],
        symptomSummary: null,
        conversationPhase: "idle",
        error: null,
        sharedWithDoctor: false,
      });
      // Pre-warm TTS & Gemini singletons on Render (fire-and-forget)
      get().warmup();
    } catch (err: any) {
      set({ error: err.message || "Failed to start AI Doctor session" });
    }
  },

  warmup: () => {
    // Fire-and-forget — no auth needed
    fetch(`${API}/api/v1/voice/warmup`).catch(() => {});
  },

  startRecording: async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      if (!audioCtx) audioCtx = new window.AudioContext();
      if (audioCtx.state === "suspended") await audioCtx.resume();

      // Stop any playing audio
      if (currentAudio) { currentAudio.pause(); currentAudio = null; }

      audioChunks = [];
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
      mr.start();

      set({ isRecording: true, avatarState: "listening", localTranscript: "", error: null, mediaRecorder: mr });
    } catch (err: any) {
      set({ error: "Microphone access denied. Please allow microphone access." });
    }
  },

  stopRecordingAndProcess: async (token: string) => {
    const { mediaRecorder, sessionId, language, turns } = get();
    if (!mediaRecorder || mediaRecorder.state === "inactive") return;

    set({ isRecording: false, avatarState: "idle", isProcessing: true });

    await new Promise<void>((resolve) => {
      mediaRecorder.onstop = () => resolve();
      mediaRecorder.stop();
      mediaRecorder.stream?.getTracks().forEach(t => t.stop());
    });

    if (audioChunks.length === 0) {
      set({ isProcessing: false, error: "No audio recorded. Please try again." });
      return;
    }

    const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
    if (audioBlob.size < 512) {
      set({ isProcessing: false, error: "Audio too short. Please speak more clearly." });
      return;
    }

    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      formData.append("session_id", sessionId || "default");
      formData.append("language", language);
      formData.append("format", "webm");

      const res = await fetch(`${API}/api/v1/voice/ai-doctor-stream`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!res.ok) {
        let errStr = "Server error";
        try {
           const errData = await res.json();
           errStr = errData.error || errStr;
        } catch(e) {}
        throw new Error(errStr);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder("utf-8");

      // Set up the turns early so we can stream text into doctorTurn
      const patientTurn: AIDoctorTurn = {
        role: "patient",
        text: "(processing...)", // Will update when done
        timestamp: new Date().toISOString(),
      };
      const doctorTurn: AIDoctorTurn = {
        role: "doctor",
        text: "",
        timestamp: new Date().toISOString(),
      };

      set((state) => ({
        turns: [...state.turns, patientTurn, doctorTurn],
        isProcessing: true, // Keep processing until we get the full text
        localTranscript: "",
      }));

      // Audio playback queue
      const audioQueue: string[] = [];
      let isPlayingQueue = false;

      const playNextAudio = () => {
        if (isPlayingQueue || audioQueue.length === 0) {
          if (!isPlayingQueue && audioQueue.length === 0) {
            set({ avatarState: "idle" });
          }
          return;
        }
        isPlayingQueue = true;
        set({ avatarState: "speaking" });
        const src = audioQueue.shift()!;
        currentAudio = new Audio(src);
        currentAudio.onended = () => {
          isPlayingQueue = false;
          playNextAudio();
        };
        currentAudio.onerror = () => {
          isPlayingQueue = false;
          playNextAudio();
        };
        currentAudio.play().catch((e) => {
          console.error("Audio playback blocked", e);
          isPlayingQueue = false;
          playNextAudio();
        });
      };

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        
        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const eventStr = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf("\n\n");

          if (eventStr.startsWith("data: ")) {
            const dataStr = eventStr.slice(6);
            if (dataStr === "[DONE]") continue;

            try {
              const data = JSON.parse(dataStr);

              if (data.type === "chunk") {
                // Streaming text chunk
                set((state) => {
                  const newTurns = [...state.turns];
                  const last = newTurns[newTurns.length - 1];
                  last.text += (last.text ? " " : "") + data.text;
                  return { turns: newTurns };
                });

                // Streaming audio chunk
                if (data.audio_b64) {
                  if (get().simliConnected) {
                    try {
                      const pcmData = await decodeToPCM16(data.audio_b64);
                      set({ simliAudioPCM16: pcmData, avatarState: "speaking" });
                    } catch (e) {
                      console.error("PCM Decode chunk error:", e);
                    }
                  }

                  // Always enqueue local native audio (Simli audio output handled in DoctorAvatar)
                  const src = `data:audio/mp3;base64,${data.audio_b64}`;
                  audioQueue.push(src);
                  playNextAudio();
                }

              } else if (data.type === "done") {
                // Final piece
                const symptomSummary = data.symptom_summary || null;
                const phase = (symptomSummary?.phase || "initial_intake") as ConversationPhase;
                
                set((state) => {
                  const newTurns = [...state.turns];
                  // Update patient turn text
                  newTurns[newTurns.length - 2].text = data.transcript || "(audio)";
                  return {
                    turns: newTurns,
                    symptomSummary,
                    conversationPhase: phase,
                    isProcessing: false,
                    language: data.language || state.language,
                  };
                });
              } else if (data.type === "error") {
                set({ error: data.message, isProcessing: false });
              }
            } catch (e) {
              console.error("SSE Parse Error", e, dataStr);
            }
          }
        }
      }

    } catch (err: any) {
      set({ isProcessing: false, avatarState: "idle", error: err.message || "Processing failed" });
    }
  },

  shareWithDoctor: async (token: string, doctorId?: string) => {
    const { sessionId, symptomSummary, turns } = get();
    set({ isSharingWithDoctor: true });
    try {
      // End session and share summary
      const body: any = {};
      if (doctorId) body.share_with_doctor_id = doctorId;
      if (sessionId) {
        await fetch(`${API}/api/v1/voice/session/${sessionId}/end`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify(body),
        });
      }
      set({ isSharingWithDoctor: false, sharedWithDoctor: true });
    } catch {
      set({ isSharingWithDoctor: false, error: "Failed to share with doctor" });
    }
  },

  setLanguage: (lang: string) => set({ language: lang }),
  clearError: () => set({ error: null }),

  processVADAudio: async (token: string, audioBlob: Blob) => {
    const { sessionId, language } = get();
    if (!sessionId) return;
    if (audioBlob.size < 512) return;

    set({ isRecording: false, avatarState: "idle", isProcessing: true, localTranscript: "" });
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }

    const patientTurn: AIDoctorTurn = { role: "patient", text: "(processing...)", timestamp: new Date().toISOString() };
    const doctorTurn:  AIDoctorTurn = { role: "doctor",  text: "",               timestamp: new Date().toISOString() };
    set((s) => ({ turns: [...s.turns, patientTurn, doctorTurn], isProcessing: true }));

    const audioQueue: string[] = [];
    let isPlayingQueue = false;
    const playNextAudio = () => {
      if (isPlayingQueue || audioQueue.length === 0) {
        if (!isPlayingQueue && audioQueue.length === 0) set({ avatarState: "idle" });
        return;
      }
      isPlayingQueue = true;
      set({ avatarState: "speaking" });
      const src = audioQueue.shift()!;
      currentAudio = new Audio(src);
      currentAudio.onended = () => { isPlayingQueue = false; playNextAudio(); };
      currentAudio.onerror = () => { isPlayingQueue = false; playNextAudio(); };
      currentAudio.play().catch(() => { isPlayingQueue = false; playNextAudio(); });
    };

    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, `recording.${audioBlob.type.includes("wav") ? "wav" : "webm"}`);
      formData.append("session_id", sessionId);
      formData.append("language", language);
      formData.append("format", audioBlob.type.includes("wav") ? "wav" : "webm");

      const res = await fetch(`${API}/api/v1/voice/ai-doctor-stream`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error("Server error");

      const reader = res.body!.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const eventStr = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf("\n\n");
          if (eventStr.startsWith("data: ")) {
            try {
              const data = JSON.parse(eventStr.slice(6));
              if (data.type === "chunk") {
                set((s) => {
                  const t = [...s.turns];
                  t[t.length - 1].text += (t[t.length - 1].text ? " " : "") + data.text;
                  return { turns: t };
                });
                if (data.audio_b64) {
                  audioQueue.push(`data:audio/mp3;base64,${data.audio_b64}`);
                  playNextAudio();
                }
              } else if (data.type === "done") {
                set((s) => {
                  const t = [...s.turns];
                  t[t.length - 2].text = data.transcript || "(audio)";
                  return { turns: t, isProcessing: false, language: data.language || s.language,
                           symptomSummary: data.symptom_summary || null,
                           conversationPhase: (data.symptom_summary?.phase || "initial_intake") as ConversationPhase };
                });
              } else if (data.type === "error") {
                set({ error: data.message, isProcessing: false });
              }
            } catch { /* malformed SSE */ }
          }
        }
      }
    } catch (err: any) {
      set({ isProcessing: false, avatarState: "idle", error: err.message || "Processing failed" });
    }
  },

  endSession: () => {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    const { mediaRecorder } = get();
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
      mediaRecorder.stream?.getTracks().forEach(t => t.stop());
    }
    set({
      isSessionActive: false,
      isRecording: false,
      isProcessing: false,
      avatarState: "idle",
      sessionId: null,
      turns: [],
      symptomSummary: null,
      conversationPhase: "idle",
      error: null,
      mediaRecorder: null,
    });
  },
}));
