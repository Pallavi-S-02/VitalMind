"use client";

import { create } from "zustand";
import { io, Socket } from "socket.io-client";

// Web Speech API interfaces
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export type SessionMode = "patient" | "ambient";

export interface VoiceTurn {
  role: "patient" | "assistant";
  transcript: string;
  timestamp: string;
}

export interface AmbientSoap {
  subjective: any;
  objective: any;
  assessment: any;
  plan: any;
  new_information?: boolean;
}

interface VoiceState {
  // Connection & Core
  socket: Socket | null;
  isConnected: boolean;
  sessionId: string | null;
  sessionMode: SessionMode;
  languageHint: string;
  isInitializing: boolean;
  error: string | null;

  // Media
  isRecording: boolean;
  isPlaying: boolean;
  mediaRecorder: MediaRecorder | null;
  volumeLog: number[]; // Store recent volume levels for visualization

  // STT & Transcripts
  localTranscript: string; // real-time fallback via Web Speech API
  finalTranscript: string;
  turns: VoiceTurn[];
  ambientSoap: AmbientSoap | null;

  // Actions
  connect: (token: string, mode: SessionMode, patientId?: string, overrideLanguage?: string) => Promise<void>;
  disconnect: () => void;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  endSession: (token?: string) => Promise<string | null>;
  sendAmbientConsent: (patientId: string, consent: boolean) => void;
  clearError: () => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

let audioContext: AudioContext | null = null;
let currentAudio: HTMLAudioElement | null = null;

export const useVoiceStore = create<VoiceState>((set, get) => ({
  socket: null,
  isConnected: false,
  sessionId: null,
  sessionMode: "patient",
  languageHint: "en",
  isInitializing: false,
  error: null,

  isRecording: false,
  isPlaying: false,
  mediaRecorder: null,
  volumeLog: Array(20).fill(0),

  localTranscript: "",
  finalTranscript: "",
  turns: [],
  ambientSoap: null,

  connect: async (token: string, mode: SessionMode, patientId?: string, overrideLanguage?: string) => {
    set({ isInitializing: true, error: null, sessionMode: mode });

    const existing = get().socket;
    if (existing?.connected) {
      existing.disconnect();
    }

    const socket = io(`${API_URL}/voice`, {
      path: "/socket.io",
      auth: { token },
      transports: ["websocket", "polling"],
    });

    socket.on("connect", () => {
      set({ isConnected: true });
      socket.emit("join_voice_session", {
        session_mode: mode,
        patient_id: patientId,
        language: overrideLanguage || get().languageHint,
      });
    });

    socket.on("disconnect", () => {
      set({ isConnected: false });
    });

    socket.on("voice_session_joined", (data) => {
      set({ sessionId: data.session_id, isInitializing: false });
    });

    socket.on("voice_response", (data) => {
      // Received response from agent
      const { transcript, spoken_response, audio_b64, audio_format, intent } = data;

      set((state) => ({
        localTranscript: "",
        finalTranscript: "",
        turns: [
          ...state.turns,
          { role: "patient", transcript, timestamp: new Date().toISOString() },
          { role: "assistant", transcript: spoken_response, timestamp: new Date().toISOString() },
        ],
      }));

      // Play audio if provided (only for patient mode usually)
      if (audio_b64 && mode === "patient") {
        try {
          if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
          }
          const audioSrc = `data:audio/${audio_format || "mp3"};base64,${audio_b64}`;
          currentAudio = new Audio(audioSrc);
          
          currentAudio.onplay = () => set({ isPlaying: true });
          currentAudio.onended = () => set({ isPlaying: false });
          currentAudio.onerror = (e) => {
            console.error("Audio playback error", e);
            set({ isPlaying: false });
          };
          
          currentAudio.play();
        } catch (err) {
          console.error("Failed to play response audio", err);
        }
      }
    });

    socket.on("voice_transcript", (data) => {
      // Stream update if backend sent it
    });

    socket.on("ambient_update", (data) => {
      set((state) => ({
        ambientSoap: data.soap_segment || data.accumulated_soap || state.ambientSoap,
        turns: [
          ...state.turns,
          { role: "patient", transcript: data.transcript, timestamp: data.timestamp }
        ]
      }));
    });

    socket.on("voice_error", (data) => {
      set({ error: data.detail, isInitializing: false });
    });

    socket.on("session_ended", () => {
      set({ isRecording: false, sessionId: null });
      if (currentAudio) currentAudio.pause();
      set({ isPlaying: false });
    });

    set({ socket });
  },

  disconnect: () => {
    const { socket, mediaRecorder } = get();
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    if (currentAudio) {
      currentAudio.pause();
    }
    socket?.disconnect();
    set({
      socket: null,
      isConnected: false,
      isRecording: false,
      isPlaying: false,
      sessionId: null,
      error: null,
      localTranscript: "",
      finalTranscript: "",
      turns: [],
      ambientSoap: null,
    });
  },

  startRecording: async () => {
    const { socket } = get();
    if (!socket?.connected) {
      set({ error: "Cannot record: not connected to server." });
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Setup audio analyzer for volume visualization
      if (!audioContext) audioContext = new window.AudioContext();
      if (audioContext.state === "suspended") await audioContext.resume();
      const source = audioContext.createMediaStreamSource(stream);
      const analyzer = audioContext.createAnalyser();
      analyzer.fftSize = 256;
      source.connect(analyzer);
      const dataArray = new Uint8Array(analyzer.frequencyBinCount);
      
      let animationFrameId: number;
      const updateVolume = () => {
        if (!get().isRecording) return;
        analyzer.getByteFrequencyData(dataArray);
        const sum = dataArray.reduce((a, b) => a + b, 0);
        const avg = sum / dataArray.length;
        set((state) => ({
          volumeLog: [...state.volumeLog.slice(1), avg]
        }));
        animationFrameId = requestAnimationFrame(updateVolume);
      };
      
      // Stop previous audio playback
      if (currentAudio) {
        currentAudio.pause();
        set({ isPlaying: false });
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      
      const audioChunks: Blob[] = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunks.push(e.data);
          // For real-time chunk streaming to backend
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64data = (reader.result as string).split(',')[1];
            socket.emit("audio_chunk", {
              audio_b64: base64data,
              format: "webm",
              final: false
            });
          };
          reader.readAsDataURL(e.data);
        }
      };

      mediaRecorder.onstart = () => {
        set({ isRecording: true, localTranscript: "", error: null });
        updateVolume();
        
        // Setup local fallback transcription
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = get().languageHint === "en" ? "en-US" : get().languageHint;
          
          recognition.onresult = (event: any) => {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; ++i) {
              interim += event.results[i][0].transcript;
            }
            set({ localTranscript: interim });
          };
          
          recognition.start();
          
          // attach to stop function
          (mediaRecorder as any)._recognition = recognition;
        }
      };

      mediaRecorder.onstop = () => {
        cancelAnimationFrame(animationFrameId);
        stream.getTracks().forEach(track => track.stop());
        
        if ((mediaRecorder as any)._recognition) {
          (mediaRecorder as any)._recognition.stop();
        }

        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64data = (reader.result as string).split(',')[1];
          // Send final chunk
          socket.emit("audio_chunk", {
            audio_b64: base64data,
            format: "webm",
            final: true
          });
        };
        reader.readAsDataURL(audioBlob);
        
        set({ isRecording: false, volumeLog: Array(20).fill(0) });
      };

      // Depending on mode, we either get large chunks or single shot
      // Patient Mode: record per-utterance
      if (get().sessionMode === "patient") {
         mediaRecorder.start(); // collect until stopped
      } else {
         // Ambient Mode: send chunks regularly
         mediaRecorder.start(3000); // Send chunks every 3 seconds
      }
      
      set({ mediaRecorder });

    } catch (err: any) {
      console.error("Microphone access error", err);
      set({ error: "Microphone access denied or unavailable." });
    }
  },

  stopRecording: () => {
    const { mediaRecorder } = get();
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  },

  endSession: async (token?: string) => {
    const { socket, sessionId } = get();
    
    let generatedReportId = null;

    if (token && sessionId) {
      // Make REST call to trigger actual final SOAP note generation (Step 20)
      try {
        const res = await fetch(`${API_URL}/api/v1/voice/session/${sessionId}/end`, {
          method: "DELETE",
          headers: {
             "Authorization": `Bearer ${token}`
          }
        });
        if (res.ok) {
           const data = await res.json();
           generatedReportId = data.generated_report_id;
        }
      } catch (err) {
        console.error("Failed to cleanly end session via REST", err);
      }
    } else if (socket?.connected) {
      // Fallback
      socket.emit("end_voice_session", {});
    }

    get().disconnect();
    return generatedReportId;
  },

  sendAmbientConsent: (patientId: string, consent: boolean) => {
    const { socket } = get();
    if (socket?.connected) {
      socket.emit("ambient_consent", { patient_id: patientId, consent_given: consent });
    }
  },
  
  clearError: () => set({ error: null })
}));
