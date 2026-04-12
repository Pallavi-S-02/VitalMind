"use client";

import React, { useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { HeartPulse } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";
import { TranscriptDisplay } from "@/components/voice/TranscriptDisplay";
import { VoiceControlBar } from "@/components/voice/VoiceControlBar";
import { VoicePulseAnimation } from "@/components/voice/VoicePulseAnimation";

export default function VoiceAssistantPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const {
    connect,
    disconnect,
    isConnected,
    isInitializing,
    isRecording,
    isPlaying,
    volumeLog,
    turns,
    localTranscript,
    languageHint,
    error,
    startRecording,
    stopRecording,
    endSession,
    clearError
  } = useVoiceStore();

  useEffect(() => {
    if (session?.accessToken && session?.user?.id) {
      connect(session.accessToken, "patient", session.user.id);
    }
    return () => {
      disconnect();
    };
  }, [session]);

  const handleEndSession = () => {
    endSession();
    router.push("/patient/dashboard");
  };

  const handleLanguageChange = (lang: string) => {
    // If we reconnect, we apply the new language
    if (session?.accessToken && session?.user?.id) {
      connect(session.accessToken, "patient", session.user.id, lang);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] relative bg-slate-50 shadow-inner rounded-3xl overflow-hidden">
      {/* Header Area */}
      <div className="absolute top-0 inset-x-0 h-48 bg-gradient-to-b from-cyan-900/10 to-transparent pointer-events-none" />
      
      <div className="relative z-10 flex items-center justify-between p-6">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-cyan-100 flex items-center justify-center text-cyan-600 shadow-sm">
            <HeartPulse className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-800">VitalMind Voice</h1>
            <p className="text-sm text-slate-500 font-medium">AI Clinical Assistant</p>
          </div>
        </div>
      </div>

      {/* Main Content Area: Transcript */}
      <div className="flex-1 relative z-10 flex flex-col justify-end pb-8">
        <TranscriptDisplay 
          turns={turns} 
          localTranscript={localTranscript} 
          isRecording={isRecording} 
        />
      </div>

      {/* Error Banner */}
      {error && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-50 bg-red-100 text-red-700 px-4 py-2 rounded-lg shadow-sm flex items-center gap-2 text-sm font-medium">
          <span>{error}</span>
          <button onClick={clearError} className="hover:text-red-900 ml-2 font-bold">✕</button>
        </div>
      )}

      {/* Bottom Area: Controls & Visualizer */}
      <div className="relative z-20 bg-white/50 backdrop-blur-xl border-t border-white/20 pb-8 pt-4 px-6 flex flex-col items-center">
        <div className="w-full max-w-md mb-6">
          <VoicePulseAnimation 
            isRecording={isRecording} 
            isPlaying={isPlaying} 
            volumeLog={volumeLog} 
          />
        </div>

        <VoiceControlBar 
          isRecording={isRecording}
          isInitializing={isInitializing}
          isConnected={isConnected}
          languageHint={languageHint}
          onStartRecording={startRecording}
          onStopRecording={stopRecording}
          onEndSession={handleEndSession}
          onLanguageChange={handleLanguageChange}
        />
      </div>
    </div>
  );
}
