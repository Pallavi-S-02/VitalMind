"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Activity,
  Bell,
  CheckCheck,
  Loader2,
  Heart,
  Wifi,
  WifiOff,
  Play,
  RefreshCw,
  User,
  ClipboardList,
} from "lucide-react";
import { useMonitoringStore } from "@/store/monitoringStore";
import { VitalsChart, VitalsDataPoint } from "@/components/monitoring/VitalsChart";
import { EWSBadge } from "@/components/monitoring/EWSBadge";
import { AlertBanner } from "@/components/monitoring/AlertBanner";

// ─────────────────────────────────────────────────────────────────────────────
// Alert history row
// ─────────────────────────────────────────────────────────────────────────────

const LEVEL_LABELS: Record<number, string> = {
  1: "Nurse Alert",
  2: "Physician SMS",
  3: "Emergency Page",
};
const LEVEL_COLORS: Record<number, string> = {
  1: "text-yellow-400 bg-yellow-950/30 border-yellow-800/30",
  2: "text-orange-400 bg-orange-950/30 border-orange-800/30",
  3: "text-red-400 bg-red-950/30 border-red-800/30",
};

// ─────────────────────────────────────────────────────────────────────────────
// Patient deep-dive page
// ─────────────────────────────────────────────────────────────────────────────

export default function PatientMonitoringDetailPage() {
  const { data: session } = useSession();
  const params = useParams();
  const patientId = params?.patientId as string;

  const [isRunningCycle, setIsRunningCycle] = useState(false);
  const [cycleResult, setCycleResult] = useState<Record<string, unknown> | null>(null);
  const [history, setHistory] = useState<VitalsDataPoint[]>([]);
  const [shiftSummary, setShiftSummary] = useState<string | null>(null);
  const [isLoadingSummary, setIsLoadingSummary] = useState(false);
  const [activeTab, setActiveTab] = useState<"vitals" | "alerts" | "summary">("vitals");
  const [news2Detail, setNews2Detail] = useState<Record<string, unknown> | null>(null);
  const [isLoadingNews2, setIsLoadingNews2] = useState(false);

  const {
    connect,
    disconnect,
    isConnected,
    joinPatientRoom,
    leavePatientRoom,
    vitalsMap,
    news2Map,
    activeAlerts,
    acknowledgeAlert,
    patients,
    loadPatients,
    loadAlerts,
  } = useMonitoringStore();

  const patient = patients.find((p) => p.id === patientId);
  const vitals = vitalsMap[patientId] ?? patient?.vitals;
  const news2 = news2Map[patientId] ?? patient?.news2;
  const patientAlerts = activeAlerts.filter((a) => a.patient_id === patientId);
  const unackedAlerts = patientAlerts.filter((a) => !a.acknowledged);

  // Connect monitoring socket + join patient-specific room
  useEffect(() => {
    if (session?.accessToken) {
      connect(session.accessToken);
      loadPatients(session.accessToken);
      loadAlerts(session.accessToken, patientId);
      setTimeout(() => joinPatientRoom(patientId), 500);
      fetchVitalsHistory();
      fetchNews2();
    }
    return () => {
      leavePatientRoom(patientId);
      disconnect();
    };
  }, [session?.accessToken, patientId]);

  const fetchVitalsHistory = async () => {
    if (!session?.accessToken) return;
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
      const res = await fetch(
        `${apiUrl}/api/v1/vitals/${patientId}/history?hours=4&limit=80`,
        { headers: { Authorization: `Bearer ${session.accessToken}` } }
      );
      if (res.ok) {
        const data = await res.json();
        const points: VitalsDataPoint[] = (data.readings || []).map(
          (r: Record<string, unknown>) => ({
            timestamp: String(r.timestamp || ""),
            heart_rate: Number(r.heart_rate) || undefined,
            spo2: Number(r.spo2) || undefined,
            systolic_bp: Number(r.systolic_bp) || undefined,
            diastolic_bp: Number(r.diastolic_bp) || undefined,
            temperature_c: Number(r.temperature_c || r.temperature) || undefined,
            respiratory_rate: Number(r.respiratory_rate) || undefined,
            blood_glucose_mgdl: Number(r.blood_glucose_mgdl) || undefined,
          })
        );
        setHistory(points.reverse());
      }
    } catch (e) {
      console.error("Failed to fetch vitals history:", e);
    }
  };

  const fetchNews2 = async () => {
    if (!session?.accessToken) return;
    setIsLoadingNews2(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
      const res = await fetch(`${apiUrl}/api/v1/monitoring/${patientId}/news2`, {
        headers: { Authorization: `Bearer ${session.accessToken}` },
      });
      if (res.ok) setNews2Detail(await res.json());
    } catch (e) {
      console.error("Failed to fetch NEWS2:", e);
    } finally {
      setIsLoadingNews2(false);
    }
  };

  const runMonitoringCycle = async () => {
    if (!session?.accessToken || isRunningCycle) return;
    setIsRunningCycle(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
      const res = await fetch(`${apiUrl}/api/v1/monitoring/${patientId}/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.accessToken}`,
        },
      });
      const data = await res.json();
      setCycleResult(data);
      loadAlerts(session.accessToken, patientId);
    } catch (e) {
      console.error("Monitoring cycle failed:", e);
    } finally {
      setIsRunningCycle(false);
    }
  };

  const loadShiftSummary = async () => {
    if (!session?.accessToken) return;
    setIsLoadingSummary(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
      const res = await fetch(
        `${apiUrl}/api/v1/monitoring/${patientId}/shift-summary?shift_hours=8`,
        { headers: { Authorization: `Bearer ${session.accessToken}` } }
      );
      if (res.ok) {
        const data = await res.json();
        const summary = data.summary;
        if (typeof summary === "string") setShiftSummary(summary);
        else if (summary?.sbar_summary) setShiftSummary(summary.sbar_summary);
        else setShiftSummary(JSON.stringify(summary, null, 2));
      }
    } catch (e) {
      console.error("Failed to load shift summary:", e);
    } finally {
      setIsLoadingSummary(false);
    }
  };

  const news2Score = (news2Detail?.news2 as Record<string, unknown>)?.news2_total as number
    ?? news2?.news2_score
    ?? 0;
  const riskLevel = (news2Detail?.news2 as Record<string, unknown>)?.risk_level as string
    ?? news2?.risk_level
    ?? "Low";

  return (
    <div
      className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      {/* Alert overlays */}
      <AlertBanner
        alerts={unackedAlerts}
        onAcknowledge={(id) => session?.user?.id && acknowledgeAlert(id, session.user.id)}
        maxVisible={2}
      />

      {/* Header */}
      <div className="px-6 pt-8 pb-5 max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-5">
          <Link
            href="/doctor/monitoring"
            className="p-2 bg-white/5 border border-white/10 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-cyan-600/20 border border-cyan-500/30 rounded-xl">
              <Heart className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                {patient?.name ?? `Patient ${patientId.slice(0, 8)}`}
              </h1>
              <div className="flex items-center gap-3 mt-0.5">
                {patient?.room && (
                  <span className="text-xs text-gray-400">Room {patient.room}</span>
                )}
                {patient?.age && (
                  <span className="text-xs text-gray-400">· {patient.age}y</span>
                )}
                <div
                  className={`flex items-center gap-1 text-xs ${
                    isConnected ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  {isConnected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                  {isConnected ? "Live" : "Reconnecting"}
                </div>
              </div>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <EWSBadge score={news2Score} riskLevel={riskLevel} size="md" />
            <button
              onClick={runMonitoringCycle}
              disabled={isRunningCycle}
              className="flex items-center gap-2 px-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-white rounded-xl text-sm font-semibold transition-colors shadow-lg shadow-cyan-900/30"
            >
              {isRunningCycle ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Run Monitoring Cycle
            </button>
          </div>
        </div>

        {/* Monitoring Cycle Result */}
        {cycleResult && (
          <div className="mb-5 bg-gray-900/80 border border-white/10 rounded-2xl p-4 animate-in fade-in slide-in-from-top-2 duration-300">
            <p className="text-sm font-semibold text-gray-300 mb-2">
              Monitoring Cycle Result
            </p>
            <div className="flex flex-wrap gap-3 text-xs text-gray-400">
              {Boolean((cycleResult.monitoring_result as Record<string, unknown>)?.news2_score !== undefined) && (
                <span>
                  NEWS2:{" "}
                  <span className="text-white font-bold">
                    {String((cycleResult.monitoring_result as Record<string, unknown>).news2_score ?? "")}
                  </span>
                </span>
              )}
              {Boolean((cycleResult.monitoring_result as Record<string, unknown>)?.overall_severity !== undefined) && (
                <span>
                  Severity:{" "}
                  <span className="text-white font-bold">
                    {String((cycleResult.monitoring_result as Record<string, unknown>).overall_severity ?? "")}
                  </span>
                </span>
              )}
              {Boolean((cycleResult.monitoring_result as Record<string, unknown>)?.alert_dispatched !== undefined) && (
                <span
                  className={
                    Boolean((cycleResult.monitoring_result as Record<string, unknown>).alert_dispatched)
                      ? "text-red-300"
                      : "text-emerald-400"
                  }
                >
                  {Boolean((cycleResult.monitoring_result as Record<string, unknown>).alert_dispatched)
                    ? "⚠ Alert dispatched"
                    : "✓ No alerts required"}
                </span>
              )}
            </div>
            {Boolean((cycleResult.monitoring_result as Record<string, unknown>)?.urgency_narrative) && (
              <p className="text-xs text-gray-300 mt-2 bg-white/5 rounded-xl p-3 leading-relaxed">
                {String((cycleResult.monitoring_result as Record<string, unknown>).urgency_narrative ?? "")}
              </p>
            )}

          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-800/40 border border-white/10 rounded-xl p-1 mb-6">
          {(
            [
              { key: "vitals", label: "Vitals & Chart", icon: Activity },
              { key: "alerts", label: `Alerts (${patientAlerts.length})`, icon: Bell },
              { key: "summary", label: "Shift Summary", icon: ClipboardList },
            ] as const
          ).map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => {
                setActiveTab(key);
                if (key === "summary" && !shiftSummary) loadShiftSummary();
              }}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === key
                  ? "bg-cyan-600 text-white shadow-lg"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="max-w-5xl mx-auto px-6 pb-16">
        {/* Vitals + Chart Tab */}
        {activeTab === "vitals" && (
          <div className="space-y-5">
            {/* NEWS2 breakdown */}
            {news2Detail && (
              <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
                    NEWS2 Score Breakdown
                  </h3>
                  <button
                    onClick={fetchNews2}
                    className="p-1.5 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${isLoadingNews2 ? "animate-spin" : ""}`} />
                  </button>
                </div>
                <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                  {Object.entries(
                    ((news2Detail.news2 as Record<string, unknown>)?.component_scores as Record<string, number>) ?? {}
                  ).map(([param, score]) => (
                    <div
                      key={param}
                      className={`flex flex-col items-center p-2.5 rounded-xl border ${
                        score > 0
                          ? "bg-orange-950/30 border-orange-800/30 text-orange-300"
                          : "bg-white/5 border-white/5 text-gray-400"
                      }`}
                    >
                      <span className="text-xl font-bold tabular-nums text-white">{score}</span>
                      <span className="text-[9px] uppercase tracking-wide text-center leading-tight mt-1 opacity-80">
                        {param.replace(/_/g, " ")}
                      </span>
                    </div>
                  ))}
                  <div className="flex flex-col items-center p-2.5 rounded-xl border bg-cyan-950/40 border-cyan-800/40 text-cyan-300">
                    <span className="text-xl font-bold tabular-nums text-white">
                      {news2Score}
                    </span>
                    <span className="text-[9px] uppercase tracking-wide mt-1 opacity-80">
                      Total
                    </span>
                  </div>
                </div>
                {(news2Detail.news2 as Record<string, unknown>)?.recommended_action !== undefined && (
                  <p className="text-sm text-gray-300 mt-4 bg-white/5 rounded-xl p-3">
                    <span className="font-semibold text-white">Recommended action: </span>
                    {String((news2Detail.news2 as Record<string, unknown>).recommended_action ?? "")}
                  </p>
                )}
              </div>
            )}

            {/* Vitals history chart */}
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
                4-Hour Vitals Trend
              </h3>
              <button
                onClick={fetchVitalsHistory}
                className="p-1.5 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>
            <VitalsChart data={history} />
          </div>
        )}

        {/* Alerts Tab */}
        {activeTab === "alerts" && (
          <div className="space-y-3">
            {patientAlerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 bg-gray-900/40 border border-dashed border-white/10 rounded-2xl">
                <Bell className="h-10 w-10 text-gray-600 mb-3" />
                <h3 className="text-white font-semibold">No alerts for this patient</h3>
                <p className="text-gray-400 text-sm mt-1">
                  Alerts will appear here when monitoring detects anomalies.
                </p>
              </div>
            ) : (
              patientAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`rounded-2xl border p-4 transition-all ${
                    LEVEL_COLORS[alert.level] || LEVEL_COLORS[1]
                  } ${alert.acknowledged ? "opacity-50" : ""}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold uppercase tracking-wider">
                          {LEVEL_LABELS[alert.level]}
                        </span>
                        <span className="text-xs opacity-60">·</span>
                        <EWSBadge score={alert.news2_score} size="sm" showLabel={false} />
                        <span className="text-xs opacity-60">·</span>
                        <span className="text-xs opacity-70">
                          {new Date(alert.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed">{alert.message}</p>
                      {alert.vitals_summary && (
                        <p className="text-xs font-mono opacity-60 mt-1">{alert.vitals_summary}</p>
                      )}
                    </div>
                    {!alert.acknowledged && (
                      <button
                        onClick={() =>
                          session?.user?.id && acknowledgeAlert(alert.id, session.user.id)
                        }
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-xl text-xs font-semibold text-white transition-colors flex-shrink-0"
                      >
                        <CheckCheck className="h-3.5 w-3.5" />
                        Acknowledge
                      </button>
                    )}
                    {alert.acknowledged && (
                      <span className="text-xs text-emerald-400 flex items-center gap-1 flex-shrink-0">
                        <CheckCheck className="h-3.5 w-3.5" />
                        Acked by {alert.acknowledged_by?.slice(0, 8) || "staff"}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Shift Summary Tab */}
        {activeTab === "summary" && (
          <div className="space-y-4">
            {isLoadingSummary ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="h-8 w-8 text-cyan-400 animate-spin" />
              </div>
            ) : shiftSummary ? (
              <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">
                  8-Hour SBAR Shift Summary
                </h3>
                <div className="text-sm text-gray-200 leading-relaxed whitespace-pre-line">
                  {shiftSummary}
                </div>
                <button
                  onClick={loadShiftSummary}
                  className="mt-5 flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Regenerate summary
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 bg-gray-900/40 border border-dashed border-white/10 rounded-2xl">
                <ClipboardList className="h-10 w-10 text-gray-600 mb-3" />
                <h3 className="text-white font-semibold">No summary generated yet</h3>
                <button
                  onClick={loadShiftSummary}
                  className="mt-4 px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-sm font-semibold transition-colors"
                >
                  Generate Summary
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
