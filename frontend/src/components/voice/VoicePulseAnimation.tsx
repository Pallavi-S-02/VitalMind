"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface VoicePulseAnimationProps {
  isRecording: boolean;
  isPlaying: boolean;
  volumeLog: number[];
}

export function VoicePulseAnimation({ isRecording, isPlaying, volumeLog }: VoicePulseAnimationProps) {
  // We use the volume history array to render a dynamic audio visualizer bar set
  
  if (!isRecording && !isPlaying) {
    return (
      <div className="flex items-center justify-center h-24 gap-1">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="w-2 h-2 bg-gray-300 rounded-full" />
        ))}
      </div>
    );
  }

  // Active state: animating
  return (
    <div className="flex items-center justify-center h-24 gap-1.5 opacity-90 transition-opacity">
      {volumeLog.slice(0, 10).map((vol, i) => {
        // Calculate bar height based on volume (0-255 roughly)
        // Ensure a minimum height for visibility
        const isPulse = isPlaying ? (Math.random() * 50 + 50) : vol; // mock playback pulse if no analzyer available for speaker
        const heightPercentage = Math.max(10, Math.min(100, (isPulse / 255) * 100 * 1.5));
        
        return (
          <div
            key={i}
            className={cn(
              "w-2.5 rounded-full transition-all duration-75 ease-out",
              isRecording ? "bg-red-500" : "bg-cyan-500" // Red for recording, cyan for speaking
            )}
            style={{
              height: `${heightPercentage}%`,
            }}
          />
        );
      })}
    </div>
  );
}
