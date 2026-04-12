"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Pill,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  Info,
  Loader2,
  Plus,
  Minus,
  RefreshCw,
  Calendar,
  ChevronDown,
  ChevronUp,
  ArrowRight,
} from "lucide-react";
import { useSession } from "next-auth/react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface Alert {
  type: "interaction" | "allergy" | "dosage";
  severity: "CONTRAINDICATED" | "MAJOR" | "MODERATE" | "MINOR";
  drugs_involved: string[];
  summary: string;
  mechanism: string;
  patient_risk: string;
  recommendation: string;
}

interface InteractionResult {
  session_id: string;
  overall_safety_rating: "SAFE" | "CAUTION" | "UNSAFE" | "CRITICAL";
  total_interactions: number;
  critical_alerts: Alert[];
  moderate_warnings: Alert[];
  minor_notes: Alert[];
  response: string;
  medications_analyzed: string;
  schedule: string;
  alert_sent: boolean;
  urgency: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper components
// ─────────────────────────────────────────────────────────────────────────────

const SEVERITY_CONFIG = {
  CONTRAINDICATED: {
    color: "bg-red-950 border-red-800 text-red-100",
    badge: "bg-red-900 text-red-200 border border-red-700",
    icon: XCircle,
    iconColor: "text-red-400",
    label: "Contraindicated",
  },
  MAJOR: {
    color: "bg-orange-950 border-orange-800 text-orange-100",
    badge: "bg-orange-900 text-orange-200 border border-orange-700",
    icon: AlertTriangle,
    iconColor: "text-orange-400",
    label: "Major",
  },
  MODERATE: {
    color: "bg-yellow-950 border-yellow-800 text-yellow-100",
    badge: "bg-yellow-900 text-yellow-200 border border-yellow-700",
    icon: AlertTriangle,
    iconColor: "text-yellow-400",
    label: "Moderate",
  },
  MINOR: {
    color: "bg-blue-950 border-blue-800 text-blue-100",
    badge: "bg-blue-900 text-blue-200 border border-blue-700",
    icon: Info,
    iconColor: "text-blue-400",
    label: "Minor",
  },
};

const RATING_CONFIG = {
  SAFE: {
    gradient: "from-emerald-900/60 to-emerald-800/40",
    border: "border-emerald-700/50",
    text: "text-emerald-300",
    badgeBg: "bg-emerald-900",
    badgeText: "text-emerald-200",
    icon: ShieldCheck,
    label: "Safe",
    description: "No significant interactions detected",
  },
  CAUTION: {
    gradient: "from-yellow-900/60 to-yellow-800/40",
    border: "border-yellow-700/50",
    text: "text-yellow-300",
    badgeBg: "bg-yellow-900",
    badgeText: "text-yellow-200",
    icon: AlertTriangle,
    label: "Caution",
    description: "Some interactions require attention",
  },
  UNSAFE: {
    gradient: "from-orange-900/60 to-orange-800/40",
    border: "border-orange-700/50",
    text: "text-orange-300",
    badgeBg: "bg-orange-900",
    badgeText: "text-orange-200",
    icon: AlertTriangle,
    label: "Unsafe",
    description: "Significant interactions found — consult your doctor",
  },
  CRITICAL: {
    gradient: "from-red-900/60 to-red-800/40",
    border: "border-red-700/50",
    text: "text-red-300",
    badgeBg: "bg-red-900",
    badgeText: "text-red-200",
    icon: XCircle,
    label: "Critical",
    description: "Dangerous interactions — immediate medical attention required",
  },
};

function AlertCard({ alert }: { alert: Alert }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.MINOR;
  const Icon = cfg.icon;

  return (
    <div
      className={`rounded-2xl border p-5 transition-all duration-200 ${cfg.color} hover:brightness-110`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Icon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${cfg.iconColor}`} />
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cfg.badge}`}>
                {cfg.label}
              </span>
              {alert.drugs_involved.map((d) => (
                <span
                  key={d}
                  className="text-xs font-mono px-2 py-0.5 rounded-full bg-white/10 text-white/80"
                >
                  {d}
                </span>
              ))}
            </div>
            <p className="mt-2 text-sm font-medium leading-relaxed">{alert.summary}</p>
          </div>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex-shrink-0 p-1 rounded-lg hover:bg-white/10 transition-colors"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 space-y-3 pt-4 border-t border-white/10 text-sm text-white/80">
          {alert.mechanism && (
            <div>
              <p className="font-semibold text-white/90 mb-1">⚗️ Mechanism</p>
              <p>{alert.mechanism}</p>
            </div>
          )}
          {alert.patient_risk && (
            <div>
              <p className="font-semibold text-white/90 mb-1">⚠️ What to watch for</p>
              <p>{alert.patient_risk}</p>
            </div>
          )}
          {alert.recommendation && (
            <div className="bg-white/10 rounded-xl p-3">
              <p className="font-semibold text-white mb-1">✅ Recommendation</p>
              <p>{alert.recommendation}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function InteractionsPage() {
  const { data: session } = useSession();

  const [medications, setMedications] = useState<string[]>([""]);
  const [customQuestion, setCustomQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<InteractionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"analysis" | "schedule">("analysis");
  const [showSchedule, setShowSchedule] = useState(false);

  const addMedication = () => setMedications((prev) => [...prev, ""]);
  const removeMedication = (i: number) =>
    setMedications((prev) => prev.filter((_, idx) => idx !== i));
  const updateMedication = (i: number, val: string) =>
    setMedications((prev) => prev.map((m, idx) => (idx === i ? val : m)));

  const runCheck = async () => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    const cleanMeds = medications.filter((m) => m.trim());
    if (cleanMeds.length === 0 && !customQuestion.trim()) {
      setError("Please enter at least one medication or a question about your medications.");
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API}/api/v1/medications/check-interactions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify({
          patient_id: session?.user?.id,
          message:
            customQuestion.trim() ||
            "Please review my medications for any interactions or safety concerns.",
          medications: cleanMeds,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || `Server error ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
      setActiveTab("analysis");
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  const ratingCfg =
    result ? (RATING_CONFIG[result.overall_safety_rating] ?? RATING_CONFIG.CAUTION) : null;

  return (
    <div
      className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      {/* Header */}
      <div className="px-6 pt-8 pb-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2.5 bg-violet-600/20 border border-violet-500/30 rounded-xl">
                <Pill className="h-6 w-6 text-violet-400" />
              </div>
              <h1 className="text-3xl font-bold text-white tracking-tight">
                Drug Interaction Checker
              </h1>
            </div>
            <p className="text-gray-400 ml-[52px]">
              AI-powered medication safety analysis. Know your risks before they find you.
            </p>
          </div>
          <Link
            href={`/patient/medications/${session?.user?.id}/schedule`}
            className="hidden sm:flex items-center gap-2 px-4 py-2.5 bg-violet-600/20 border border-violet-500/30 rounded-xl text-violet-300 text-sm font-medium hover:bg-violet-600/30 transition-colors"
          >
            <Calendar className="h-4 w-4" />
            View Schedule
          </Link>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 pb-16 space-y-6">
        {/* Input Section */}
        <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
          <h2 className="text-lg font-semibold text-white mb-1">Your Medications</h2>
          <p className="text-sm text-gray-400 mb-5">
            Enter your medications or ask a specific question about your regimen.
          </p>

          <div className="space-y-3 mb-5">
            {medications.map((med, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="flex-1 relative">
                  <Pill className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                  <input
                    id={`medication-input-${i}`}
                    type="text"
                    value={med}
                    onChange={(e) => updateMedication(i, e.target.value)}
                    placeholder={`e.g. warfarin 5mg daily`}
                    className="w-full bg-gray-800/80 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all text-sm"
                  />
                </div>
                {medications.length > 1 && (
                  <button
                    onClick={() => removeMedication(i)}
                    className="p-2.5 rounded-xl bg-red-900/30 border border-red-800/30 text-red-400 hover:bg-red-900/50 transition-colors"
                    aria-label="Remove medication"
                  >
                    <Minus className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>

          <button
            onClick={addMedication}
            className="flex items-center gap-2 text-sm text-violet-400 hover:text-violet-300 transition-colors mb-6"
          >
            <Plus className="h-4 w-4" />
            Add another medication
          </button>

          <div className="mb-5">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Specific question (optional)
            </label>
            <textarea
              id="drug-interaction-question"
              value={customQuestion}
              onChange={(e) => setCustomQuestion(e.target.value)}
              placeholder="e.g. Is it safe to take ibuprofen with my warfarin? Can I drink grapefruit juice?"
              rows={3}
              className="w-full bg-gray-800/80 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all text-sm resize-none"
            />
          </div>

          {error && (
            <div className="mb-4 flex items-start gap-3 bg-red-900/20 border border-red-800/40 rounded-xl p-4 text-red-300 text-sm">
              <XCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <button
            id="run-interaction-check"
            onClick={runCheck}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-3 py-3.5 px-6 bg-violet-600 hover:bg-violet-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-violet-900/40 text-sm"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Analyzing medications...
              </>
            ) : (
              <>
                <ShieldCheck className="h-5 w-5" />
                Check Interactions
              </>
            )}
          </button>
        </div>

        {/* Results */}
        {result && ratingCfg && (
          <div className="space-y-5 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Safety Rating Card */}
            <div
              className={`bg-gradient-to-br ${ratingCfg.gradient} border ${ratingCfg.border} rounded-2xl p-6`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-white/10 rounded-xl">
                    <ratingCfg.icon className={`h-7 w-7 ${ratingCfg.text}`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-xl font-bold text-white">Safety Rating:</h2>
                      <span
                        className={`text-xl font-bold ${ratingCfg.text}`}
                      >
                        {ratingCfg.label}
                      </span>
                    </div>
                    <p className="text-gray-300 text-sm mt-0.5">{ratingCfg.description}</p>
                    {result.medications_analyzed && (
                      <p className="text-gray-400 text-xs mt-1">
                        Analyzed: {result.medications_analyzed}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex gap-3 flex-wrap">
                  <div className="text-center bg-white/10 rounded-xl px-4 py-2">
                    <p className="text-2xl font-bold text-white">{result.total_interactions}</p>
                    <p className="text-xs text-gray-300">Interactions</p>
                  </div>
                  <div className="text-center bg-white/10 rounded-xl px-4 py-2">
                    <p className="text-2xl font-bold text-white">
                      {result.critical_alerts.length}
                    </p>
                    <p className="text-xs text-gray-300">Critical</p>
                  </div>
                </div>
              </div>

              {result.alert_sent && (
                <div className="mt-4 flex items-center gap-2 bg-red-900/40 border border-red-700/50 rounded-xl px-4 py-2.5 text-sm text-red-200">
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  Your prescribing physician has been automatically notified about these interactions.
                </div>
              )}
            </div>

            {/* Tabs */}
            <div className="flex bg-gray-900/80 border border-white/10 rounded-2xl p-1.5 gap-1.5">
              {(["analysis", "schedule"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 py-2.5 px-4 rounded-xl text-sm font-semibold capitalize transition-all ${
                    activeTab === tab
                      ? "bg-violet-600 text-white shadow-lg shadow-violet-900/40"
                      : "text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {tab === "analysis" ? "Interaction Analysis" : "Medication Schedule"}
                </button>
              ))}
            </div>

            {/* Tab content */}
            {activeTab === "analysis" && (
              <div className="space-y-4">
                {/* Plain language summary */}
                <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-6">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">
                    AI Summary
                  </h3>
                  <div className="text-gray-200 text-sm leading-relaxed whitespace-pre-line">
                    {result.response}
                  </div>
                </div>

                {/* Critical alerts */}
                {result.critical_alerts.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
                      Critical & Major Alerts ({result.critical_alerts.length})
                    </h3>
                    {result.critical_alerts.map((alert, i) => (
                      <AlertCard key={i} alert={alert} />
                    ))}
                  </div>
                )}

                {/* Moderate warnings */}
                {result.moderate_warnings.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
                      Moderate Warnings ({result.moderate_warnings.length})
                    </h3>
                    {result.moderate_warnings.map((alert, i) => (
                      <AlertCard key={i} alert={alert} />
                    ))}
                  </div>
                )}

                {/* Minor notes */}
                {result.minor_notes.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
                      Minor Notes ({result.minor_notes.length})
                    </h3>
                    {result.minor_notes.map((alert, i) => (
                      <AlertCard key={i} alert={alert} />
                    ))}
                  </div>
                )}

                {result.critical_alerts.length === 0 &&
                  result.moderate_warnings.length === 0 &&
                  result.minor_notes.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-10 bg-emerald-950/40 border border-emerald-800/40 rounded-2xl text-center">
                      <ShieldCheck className="h-12 w-12 text-emerald-400 mb-3" />
                      <h3 className="text-lg font-semibold text-white">No interactions detected</h3>
                      <p className="text-gray-400 text-sm mt-1 max-w-xs">
                        Your current medication combination appears safe. Always inform your
                        doctor of any new medications.
                      </p>
                    </div>
                  )}
              </div>
            )}

            {activeTab === "schedule" && (
              <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">
                  Your Medication Schedule
                </h3>
                {result.schedule ? (
                  <pre className="text-gray-200 text-sm whitespace-pre-wrap font-sans leading-relaxed">
                    {result.schedule}
                  </pre>
                ) : (
                  <p className="text-gray-400 text-sm">
                    Schedule was not generated — please run the check with specific medications.
                  </p>
                )}
              </div>
            )}

            {/* Run again */}
            <button
              onClick={runCheck}
              className="flex items-center gap-2 text-sm text-violet-400 hover:text-violet-300 transition-colors mx-auto"
            >
              <RefreshCw className="h-4 w-4" />
              Run another check
            </button>
          </div>
        )}

        {/* Disclaimer */}
        <div className="text-center">
          <p className="text-xs text-gray-600 max-w-lg mx-auto leading-relaxed">
            VitalMind AI provides medication safety information for educational purposes only.
            Always consult your physician, pharmacist, or licensed healthcare professional before
            making any changes to your medication regimen.
          </p>
        </div>
      </div>
    </div>
  );
}
