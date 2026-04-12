"use client";

import React, { useRef, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useParams, useRouter } from "next/navigation";
import {
  Loader2, AlertCircle, Video, Bot, ChevronRight, ChevronLeft,
  HeartPulse, Send, X
} from "lucide-react";
import { useDailyRoom } from "@/hooks/useDailyRoom";
import { CallControls } from "@/components/telemedicine/CallControls";

// ─────────────────────────────────────────────────────────────────────────────
// In-call AI Assistant (side panel)
// ─────────────────────────────────────────────────────────────────────────────

interface AiMessage {
  role: "user" | "assistant";
  content: string;
}

function InCallAiPanel({ token, patientId }: { token: string; patientId?: string }) {
  const [messages, setMessages] = useState<AiMessage[]>([
    { role: "assistant", content: "I'm your in-call AI assistant. Ask me about the patient's history, medications, or lab results during this consultation." }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsLoading(true);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/api/v1/chat/message`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: userMsg,
          patient_id: patientId,
          context: { source: "telemedicine_in_call" },
        }),
      });
      const data = await res.json();
      const reply = data.response || data.content || data.message || "I couldn't retrieve that information.";
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Unable to fetch response. Please try again." }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 border-l border-white/10">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10">
        <div className="h-7 w-7 bg-cyan-500/20 rounded-full flex items-center justify-center">
          <Bot className="w-4 h-4 text-cyan-400" />
        </div>
        <span className="text-white text-sm font-semibold">AI Assistant</span>
        <span className="ml-auto text-xs text-gray-500 font-medium">In-call context</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`h-6 w-6 rounded-full flex-shrink-0 flex items-center justify-center text-[10px] font-bold ${
              msg.role === "assistant" ? "bg-cyan-500/20 text-cyan-400" : "bg-gray-700 text-gray-300"
            }`}>
              {msg.role === "assistant" ? "AI" : "Dr"}
            </div>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
              msg.role === "assistant"
                ? "bg-gray-800 text-gray-100 rounded-tl-sm"
                : "bg-cyan-600/30 text-cyan-100 rounded-tr-sm"
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-2.5">
            <div className="h-6 w-6 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[10px] font-bold">AI</div>
            <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3">
              <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-white/10">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Ask about patient history..."
            className="flex-1 bg-gray-800 text-white text-sm rounded-xl px-4 py-2.5 placeholder:text-gray-500 border border-white/10 focus:outline-none focus:border-cyan-500/50 transition-colors"
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
            className="h-9 w-9 bg-cyan-600 rounded-xl flex items-center justify-center disabled:opacity-50 hover:bg-cyan-500 transition-colors"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Doctor Telemedicine Page
// ─────────────────────────────────────────────────────────────────────────────

export default function DoctorTelemedicinePage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();

  const sessionId = params.sessionId as string; // appointmentId
  const [patientId, setPatientId] = useState<string | undefined>();
  const [showSidePanel, setShowSidePanel] = useState(true);

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
    endForAll,
  } = useDailyRoom({
    appointmentId: sessionId,
    token: session?.accessToken ?? "",
    role: "doctor",
    containerRef,
    userName: session?.user?.name ?? "Doctor",
  });

  // Load appointment to get patient ID for AI context
  useEffect(() => {
    if (!session?.accessToken || !sessionId) return;
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/api/v1/appointments/${sessionId}`, {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    })
      .then((r) => r.json())
      .then((data) => setPatientId(data.patient_id))
      .catch(() => {});
  }, [session?.accessToken, sessionId]);

  // Auto-init
  useEffect(() => {
    if (session?.accessToken && callStatus === "idle") {
      initRoom();
    }
  }, [session?.accessToken, callStatus]);

  // Navigate after call ends
  useEffect(() => {
    if (callStatus === "ended") {
      router.push("/doctor/dashboard");
    }
  }, [callStatus]);

  return (
    <div className="flex h-[calc(100vh-8rem)] bg-gray-950 rounded-2xl overflow-hidden relative">

      {/* ── Main Call Area ── */}
      <div className={`flex flex-col transition-all duration-300 ${showSidePanel ? "flex-1" : "w-full"}`}>

        {/* Header */}
        <div className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-6 py-4 bg-gradient-to-b from-gray-900 to-transparent"
          style={{ right: showSidePanel ? "320px" : "0" }}>
          <div className="flex items-center gap-2 text-white">
            <Video className="w-5 h-5 text-cyan-400" />
            <span className="font-semibold text-sm">Video Consultation</span>
            {patientId && (
              <span className="ml-2 text-xs text-gray-400 font-medium flex items-center gap-1">
                <HeartPulse className="w-3 h-3" /> Patient context loaded
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {callStatus === "joined" && (
              <span className="text-xs bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2.5 py-1 rounded-full font-medium flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
                Live
              </span>
            )}
            <button
              onClick={() => setShowSidePanel((v) => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800/80 backdrop-blur text-gray-300 text-xs font-medium rounded-lg border border-white/10 hover:bg-gray-700 transition-colors"
            >
              <Bot className="w-3.5 h-3.5" />
              {showSidePanel ? <><ChevronRight className="w-3 h-3" /> Hide AI</> : <><ChevronLeft className="w-3 h-3" /> AI Assistant</>}
            </button>
          </div>
        </div>

        {/* Loading / Error state */}
        {callStatus !== "joined" && callStatus !== "joining" && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-6 bg-gray-950"
            style={{ right: showSidePanel ? "320px" : "0" }}>
            {callStatus === "error" ? (
              <div className="flex flex-col items-center gap-4 text-center max-w-sm px-4">
                <div className="h-16 w-16 rounded-full bg-red-900/30 border border-red-700/40 flex items-center justify-center">
                  <AlertCircle className="w-8 h-8 text-red-400" />
                </div>
                <div>
                  <h2 className="text-white font-semibold text-lg mb-1">Cannot start call</h2>
                  <p className="text-gray-400 text-sm">{errorMsg}</p>
                </div>
                <button onClick={initRoom} className="px-5 py-2.5 bg-cyan-600 text-white rounded-full text-sm font-medium hover:bg-cyan-500 transition-colors">
                  Retry
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4 text-center">
                <div className="h-16 w-16 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center">
                  <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
                </div>
                <div>
                  <h2 className="text-white font-semibold text-lg">Starting consultation…</h2>
                  <p className="text-gray-500 text-sm mt-1">Creating your secure video room</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Daily iframe */}
        <div ref={containerRef} className="flex-1 w-full" />

        {/* Controls */}
        <div className="absolute bottom-0 left-0 z-20 flex flex-col items-center pb-8 pt-4 bg-gradient-to-t from-gray-950 to-transparent"
          style={{ right: showSidePanel ? "320px" : "0" }}>
          <CallControls
            callStatus={callStatus}
            isMicOn={isMicOn}
            isCamOn={isCamOn}
            participants={participants}
            isOwner={true}
            onToggleMic={toggleMic}
            onToggleCam={toggleCam}
            onLeave={leave}
            onEndForAll={endForAll}
          />
        </div>
      </div>

      {/* ── Side Panel: AI Assistant ── */}
      {showSidePanel && (
        <div className="w-[320px] flex-shrink-0 border-l border-white/10">
          <InCallAiPanel
            token={session?.accessToken ?? ""}
            patientId={patientId}
          />
        </div>
      )}
    </div>
  );
}
