"use client";

import React, { useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  Mic, Phone, ChevronLeft, Globe2,
  CheckCircle2, AlertCircle, Loader2, MessageCircle,
  Stethoscope, Activity, Radio, Volume2, Zap, Wifi,
} from "lucide-react";
import DoctorAvatar from "@/components/voice/DoctorAvatar";
import SymptomSummaryPanel from "@/components/voice/SymptomSummaryPanel";
import { useAIDoctorStore } from "@/store/aiDoctorStore";

const LANGUAGES = [
  { code: "en", label: "English",  flag: "🇬🇧" },
  { code: "hi", label: "Hindi",    flag: "🇮🇳" },
  { code: "mr", label: "Marathi",  flag: "🇮🇳" },
  { code: "ta", label: "Tamil",    flag: "🇮🇳" },
  { code: "te", label: "Telugu",   flag: "🇮🇳" },
  { code: "kn", label: "Kannada",  flag: "🇮🇳" },
  { code: "bn", label: "Bengali",  flag: "🇮🇳" },
];

export default function AIDoctorPage() {
  const { data: session }  = useSession();
  const router             = useRouter();
  const transcriptRef      = useRef<HTMLDivElement>(null);

  const {
    sessionId, isSessionActive, language,
    isListening, isProcessing, isSpeaking,
    avatarState, turns, conversationPhase,
    symptomSummary, isSharingWithDoctor, sharedWithDoctor, error,
    startSession, startListening, stopListening,
    shareWithDoctor, setLanguage, endSession, clearError,
    turnCount,
  } = useAIDoctorStore();

  const [showLangMenu, setShowLangMenu] = useState(false);

  // ── Start session on mount ───────────────────────────────────────────────
  useEffect(() => {
    if (session?.accessToken && session?.user?.id && !isSessionActive) {
      startSession(session.accessToken, session.user.id);
    }
    return () => { endSession(); };
  }, [session]);

  // ── Auto-scroll transcript ───────────────────────────────────────────────
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [turns]);

  const handleMicToggle = () => {
    if (!isSessionActive) return;
    if (isListening) stopListening();
    else             startListening();
  };

  const handleShareWithDoctor = async () => {
    if (session?.accessToken) await shareWithDoctor(session.accessToken);
  };

  const currentLang = LANGUAGES.find(l => l.code === language) || LANGUAGES[0];

  // ── Status bar label ────────────────────────────────────────────────────
  const statusLabel = (() => {
    if (!isSessionActive)  return "Connecting…";
    if (avatarState === "connecting") return "Establishing Link…";
    if (isSpeaking)        return "Dr. Janvi Speaking";
    if (isProcessing)      return "Processing…";
    if (isListening)       return "Acoustic Sensors Active";
    return "System Awaiting Input";
  })();

  const statusColor = (() => {
    if (isSpeaking)  return "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]";
    if (isListening) return "bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.2)]";
    if (isProcessing) return "bg-amber-500/10 border-amber-500/30 text-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.2)]";
    return "bg-slate-800/50 border-slate-700/50 text-slate-400";
  })();

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] bg-[#040814] rounded-3xl overflow-hidden relative shadow-2xl border border-white/5 ring-1 ring-white/10 font-sans">

      {/* ─── Premium Ambient Background ─── */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden z-0">
        <div className={`absolute -top-32 -left-32 w-[40rem] h-[40rem] rounded-full blur-[120px] opacity-30 mix-blend-screen transition-all duration-[2000ms] ease-in-out ${
          isListening ? "bg-blue-600 scale-110" : isSpeaking ? "bg-emerald-600 scale-100 translate-x-10" : "bg-cyan-900 scale-90"
        }`} />
        <div className="absolute top-1/2 right-1/4 w-[30rem] h-[30rem] rounded-full blur-[100px] opacity-20 bg-indigo-800 mix-blend-screen" />
        <div className={`absolute -bottom-32 left-1/3 w-[50rem] h-[20rem] rounded-full blur-[100px] opacity-20 mix-blend-screen transition-colors duration-[3000ms] ${
          isListening ? "bg-rose-900" : "bg-blue-900"
        }`} />
        <div
          className="absolute inset-0 opacity-[0.03] mix-blend-screen"
          style={{
            backgroundImage: "linear-gradient(rgba(255, 255, 255, 1) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 1) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
      </div>

      {/* ─── Top Bar Glass Header ─── */}
      <div className="relative z-50 flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#091124]/60 backdrop-blur-xl shadow-lg">

        {/* Left: Back */}
        <div className="flex-1 flex justify-start">
          <button
            onClick={() => { endSession(); router.push("/patient/dashboard"); }}
            className="group flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition-all border border-white/5 hover:border-white/10 shadow-sm"
          >
            <ChevronLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
            <span className="text-sm font-semibold tracking-wide">Leave</span>
          </button>
        </div>

        {/* Center */}
        <div className="flex-1 flex flex-col items-center justify-center">
          <div className="flex items-center gap-2.5">
            <div className="relative flex items-center justify-center">
              <div className={`absolute w-4 h-4 rounded-full ${isSessionActive ? "bg-emerald-500/20 animate-ping duration-[3s]" : "bg-slate-600/20"}`} />
              <div className={`relative w-2 h-2 rounded-full ${isSessionActive ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]" : "bg-slate-500"}`} />
            </div>
            <span className="text-xs font-black text-white tracking-[0.2em]">Dr. Janvi</span>
          </div>
          {isSessionActive && (
            <div className="text-[10px] text-cyan-400/70 font-mono tracking-widest mt-1 uppercase flex items-center gap-1.5 opacity-80">
              <Radio className="w-3 h-3 text-cyan-500 animate-pulse" />
              Gemini Live — Real-time Audio
            </div>
          )}
        </div>

        {/* Right: Language */}
        <div className="flex-1 flex justify-end relative">
          <button
            onClick={() => setShowLangMenu(!showLangMenu)}
            className="flex items-center gap-2.5 px-4 py-2 bg-[#0c162d] hover:bg-[#111e3b] rounded-xl border border-white/10 hover:border-white/20 text-xs font-bold text-slate-200 transition-all shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
          >
            <Globe2 className="w-4 h-4 text-cyan-400" />
            <span>{currentLang.flag} {currentLang.label}</span>
          </button>

          {showLangMenu && (
            <div className="absolute right-0 top-12 z-50 bg-[#0c162d]/95 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] overflow-hidden w-48 ring-1 ring-white/5 animate-in slide-in-from-top-2 fade-in duration-200">
              <div className="px-4 py-2 border-b border-white/5 bg-white/5">
                <span className="text-[10px] uppercase tracking-widest font-bold text-slate-400">Select Dialect</span>
              </div>
              <div className="p-1">
                {LANGUAGES.map(l => (
                  <button
                    key={l.code}
                    onClick={() => { setLanguage(l.code); setShowLangMenu(false); }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                      language === l.code
                        ? "bg-cyan-500/10 text-cyan-400 font-bold"
                        : "text-slate-300 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <span>{l.flag}</span>
                    <span>{l.label}</span>
                    {language === l.code && <CheckCircle2 className="w-4 h-4 ml-auto" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ─── Main Interface Grid ─── */}
      <div className="relative z-10 flex flex-1 overflow-hidden h-full">

        {/* ─── Left Panel: Avatar & Controls ─── */}
        <div className="flex flex-col items-center py-10 px-8 w-[340px] flex-shrink-0 border-r border-white/5 bg-[#091124]/30 backdrop-blur-md relative">

          <div className="absolute top-0 right-0 w-px h-full bg-gradient-to-b from-transparent via-white/10 to-transparent" />

          {/* Avatar */}
          <div className="flex-1 w-full flex flex-col items-center justify-center relative">
            <div className={`absolute top-0 flex items-center gap-2 px-4 py-1.5 rounded-full border text-[10px] uppercase tracking-[0.2em] font-black transition-all duration-500 ${statusColor}`}>
              {isSpeaking  ? <Volume2 className="w-3 h-3" /> :
               isListening ? <Mic className="w-3 h-3" />    :
               isProcessing ? <Loader2 className="w-3 h-3 animate-spin" /> :
               <Activity className="w-3 h-3" />}
              {statusLabel}
            </div>

            <div className="transform hover:scale-105 transition-transform duration-700 mt-8">
              <DoctorAvatar state={avatarState} />
            </div>

            {/* Live indicator */}
            {isSessionActive && (
              <div className="mt-6 flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                <Wifi className="w-3 h-3 text-emerald-400 animate-pulse" />
                <span className="text-[10px] font-bold text-emerald-400 tracking-wider uppercase">AI Doctor Connected</span>
              </div>
            )}
          </div>

          {/* Controls */}
          <div className="w-full space-y-4 relative z-20">
            {error && (
              <div className="flex items-start gap-3 bg-red-950/50 border border-red-500/40 rounded-2xl p-4 shadow-[0_0_20px_rgba(239,68,68,0.15)] animate-in slide-in-from-bottom-4">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-red-400 uppercase tracking-wider mb-1">System Error</p>
                  <p className="text-xs text-red-200/80 leading-relaxed">{error}</p>
                </div>
                <button onClick={clearError} className="text-red-500 hover:text-red-300 transition-colors p-1 bg-red-950 rounded-lg">✕</button>
              </div>
            )}

            {sharedWithDoctor && (
              <div className="flex items-center gap-3 bg-emerald-950/50 border border-emerald-500/40 rounded-2xl p-4 animate-in slide-in-from-bottom-4">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <div className="flex-1">
                  <p className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Sync Complete</p>
                  <p className="text-xs text-emerald-200/80 mt-0.5">Summary dispatched to medical vault.</p>
                </div>
              </div>
            )}

            {/* ── Mic Toggle / Live Status Button ── */}
            <button
              onClick={handleMicToggle}
              disabled={!isSessionActive || avatarState === "connecting"}
              className={`relative w-full group overflow-hidden rounded-[2rem] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed transform active:scale-[0.98]
                ${isListening
                  ? "bg-red-600 shadow-[0_0_40px_rgba(220,38,38,0.6)] ring-2 ring-red-400 ring-offset-2 ring-offset-[#040814]"
                  : isSpeaking
                  ? "bg-gradient-to-br from-emerald-500 to-teal-600 shadow-[0_0_30px_rgba(16,185,129,0.4)] ring-1 ring-white/10"
                  : "bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_30px_rgba(6,182,212,0.3)] hover:shadow-[0_0_40px_rgba(6,182,212,0.5)] ring-1 ring-white/10"
                }`}
            >
              <div className="relative z-10 flex items-center justify-center gap-3 py-5 text-white font-black tracking-wide">
                {avatarState === "connecting" ? (
                  <><Loader2 className="w-5 h-5 animate-spin" /> CONNECTING…</>
                ) : isProcessing && !isListening ? (
                  <><Loader2 className="w-5 h-5 animate-spin" /> PROCESSING…</>
                ) : isSpeaking ? (
                  <><Volume2 className="w-5 h-5" /> DR. JANVI SPEAKING</>
                ) : isListening ? (
                  <><Mic className="w-5 h-5 animate-pulse" /> LISTENING — TAP TO PAUSE</>
                ) : (
                  <><Mic className="w-6 h-6 group-hover:scale-110 transition-transform" /> TAP TO SPEAK</>
                )}
              </div>
              <div className="absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-white/50 to-transparent opacity-50 z-20" />
              <div className="absolute inset-0 bg-gradient-to-b from-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity z-0" />
              {isListening && (
                <div className="absolute inset-0 flex items-center gap-[2px] opacity-20 justify-center z-0 w-full overflow-hidden">
                  {[...Array(40)].map((_, i) => (
                    <div key={i} className="w-[3px] bg-white rounded-full animate-pulse"
                      style={{ height: `${Math.random() * 100}%`, animationDuration: `${Math.random() * 0.5 + 0.3}s` }} />
                  ))}
                </div>
              )}
            </button>

            {/* Status hint */}
            <div className={`flex items-center justify-center gap-2 text-[10px] font-bold uppercase tracking-[0.15em] transition-colors ${
              isSessionActive ? "text-emerald-400" : "text-amber-400"
            }`}>
              {isSessionActive ? (
                <><Zap className="w-3 h-3" /> AI Doctor Active — speak naturally</>
              ) : (
                <><Loader2 className="w-3 h-3 animate-spin" /> Establishing connection…</>
              )}
            </div>

            {/* Terminate */}
            <button
              onClick={() => { endSession(); router.push("/patient/dashboard"); }}
              className="w-full flex items-center justify-center gap-2 py-4 text-[11px] uppercase tracking-[0.2em] font-bold text-slate-500 hover:text-rose-400 transition-colors"
            >
              <Phone className="w-3.5 h-3.5" />
              Terminate Link
            </button>
          </div>
        </div>

        {/* ─── Middle Panel: Conversation Feed ─── */}
        <div className="flex-1 flex flex-col min-w-0 relative bg-[#060b17]/50 backdrop-blur-sm border-r border-white/5">

          {/* Transcript Header */}
          <div className="px-8 py-4 border-b border-white/5 flex items-center gap-4 bg-gradient-to-b from-[#091124] to-transparent">
            <div className="p-2 bg-blue-900/40 rounded-lg border border-blue-500/20 shadow-[0_0_15px_rgba(59,130,246,0.15)]">
              <MessageCircle className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-200 tracking-wide">Secure Data Link</h3>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest mt-0.5">Encrypted End-to-End Chat Feed</p>
            </div>
            {turnCount > 0 && (
              <div className="ml-auto flex flex-col items-end">
                <span className="text-xl font-light text-cyan-400 font-mono">{turnCount}</span>
                <span className="text-[9px] uppercase tracking-widest text-slate-500">Exchanges</span>
              </div>
            )}
          </div>

          {/* Message List */}
          <div ref={transcriptRef} className="flex-1 overflow-y-auto px-8 py-8 space-y-6 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10 z-10">
            {turns.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center gap-6 opacity-60 max-w-md mx-auto animate-in zoom-in-95 duration-[1s]">
                <div className="w-24 h-24 rounded-full border-2 border-dashed border-slate-600/50 flex items-center justify-center relative bg-[#091124]">
                  <div className="absolute inset-0 bg-blue-500/5 rounded-full animate-ping duration-[3s]" />
                  <Stethoscope className="w-10 h-10 text-cyan-500 opacity-80" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-2xl font-light text-white tracking-widest font-outfit">
                    {isSessionActive ? "Ready — Speak Now" : "Awaiting Connection"}
                  </h2>
                  <p className="text-sm text-slate-400 font-medium leading-relaxed px-6">
                    {isSessionActive
                      ? "Dr. Janvi is listening. Speak naturally in any language — Hindi, English, or mix."
                      : "Establishing your secure real-time audio link with Dr. Janvi…"}
                  </p>
                </div>
              </div>
            ) : (
              turns.map((turn, i) => (
                <div key={i} className={`flex ${turn.role === "patient" ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-4 duration-500`}>
                  {turn.role === "doctor" && (
                    <div className="flex-shrink-0 mr-4 mt-2">
                      <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#0c162d] to-[#121f3d] border border-white/10 flex items-center justify-center shadow-[0_0_20px_rgba(0,0,0,0.5)]">
                        <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                      </div>
                    </div>
                  )}
                  <div className={`max-w-[75%] relative overflow-hidden backdrop-blur-xl ${
                    turn.role === "patient"
                      ? "bg-blue-600/10 border border-blue-500/20 text-blue-50 rounded-3xl rounded-tr-sm shadow-[0_4px_30px_rgba(37,99,235,0.05)]"
                      : "bg-[#0f172a]/80 border border-slate-700/50 text-slate-200 rounded-3xl rounded-tl-sm shadow-[0_4px_30px_rgba(0,0,0,0.2)]"
                  }`}>
                    <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent pointer-events-none" />
                    <div className="p-5 text-[15px] font-medium leading-relaxed relative z-10">
                      {turn.text}
                    </div>
                    <div className="px-5 py-2.5 bg-black/20 border-t border-white/5 flex items-center justify-between z-10 relative">
                      <span className="text-[10px] font-black uppercase tracking-widest text-[#64748b]">
                        {turn.role === "patient" ? "USER INPUT" : "AI SYNTHESIS"}
                        {turn.language && turn.language !== "en" && ` [${turn.language}]`}
                      </span>
                      <span className="text-[10px] font-mono text-[#64748b]">
                        {new Date(turn.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}

            {/* Live listening indicator */}
            {isListening && (
              <div className="flex justify-end">
                <div className="px-6 py-4 rounded-3xl rounded-tr-sm bg-blue-500/5 border border-blue-500/20 flex gap-2 items-center">
                  {[0.2, 0.4, 0.6, 0.8, 1].map((o, i) => (
                    <span
                      key={i}
                      className="w-1.5 h-6 rounded-full bg-blue-400"
                      style={{ animation: "pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite", animationDelay: `${i * 0.15}s`, opacity: o }}
                    />
                  ))}
                  <span className="text-[10px] uppercase font-bold text-blue-400 ml-2 tracking-wider">Streaming to Gemini Live…</span>
                </div>
              </div>
            )}

            {/* Speaking indicator */}
            {isSpeaking && (
              <div className="flex justify-start">
                <div className="px-6 py-4 rounded-3xl rounded-tl-sm bg-emerald-500/5 border border-emerald-500/20 flex gap-2 items-center">
                  {[1, 0.8, 0.6, 0.8, 1].map((o, i) => (
                    <span
                      key={i}
                      className="w-1.5 h-6 rounded-full bg-emerald-400"
                      style={{ animation: "pulse 0.8s cubic-bezier(0.4, 0, 0.6, 1) infinite", animationDelay: `${i * 0.1}s`, opacity: o }}
                    />
                  ))}
                  <span className="text-[10px] uppercase font-bold text-emerald-400 ml-2 tracking-wider">Dr. Janvi Speaking…</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ─── Right Panel: Clinical Summary ─── */}
        <div className="w-[340px] flex-shrink-0 bg-[#091124]/30 backdrop-blur-md relative overflow-y-auto scrollbar-none z-20 shadow-[-20px_0_40px_-5px_rgba(0,0,0,0.5)]">
          <SymptomSummaryPanel
            data={symptomSummary}
            isProcessing={isProcessing}
            onShareWithDoctor={handleShareWithDoctor}
            sharing={isSharingWithDoctor}
            conversationPhase={conversationPhase}
          />
        </div>
      </div>
    </div>
  );
}
