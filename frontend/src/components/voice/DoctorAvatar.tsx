"use client";

import React, { useRef, useEffect, useState } from "react";
import { SimliClient, generateSimliSessionToken, generateIceServers } from "simli-client";
import { useAIDoctorStore, AvatarState } from "@/store/aiDoctorStore";

interface DoctorAvatarProps {
  state: AvatarState;
}

const stateConfig = {
  idle: {
    label: "AWAITING CONNECTION",
    subLabel: "System Ready",
    ringColor: "ring-cyan-500/20",
    glowClass: "shadow-[0_0_50px_rgba(6,182,212,0.15)]",
    bgClass: "bg-[#040814]",
    pulseColor: "border-cyan-500/20"
  },
  listening: {
    label: "PROCESSING AUDIO",
    subLabel: "Acoustic Sensors Active",
    ringColor: "ring-blue-500/50",
    glowClass: "shadow-[0_0_80px_rgba(59,130,246,0.3)]",
    bgClass: "bg-[#040814]",
    pulseColor: "border-blue-500/50"
  },
  speaking: {
    label: "TRANSMITTING DATA",
    subLabel: "AI Synthesis in Progress",
    ringColor: "ring-emerald-400/50",
    glowClass: "shadow-[0_0_100px_rgba(16,185,129,0.35)]",
    bgClass: "bg-[#040814]",
    pulseColor: "border-emerald-500/50"
  },
};

export default function DoctorAvatar({ state }: DoctorAvatarProps) {
  const config = stateConfig[state];

  // Simli AI Integration Hook
  const { simliAudioPCM16, consumeSimliAudio, simliConnected, setSimliConnected } = useAIDoctorStore();
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const simliClientRef = useRef<SimliClient | null>(null);

  useEffect(() => {
    const initSimli = async () => {
      const simliAPIKey = process.env.NEXT_PUBLIC_SIMLI_API_KEY;
      if (!simliAPIKey) {
        console.warn("Simli API Key missing. Avatar will fall back to static photo stream if active.");
        setSimliConnected(false);
        return;
      }

      if (!simliClientRef.current && videoRef.current && audioRef.current) {
        try {
          const iceServers = await generateIceServers(simliAPIKey);
          const sessionObj = await generateSimliSessionToken({
            apiKey: simliAPIKey,
            config: {
              faceId: process.env.NEXT_PUBLIC_SIMLI_FACE_ID || "tmp9i8b3",
              handleSilence: true,
              maxSessionLength: 3600,
              maxIdleTime: 600,
            }
          });

          const client = new SimliClient(
            sessionObj.session_token,
            videoRef.current,
            audioRef.current,
            iceServers
          );

          client.on("error", (detail: string) => {
             console.error("Simli Async Error:", detail);
             setSimliConnected(false);
          });
          
          await client.start();
          simliClientRef.current = client;
          setSimliConnected(true);
        } catch (e) {
          console.error("Failed to initialize Simli:", e);
          setSimliConnected(false);
        }
      }
    };

    initSimli();

    return () => {
      try {
        if (simliClientRef.current) simliClientRef.current.stop();
        setSimliConnected(false);
      } catch (e) {}
    };
  }, []);

  useEffect(() => {
    if (simliAudioPCM16 && simliClientRef.current) {
      simliClientRef.current.sendAudioData(simliAudioPCM16);
      consumeSimliAudio();
    }
  }, [simliAudioPCM16, consumeSimliAudio]);

  return (
    <div className="flex flex-col items-center gap-8 group">
      
      {/* ─── HUD Avatar Container ─── */}
      <div className="relative flex items-center justify-center">
        
        {/* Decorative HUD Rings */}
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent w-[140%] z-0" />
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[1px] bg-gradient-to-b from-transparent via-cyan-500/10 to-transparent h-[140%] z-0" />

        {/* Dynamic State Pulses */}
        {state === "listening" && (
          <>
            <span className="absolute w-[280px] h-[280px] rounded-full border border-blue-500/20 animate-ping" style={{ animationDuration: "2s" }} />
            <span className="absolute w-[320px] h-[320px] rounded-full border border-blue-500/10 animate-ping" style={{ animationDuration: "3s" }} />
          </>
        )}
        {state === "speaking" && (
          <>
             <span className="absolute w-[260px] h-[260px] rounded-full border-[3px] border-emerald-500/30 animate-pulse" style={{ animationDuration: "0.8s" }} />
             <span className="absolute w-[300px] h-[300px] rounded-full border border-emerald-500/10 animate-ping" style={{ animationDuration: "1.5s" }} />
          </>
        )}
        
        {/* Base Ring & Glass Core */}
        <div className="absolute w-[240px] h-[240px] rounded-full border-2 border-white/5 opacity-50 z-0" />
        
        <div
          className={`relative w-48 h-48 rounded-full ring-2 ring-offset-8 ring-offset-[#091124]/50 ${config.ringColor} ${config.glowClass} ${config.bgClass} flex items-center justify-center overflow-hidden transition-all duration-700 z-10`}
          style={{ boxShadow: state === "speaking" ? "0 0 100px rgba(16,185,129,0.4), inset 0 0 40px rgba(16,185,129,0.2)" : undefined }}
        >
          {/* Tech Scan Line Overlay over the video */}
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0)_50%,rgba(0,0,0,0.1)_50%)] bg-[length:100%_4px] mix-blend-overlay z-20 pointer-events-none" />
          
          {/* Simli WebRTC Video Stream */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            className={`w-full h-full object-cover transition-transform duration-[1.5s] z-10 mix-blend-screen opacity-90 ${state === "speaking" ? "scale-105" : "scale-100"} ${!simliConnected ? "hidden" : "block"}`}
          />
          <audio ref={audioRef} autoPlay muted />

          {/* Static Fallback Mesh */}
          <img
            src="/janvi-avatar.png"
            alt="Dr. Janvi AI Avatar"
            className={`absolute w-full h-full object-cover transition-all duration-[2s] ${simliConnected ? "opacity-0 -z-10 scale-110 blur-md" : "opacity-90 z-0 scale-100 blur-0"} 
              ${state === "idle" && !simliConnected ? "animate-breathe mix-blend-screen" : ""}
            `}
          />
          
          {/* Inner Vignette / Shadow */}
          <div className="absolute inset-0 shadow-[inset_0_0_50px_rgba(4,8,20,1)] z-30 pointer-events-none" />
        </div>

        {/* HUD Targeting brackets around the avatar */}
        <div className={`absolute -top-4 -left-4 w-8 h-8 border-t-2 border-l-2 transition-colors duration-500 ${config.pulseColor} opacity-50 z-20`} />
        <div className={`absolute -top-4 -right-4 w-8 h-8 border-t-2 border-r-2 transition-colors duration-500 ${config.pulseColor} opacity-50 z-20`} />
        <div className={`absolute -bottom-4 -left-4 w-8 h-8 border-b-2 border-l-2 transition-colors duration-500 ${config.pulseColor} opacity-50 z-20`} />
        <div className={`absolute -bottom-4 -right-4 w-8 h-8 border-b-2 border-r-2 transition-colors duration-500 ${config.pulseColor} opacity-50 z-20`} />
      </div>

      {/* ─── HUD Status Display ─── */}
      <div className="text-center relative z-20">
        <p className={`text-[11px] uppercase tracking-[0.3em] font-black transition-all duration-500 mb-1 ${
          state === "listening" ? "text-blue-400 drop-shadow-[0_0_8px_rgba(59,130,246,0.8)]" : 
          state === "speaking" ? "text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.8)]" : 
          "text-cyan-500/70"
        }`}>
          {config.label}
        </p>
        <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">{config.subLabel}</p>
        
        {/* Audio Visualizer line */}
        <div className="mt-4 w-32 h-[1px] bg-slate-800 relative mx-auto overflow-hidden">
           {state !== "idle" && (
             <div className={`absolute inset-y-0 left-0 h-full w-full ${state === "listening" ? "bg-blue-500" : "bg-emerald-500"}`} style={{ animation: "pulse 1.5s ease-in-out infinite alternate" }} />
           )}
        </div>
      </div>
    </div>
  );
}
