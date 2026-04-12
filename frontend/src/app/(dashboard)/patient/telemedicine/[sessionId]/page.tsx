"use client";

import React, { useRef, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useParams, useRouter } from "next/navigation";
import { Loader2, AlertCircle, Video } from "lucide-react";
import { useDailyRoom } from "@/hooks/useDailyRoom";
import { CallControls } from "@/components/telemedicine/CallControls";

export default function PatientTelemedicinePage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string; // This is the appointmentId

  const containerRef = useRef<HTMLDivElement>(null);

  const {
    callStatus,
    roomInfo,
    participants,
    isMicOn,
    isCamOn,
    errorMsg,
    initRoom,
    toggleMic,
    toggleCam,
    leave,
  } = useDailyRoom({
    appointmentId: sessionId,
    token: session?.accessToken ?? "",
    role: "patient",
    containerRef,
    userName: session?.user?.name ?? "Patient",
  });

  // Auto-init when session is available
  useEffect(() => {
    if (session?.accessToken && callStatus === "idle") {
      initRoom();
    }
  }, [session?.accessToken, callStatus]);

  // Navigate away when call ends
  useEffect(() => {
    if (callStatus === "ended") {
      router.push("/patient/dashboard");
    }
  }, [callStatus]);

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-gray-950 relative rounded-2xl overflow-hidden">

      {/* Header bar */}
      <div className="absolute top-0 inset-x-0 z-20 flex items-center justify-between px-6 py-4 bg-gradient-to-b from-gray-900 to-transparent">
        <div className="flex items-center gap-2 text-white">
          <Video className="w-5 h-5 text-cyan-400" />
          <span className="font-semibold text-sm">Video Consultation</span>
        </div>
        {callStatus === "joined" && (
          <span className="text-xs bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2.5 py-1 rounded-full font-medium flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            Live
          </span>
        )}
      </div>

      {/* Loading / Error / Idle states (shown when call not yet joined) */}
      {callStatus !== "joined" && callStatus !== "joining" && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-6 bg-gray-950">
          {callStatus === "error" ? (
            <div className="flex flex-col items-center gap-4 text-center max-w-sm px-4">
              <div className="h-16 w-16 rounded-full bg-red-900/30 border border-red-700/40 flex items-center justify-center">
                <AlertCircle className="w-8 h-8 text-red-400" />
              </div>
              <div>
                <h2 className="text-white font-semibold text-lg mb-1">Cannot join call</h2>
                <p className="text-gray-400 text-sm">{errorMsg}</p>
              </div>
              <button
                onClick={initRoom}
                className="px-5 py-2.5 bg-cyan-600 text-white rounded-full text-sm font-medium hover:bg-cyan-500 transition-colors"
              >
                Try Again
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="h-16 w-16 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center">
                <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
              </div>
              <div>
                <h2 className="text-white font-semibold text-lg">Joining your consultation…</h2>
                <p className="text-gray-500 text-sm mt-1">Setting up your secure video connection</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Daily iframe container */}
      <div ref={containerRef} className="flex-1 w-full rounded-none" />

      {/* Controls pinned to bottom */}
      <div className="absolute bottom-0 inset-x-0 z-20 flex flex-col items-center pb-8 pt-4 bg-gradient-to-t from-gray-950 to-transparent">
        <CallControls
          callStatus={callStatus}
          isMicOn={isMicOn}
          isCamOn={isCamOn}
          participants={participants}
          isOwner={false}
          onToggleMic={toggleMic}
          onToggleCam={toggleCam}
          onLeave={leave}
        />
      </div>
    </div>
  );
}
