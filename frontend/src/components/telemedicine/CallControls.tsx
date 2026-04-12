"use client";

import React from "react";
import { Mic, MicOff, Video, VideoOff, PhoneOff, Users, Loader2 } from "lucide-react";
import { CallStatus, Participant } from "@/hooks/useDailyRoom";
import { cn } from "@/lib/utils";

interface CallControlsProps {
  callStatus: CallStatus;
  isMicOn: boolean;
  isCamOn: boolean;
  participants: Participant[];
  isOwner: boolean;
  onToggleMic: () => void;
  onToggleCam: () => void;
  onLeave: () => void;
  onEndForAll?: () => void;
}

export function CallControls({
  callStatus,
  isMicOn,
  isCamOn,
  participants,
  isOwner,
  onToggleMic,
  onToggleCam,
  onLeave,
  onEndForAll,
}: CallControlsProps) {
  const isActive = callStatus === "joined";
  const remoteCount = participants.filter((p) => !p.local).length;

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Participant count */}
      {isActive && (
        <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500 bg-white/80 px-3 py-1 rounded-full border border-gray-100">
          <Users className="w-3.5 h-3.5" />
          <span>{remoteCount} other{remoteCount !== 1 ? "s" : ""} in call</span>
          <span className="relative flex h-2 w-2 ml-1">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
        </div>
      )}

      {/* Main controls */}
      <div className="flex items-center gap-4 bg-gray-900/90 backdrop-blur-md px-6 py-3 rounded-2xl shadow-xl border border-white/10">

        {/* Mic */}
        <button
          onClick={onToggleMic}
          disabled={!isActive}
          title={isMicOn ? "Mute microphone" : "Unmute microphone"}
          className={cn(
            "h-11 w-11 rounded-full flex items-center justify-center transition-all",
            "disabled:opacity-40 disabled:cursor-not-allowed",
            isMicOn
              ? "bg-white/10 text-white hover:bg-white/20"
              : "bg-red-500/90 text-white hover:bg-red-500"
          )}
        >
          {isMicOn ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
        </button>

        {/* Camera */}
        <button
          onClick={onToggleCam}
          disabled={!isActive}
          title={isCamOn ? "Turn off camera" : "Turn on camera"}
          className={cn(
            "h-11 w-11 rounded-full flex items-center justify-center transition-all",
            "disabled:opacity-40 disabled:cursor-not-allowed",
            isCamOn
              ? "bg-white/10 text-white hover:bg-white/20"
              : "bg-red-500/90 text-white hover:bg-red-500"
          )}
        >
          {isCamOn ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
        </button>

        {/* Divider */}
        <div className="w-px h-8 bg-white/10" />

        {/* Leave / End call */}
        {isOwner && onEndForAll ? (
          <button
            onClick={onEndForAll}
            disabled={!isActive}
            title="End call for everyone"
            className="h-11 px-4 bg-red-600 text-white rounded-full flex items-center gap-2 text-sm font-semibold hover:bg-red-700 transition-colors disabled:opacity-40"
          >
            <PhoneOff className="w-4 h-4" />
            End for All
          </button>
        ) : (
          <button
            onClick={onLeave}
            disabled={callStatus === "leaving"}
            title="Leave call"
            className="h-11 w-11 bg-red-600 text-white rounded-full flex items-center justify-center hover:bg-red-700 transition-colors disabled:opacity-40"
          >
            {callStatus === "leaving"
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <PhoneOff className="w-4 h-4" />}
          </button>
        )}
      </div>

      {/* Status label */}
      {callStatus === "joining" && (
        <p className="text-xs text-gray-400 animate-pulse flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin" /> Connecting to call...
        </p>
      )}
    </div>
  );
}
