"use client";

import React, { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { VoiceTurn } from "@/store/voiceStore";
import { User, Sparkles } from "lucide-react";

interface TranscriptDisplayProps {
  turns: VoiceTurn[];
  localTranscript: string;
  isRecording: boolean;
}

export function TranscriptDisplay({ turns, localTranscript, isRecording }: TranscriptDisplayProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [turns, localTranscript]);

  return (
    <div 
      ref={containerRef}
      className="flex-1 w-full max-w-3xl mx-auto overflow-y-auto px-4 py-8 space-y-6 scroll-smooth"
    >
      {turns.map((turn, idx) => (
        <div 
          key={idx} 
          className={cn(
            "flex gap-4 p-4 rounded-2xl max-w-[85%] animate-in fade-in slide-in-from-bottom-2",
            turn.role === "patient" 
              ? "bg-white border text-gray-800 ml-auto" 
              : "bg-cyan-50/50 border border-cyan-100 text-slate-800 mr-auto"
          )}
        >
          <div className={cn(
            "h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
            turn.role === "patient" ? "bg-gray-100 text-gray-500" : "bg-cyan-100 text-cyan-600"
          )}>
            {turn.role === "patient" ? <User size={16} /> : <Sparkles size={16} />}
          </div>
          <div className="flex-1">
            <p className="text-[10px] font-semibold tracking-wider uppercase mb-1 opacity-50">
              {turn.role === "patient" ? "You" : "VitalMind Assistant"}
            </p>
            <p className="text-[15px] leading-relaxed font-medium">
              {turn.transcript}
            </p>
          </div>
        </div>
      ))}
      
      {/* Real-time local fallback placeholder */}
      {isRecording && localTranscript && (
        <div className="flex gap-4 p-4 rounded-2xl max-w-[85%] bg-white/50 border text-gray-600 ml-auto border-dashed animate-pulse">
          <div className="h-8 w-8 rounded-full bg-gray-50 border border-gray-100 text-gray-400 flex items-center justify-center flex-shrink-0 mt-0.5">
            <User size={16} />
          </div>
          <div className="flex-1">
            <p className="text-[10px] font-semibold tracking-wider uppercase mb-1 opacity-50">
              You (Listening...)
            </p>
            <p className="text-[15px] leading-relaxed">
              {localTranscript}
            </p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {turns.length === 0 && !localTranscript && (
        <div className="h-full flex flex-col items-center justify-center text-center opacity-50 space-y-4">
          <Sparkles className="h-12 w-12 text-gray-400" />
          <p className="text-gray-500 font-medium max-w-sm">
            I'm VitalMind, your voice assistant. Tap the microphone and tell me how you are feeling today.
          </p>
        </div>
      )}
    </div>
  );
}
