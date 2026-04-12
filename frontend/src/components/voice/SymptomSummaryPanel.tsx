"use client";

import React from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  FlaskConical,
  Stethoscope,
  ChevronRight,
  Share2,
  Loader2,
  Heart,
  Thermometer,
  Brain,
} from "lucide-react";

interface SymptomData {
  symptoms: string[];
  urgency: "routine" | "moderate" | "urgent" | "emergency";
  differential: any | null;
  recommended_tests: string[];
  phase: string;
  specialist?: string;
}

interface Props {
  data: SymptomData | null;
  isProcessing: boolean;
  onShareWithDoctor: () => void;
  sharing?: boolean;
  conversationPhase: string;
}

const urgencyConfig = {
  routine: { color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30", label: "Routine", icon: CheckCircle },
  moderate: { color: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/30", label: "Moderate", icon: Activity },
  urgent: { color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30", label: "Urgent", icon: AlertTriangle },
  emergency: { color: "text-red-400", bg: "bg-red-500/10 border-red-500/30", label: "Emergency", icon: AlertTriangle },
};

const phaseLabel: Record<string, string> = {
  initial_intake: "Gathering Symptoms",
  followup_interview: "Asking Follow-ups",
  diagnose: "Analyzing...",
  search_medical_kb: "Searching Medical KB...",
  differential_complete: "Analysis Complete",
  emergency_triage: "Emergency Detected",
};

const symptomIcons: Record<string, React.ElementType> = {
  "heart": Heart,
  "fever": Thermometer,
  "head": Brain,
};

const getSympIconfor = (s: string) => {
  const lower = s.toLowerCase();
  if (lower.includes("heart") || lower.includes("chest")) return Heart;
  if (lower.includes("fever") || lower.includes("temperature")) return Thermometer;
  if (lower.includes("head") || lower.includes("dizz")) return Brain;
  return Activity;
};

export default function SymptomSummaryPanel({ data, isProcessing, onShareWithDoctor, sharing, conversationPhase }: Props) {
  const urgency = data?.urgency || "routine";
  const urg = urgencyConfig[urgency] || urgencyConfig.routine;
  const UrgIcon = urg.icon;

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-300 uppercase tracking-widest">Clinical Summary</h2>
        {isProcessing && (
          <div className="flex items-center gap-1.5 text-xs text-blue-400">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Analyzing...</span>
          </div>
        )}
      </div>

      {/* Phase progress */}
      <div className="bg-slate-800/40 rounded-2xl p-3 border border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
          <span className="text-xs font-semibold text-slate-300">
            {phaseLabel[conversationPhase] || phaseLabel[data?.phase || ""] || "Ready"}
          </span>
        </div>
        {/* Progress dots */}
        <div className="flex gap-2 mt-2.5">
          {["Intake", "Follow-up", "Diagnosis"].map((step, i) => {
            const currentIdx = ["initial_intake", "followup_interview", "differential_complete"].indexOf(data?.phase || "initial_intake");
            const isActive = i <= currentIdx;
            return (
              <React.Fragment key={step}>
                <div className={`flex-1 h-1 rounded-full transition-colors duration-500 ${isActive ? "bg-blue-500" : "bg-slate-700"}`} />
              </React.Fragment>
            );
          })}
        </div>
        <div className="flex justify-between mt-1">
          {["Intake", "Interview", "Diagnosis"].map(s => (
            <span key={s} className="text-[9px] text-slate-500">{s}</span>
          ))}
        </div>
      </div>

      {/* Urgency badge */}
      {data && (
        <div className={`flex items-center gap-2 px-3 py-2.5 rounded-2xl border ${urg.bg}`}>
          <UrgIcon className={`w-4 h-4 ${urg.color}`} />
          <span className={`text-sm font-bold ${urg.color}`}>{urg.label} Priority</span>
        </div>
      )}

      {/* Detected symptoms */}
      <div className="bg-slate-800/40 rounded-2xl p-4 border border-white/5 flex-shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-blue-400" />
          <span className="text-xs font-bold text-slate-300 uppercase tracking-widest">Symptoms Detected</span>
        </div>
        {data?.symptoms && data.symptoms.filter(Boolean).length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {data.symptoms.filter(Boolean).slice(0, 8).map((s, i) => {
              const Icon = getSympIconfor(s);
              return (
                <span key={i} className="flex items-center gap-1 text-xs bg-blue-500/10 text-blue-300 border border-blue-500/20 px-2.5 py-1 rounded-full font-medium">
                  <Icon className="w-3 h-3" />
                  {s}
                </span>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic">Speak to start detecting symptoms...</p>
        )}
      </div>

      {/* Differential diagnosis */}
      {data?.differential && (
        <div className="bg-slate-800/40 rounded-2xl p-4 border border-white/5">
          <div className="flex items-center gap-2 mb-3">
            <Stethoscope className="w-4 h-4 text-purple-400" />
            <span className="text-xs font-bold text-slate-300 uppercase tracking-widest">Differential Diagnosis</span>
          </div>
          {/* Primary */}
          {data.differential.primary_diagnosis && (
            <div className="mb-3 p-3 bg-purple-500/10 border border-purple-500/20 rounded-xl">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-purple-300">
                  {data.differential.primary_diagnosis.condition || "Under evaluation"}
                </span>
                {data.differential.primary_diagnosis.probability && (
                  <span className="text-xs bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full">
                    {data.differential.primary_diagnosis.probability}
                  </span>
                )}
              </div>
            </div>
          )}
          {/* Others */}
          {data.differential.differential?.slice(0, 3).map((d: any, i: number) => (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0">
              <span className="text-xs text-slate-300">{d.condition || d.name}</span>
              <div className="flex items-center gap-1 text-xs text-slate-500">
                <span>{d.probability || d.likelihood || ""}</span>
                <ChevronRight className="w-3 h-3" />
              </div>
            </div>
          ))}
          {/* Specialist */}
          {data.specialist && (
            <div className="mt-3 pt-3 border-t border-white/5 flex items-center gap-2">
              <Stethoscope className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-xs text-cyan-300 font-semibold">Refer to: {data.specialist}</span>
            </div>
          )}
        </div>
      )}

      {/* Recommended tests */}
      {data?.recommended_tests && data.recommended_tests.length > 0 && (
        <div className="bg-slate-800/40 rounded-2xl p-4 border border-white/5">
          <div className="flex items-center gap-2 mb-3">
            <FlaskConical className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-bold text-slate-300 uppercase tracking-widest">Recommended Tests</span>
          </div>
          <ul className="space-y-2">
            {data.recommended_tests.slice(0, 6).map((t, i) => (
              <li key={i} className="flex items-center gap-2 text-xs text-slate-300">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                {typeof t === "string" ? t : (t as any).test || (t as any).name}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Share with doctor */}
      {data?.differential && (
        <button
          onClick={onShareWithDoctor}
          disabled={sharing}
          className="mt-auto w-full flex items-center justify-center gap-2 py-3 px-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 text-white rounded-2xl text-sm font-bold transition-all shadow-lg shadow-cyan-900/30 hover:-translate-y-0.5 active:scale-95"
        >
          {sharing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Share2 className="w-4 h-4" />}
          {sharing ? "Sending to Doctor..." : "Share with My Doctor"}
        </button>
      )}
    </div>
  );
}
