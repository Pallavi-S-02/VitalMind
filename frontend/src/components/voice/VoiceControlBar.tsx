"use client";

import React from "react";
import { Mic, Square, Loader2, Languages, PhoneOff } from "lucide-react";
import { cn } from "@/lib/utils";

interface VoiceControlBarProps {
  isRecording: boolean;
  isInitializing: boolean;
  isConnected: boolean;
  languageHint: string;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onEndSession: () => void;
  onLanguageChange: (lang: string) => void;
}

export function VoiceControlBar({
  isRecording,
  isInitializing,
  isConnected,
  languageHint,
  onStartRecording,
  onStopRecording,
  onEndSession,
  onLanguageChange
}: VoiceControlBarProps) {

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="flex items-center gap-6 bg-white/80 p-3 px-6 rounded-full shadow-lg border border-gray-100 backdrop-blur-md">
        
        {/* Language Selector */}
        <div className="flex items-center gap-2 pr-4 border-r border-gray-200">
          <Languages className="w-4 h-4 text-gray-400" />
          <select
            value={languageHint}
            onChange={(e) => onLanguageChange(e.target.value)}
            disabled={isRecording}
            className="bg-transparent text-sm font-medium text-gray-600 focus:outline-none cursor-pointer disabled:opacity-50"
          >
            <option value="en">English</option>
            <option value="es">Español</option>
            <option value="fr">Français</option>
            <option value="de">Deutsch</option>
            <option value="hi">हिन्दी</option>
            <option value="ar">العربية</option>
          </select>
        </div>

        {/* Record Button */}
        <button
          onClick={isRecording ? onStopRecording : onStartRecording}
          disabled={!isConnected || isInitializing}
          className={cn(
            "h-14 w-14 rounded-full flex items-center justify-center transition-all shadow-md transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed",
            isRecording 
              ? "bg-red-500 text-white shadow-red-200 animate-pulse" 
              : "bg-cyan-500 text-white shadow-cyan-200 hover:bg-cyan-600"
          )}
        >
          {isInitializing ? (
            <Loader2 className="w-6 h-6 animate-spin" />
          ) : isRecording ? (
            <Square className="w-5 h-5 fill-current" />
          ) : (
            <Mic className="w-6 h-6" />
          )}
        </button>

        {/* End Session Button */}
        <button
          onClick={onEndSession}
          className="h-10 w-10 rounded-full bg-gray-100 text-gray-500 hover:text-red-500 hover:bg-red-50 flex items-center justify-center transition-colors ml-4"
          title="End Session"
        >
          <PhoneOff className="w-4 h-4" />
        </button>
      </div>

      <div className="h-4 flex items-center text-xs font-medium text-gray-400 transition-opacity">
        {isInitializing ? (
          <span className="flex items-center gap-1.5"><Loader2 className="w-3 h-3 animate-spin"/> Connecting...</span>
        ) : isRecording ? (
          <span className="text-red-500 flex items-center gap-1.5 hover:animate-pulse">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
            </span>
            Listening
          </span>
        ) : isConnected ? (
          <span className="text-emerald-500">Connected • Tap to speak</span>
        ) : (
          <span className="text-gray-500">Disconnected</span>
        )}
      </div>
    </div>
  );
}
