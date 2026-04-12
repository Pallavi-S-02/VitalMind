"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Calendar,
  Pill,
  Clock,
  AlertTriangle,
  ChevronLeft,
  RefreshCw,
  Loader2,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";
import { useSession } from "next-auth/react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface ScheduleData {
  patient_id: string;
  schedule: string;
  medications: string[];
}

// Parse medicine schedule text into structured time blocks for better display
function parseScheduleIntoBlocks(text: string): { time: string; items: string[] }[] {
  const blocks: { time: string; items: string[] }[] = [];
  const timeLabels = ["Morning", "Afternoon", "Evening", "Bedtime", "Timing", "Standard", "General"];

  if (typeof text !== "string") return [];
  const lines = text.split("\n");
  let currentBlock: { time: string; items: string[] } | null = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    const matchedLabel = timeLabels.find(
      (label) => trimmed.startsWith(label) || trimmed.includes(`🕐`) || trimmed.includes("Recommendations")
    );

    if (matchedLabel || trimmed.endsWith(":") || trimmed.startsWith("🕐")) {
      if (currentBlock) blocks.push(currentBlock);
      currentBlock = { time: trimmed.replace(":", "").replace("🕐", "").trim(), items: [] };
    } else if (currentBlock && trimmed.startsWith("•")) {
      currentBlock.items.push(trimmed.replace("•", "").trim());
    } else if (currentBlock) {
      currentBlock.items.push(trimmed);
    }
  }

  if (currentBlock) blocks.push(currentBlock);
  return blocks.filter((b) => b.items.length > 0);
}

const TIME_ICONS: Record<string, string> = {
  morning: "🌅",
  afternoon: "☀️",
  evening: "🌇",
  bedtime: "🌙",
  night: "🌙",
  timing: "⏰",
  standard: "💊",
  general: "💡",
};

function getTimeEmoji(timeLabel: string): string {
  const key = timeLabel.toLowerCase().split(" ")[0];
  return TIME_ICONS[key] || "💊";
}

export default function MedicationSchedulePage() {
  const { data: session } = useSession();
  const params = useParams();
  const patientId = params?.patientId as string;

  const [scheduleData, setScheduleData] = useState<ScheduleData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"visual" | "raw">("visual");

  const fetchSchedule = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const targetId = patientId || session?.user?.id;
      if (!targetId) {
        setError("Could not determine patient ID.");
        return;
      }

      const res = await fetch(`${API}/api/v1/medications/${targetId}/schedule`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || `Error ${res.status}`);
      }

      const data = await res.json();
      setScheduleData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load schedule.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (session?.accessToken) {
      fetchSchedule();
    }
  }, [session, patientId]);

  const scheduleBlocks = scheduleData
    ? parseScheduleIntoBlocks(scheduleData.schedule)
    : [];

  return (
    <div
      className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      {/* Header */}
      <div className="px-6 pt-8 pb-6 max-w-4xl mx-auto">
        <Link
          href="/patient/medications/interactions"
          className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200 transition-colors mb-6"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to Interaction Checker
        </Link>

        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2.5 bg-teal-600/20 border border-teal-500/30 rounded-xl">
                <Calendar className="h-6 w-6 text-teal-400" />
              </div>
              <h1 className="text-3xl font-bold text-white tracking-tight">
                Medication Schedule
              </h1>
            </div>
            <p className="text-gray-400 ml-[52px]">
              AI-optimized daily dosing plan based on your current medications.
            </p>
          </div>

          <button
            onClick={fetchSchedule}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2.5 bg-teal-600/20 border border-teal-500/30 rounded-xl text-teal-300 text-sm font-medium hover:bg-teal-600/30 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 pb-16 space-y-6">
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="relative mb-6">
              <div className="h-16 w-16 rounded-full border-4 border-teal-900/50 border-t-teal-500 animate-spin" />
              <Pill className="absolute inset-0 m-auto h-6 w-6 text-teal-400" />
            </div>
            <p className="text-gray-300 font-medium">Generating your personalized schedule...</p>
            <p className="text-gray-500 text-sm mt-1">
              Analyzing timing, interactions, and lifestyle factors
            </p>
          </div>
        )}

        {error && !isLoading && (
          <div className="flex flex-col items-center justify-center py-16 bg-red-950/20 border border-red-800/30 rounded-2xl">
            <AlertTriangle className="h-12 w-12 text-red-400 mb-4" />
            <h3 className="text-lg font-semibold text-white">Failed to Load Schedule</h3>
            <p className="text-gray-400 text-sm mt-1">{error}</p>
            <button
              onClick={fetchSchedule}
              className="mt-5 px-5 py-2.5 bg-red-900/40 border border-red-800/40 rounded-xl text-red-300 text-sm hover:bg-red-900/60 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {scheduleData && !isLoading && (
          <>
            {/* Medication list */}
            <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">
                Medications Included ({scheduleData.medications.length})
              </h2>
              <div className="flex flex-wrap gap-2">
                {scheduleData.medications.map((m, i) => (
                  <span
                    key={i}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-teal-900/30 border border-teal-800/40 rounded-xl text-teal-200 text-sm font-medium"
                  >
                    <Pill className="h-3.5 w-3.5" />
                    {m}
                  </span>
                ))}
              </div>
            </div>

            {/* View mode toggle */}
            <div className="flex bg-gray-900/80 border border-white/10 rounded-2xl p-1.5 gap-1.5">
              {(["visual", "raw"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={`flex-1 py-2.5 px-4 rounded-xl text-sm font-semibold transition-all ${
                    viewMode === mode
                      ? "bg-teal-600 text-white shadow-lg shadow-teal-900/40"
                      : "text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {mode === "visual" ? "📅 Visual Schedule" : "📄 Raw Text"}
                </button>
              ))}
            </div>

            {/* Visual Schedule */}
            {viewMode === "visual" && (
              <div className="space-y-4">
                {scheduleBlocks.length > 0 ? (
                  scheduleBlocks.map((block, i) => (
                    <div
                      key={i}
                      className="bg-gray-900/80 border border-white/10 rounded-2xl overflow-hidden"
                    >
                      <div className="flex items-center gap-3 px-6 py-4 bg-white/5 border-b border-white/10">
                        <span className="text-2xl">{getTimeEmoji(block.time)}</span>
                        <h3 className="text-lg font-bold text-white">{block.time}</h3>
                      </div>
                      <ul className="divide-y divide-white/5">
                        {block.items.map((item, j) => (
                          <li
                            key={j}
                            className="flex items-start gap-3 px-6 py-4 text-sm text-gray-300 hover:bg-white/5 transition-colors"
                          >
                            <div className="h-2 w-2 rounded-full bg-teal-500 mt-1.5 flex-shrink-0" />
                            <span className="leading-relaxed">{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))
                ) : (
                  <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-6">
                    <pre className="text-gray-200 text-sm whitespace-pre-wrap font-sans leading-relaxed">
                      {scheduleData.schedule}
                    </pre>
                  </div>
                )}
              </div>
            )}

            {/* Raw text view */}
            {viewMode === "raw" && (
              <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-6">
                <pre className="text-gray-200 text-sm whitespace-pre-wrap font-sans leading-relaxed">
                  {scheduleData.schedule}
                </pre>
              </div>
            )}

            {/* CTA */}
            <div className="bg-gradient-to-br from-violet-900/40 to-violet-800/20 border border-violet-700/30 rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h3 className="text-white font-semibold mb-1">Want to check for interactions?</h3>
                <p className="text-gray-400 text-sm">
                  Run a full AI safety analysis on all your medications.
                </p>
              </div>
              <Link
                href="/patient/medications/interactions"
                className="flex items-center gap-2 px-5 py-3 bg-violet-600 text-white rounded-xl font-medium text-sm hover:bg-violet-500 transition-colors flex-shrink-0 shadow-lg shadow-violet-900/40"
              >
                <ShieldCheck className="h-4 w-4" />
                Check Interactions
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </>
        )}

        {/* Disclaimer */}
        <p className="text-xs text-gray-600 text-center max-w-lg mx-auto leading-relaxed">
          This schedule is AI-generated for guidance only. Always follow your prescriber's
          instructions and consult your pharmacist before modifying your medication routine.
        </p>
      </div>
    </div>
  );
}
