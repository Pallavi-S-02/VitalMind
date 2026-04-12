"use client";

/**
 * Nurse Monitoring Page — simplified ward-level vitals view.
 *
 * Shows all active patients sorted by urgency (NEWS2 score).
 * Focuses on: patient name, current vitals, EWS badge, alert acknowledgment.
 * Nurses see a denser grid than doctors — optimized for quick scanning.
 */

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  Activity,
  Bell,
  CheckCheck,
  Loader2,
  Wifi,
  WifiOff,
  Search,
  AlertTriangle,
  CheckCircle,
} from "lucide-react";
import { useMonitoringStore, MonitoredPatient } from "@/store/monitoringStore";
import { EWSBadge } from "@/components/monitoring/EWSBadge";
import { AlertBanner } from "@/components/monitoring/AlertBanner";
import { cn } from "@/lib/utils";

// ─────────────────────────────────────────────────────────────────────────────
// Compact patient row for nurse view
// ─────────────────────────────────────────────────────────────────────────────

function PatientRow({
  patient,
  onAcknowledge,
  userId,
}: {
  patient: MonitoredPatient & { alert_count: number };
  onAcknowledge: (alertId: string) => void;
  userId: string;
}) {
  const v = patient.vitals;
  const news2Score = patient.news2?.news2_score ?? 0;
  const riskLevel = patient.news2?.risk_level ?? "Low";
  const hasAlert = patient.alert_count > 0;
  const isCritical = news2Score >= 7;
  const latestAlert = patient.last_alert;

  return (
    <div
      className={cn(
        "flex items-center gap-4 px-5 py-4 border-b border-white/5 hover:bg-white/5 transition-all",
        isCritical && "bg-red-950/10 hover:bg-red-950/20",
        hasAlert && !isCritical && "bg-yellow-950/5"
      )}
    >
      {/* News2 risk stripe */}
      <div
        className={`w-1 h-10 rounded-full flex-shrink-0 ${
          news2Score >= 7
            ? "bg-red-500"
            : news2Score >= 5
            ? "bg-orange-500"
            : news2Score >= 1
            ? "bg-yellow-500"
            : "bg-emerald-500/40"
        }`}
      />

      {/* Patient info */}
      <div className="w-44 flex-shrink-0">
        <p className="text-sm font-semibold text-white">{patient.name}</p>
        <p className="text-xs text-gray-500">
          {patient.room ? `Room ${patient.room}` : ""}
          {patient.room && patient.age ? " · " : ""}
          {patient.age ? `${patient.age}y` : ""}
        </p>
      </div>

      {/* EWS Badge */}
      <div className="w-32 flex-shrink-0">
        <EWSBadge score={news2Score} riskLevel={riskLevel} size="sm" />
      </div>

      {/* Vitals inline */}
      <div className="flex-1 grid grid-cols-5 gap-2 text-xs">
        {[
          { label: "HR", value: v?.heart_rate, unit: "", lo: 60, hi: 100 },
          { label: "SpO₂", value: v?.spo2, unit: "%", lo: 95, hi: 100 },
          {
            label: "BP",
            value: v?.systolic_bp,
            unit: "",
            extra: v?.diastolic_bp ? `/${v.diastolic_bp.toFixed(0)}` : "",
            lo: 90,
            hi: 130,
          },
          { label: "Temp", value: v?.temperature_c, unit: "°C", lo: 36.1, hi: 37.2 },
          { label: "RR", value: v?.respiratory_rate, unit: "", lo: 12, hi: 20 },
        ].map(({ label, value, unit, lo, hi, extra }: any) => {
          const hasVal = value !== undefined && value !== null;
          const isAbnormal = hasVal && (value < lo || value > hi);
          return (
            <div key={label} className="flex flex-col">
              <span className="text-gray-600 font-medium uppercase tracking-wide text-[9px]">
                {label}
              </span>
              <span
                className={`font-bold tabular-nums ${
                  isAbnormal ? "text-red-400" : hasVal ? "text-gray-200" : "text-gray-600"
                }`}
              >
                {hasVal ? `${value.toFixed(label === "Temp" ? 1 : 0)}${extra || ""}${unit}` : "—"}
              </span>
            </div>
          );
        })}
      </div>

      {/* Alert status + action */}
      <div className="w-40 flex-shrink-0 flex items-center justify-end gap-3">
        {hasAlert && latestAlert ? (
          <button
            onClick={() => onAcknowledge(latestAlert.id)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-600/20 border border-yellow-700/40 hover:bg-yellow-600/30 text-yellow-300 rounded-xl text-xs font-semibold transition-colors"
          >
            <AlertTriangle className="h-3 w-3" />
            Ack ({patient.alert_count})
          </button>
        ) : (
          <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium">
            <CheckCircle className="h-3.5 w-3.5" />
            Stable
          </span>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main nurse monitoring page
// ─────────────────────────────────────────────────────────────────────────────

export default function NurseMonitoringPage() {
  const { data: session } = useSession();
  const [searchQuery, setSearchQuery] = useState("");

  const {
    connect,
    disconnect,
    isConnected,
    patients,
    vitalsMap,
    news2Map,
    activeAlerts,
    acknowledgeAlert,
    isLoadingPatients,
    loadPatients,
    loadAlerts,
  } = useMonitoringStore();

  useEffect(() => {
    if (session?.accessToken) {
      connect(session.accessToken);
      loadPatients(session.accessToken);
      loadAlerts(session.accessToken);
    }
    return () => disconnect();
  }, [session?.accessToken]);

  // Refresh alerts every 30s
  useEffect(() => {
    if (!session?.accessToken) return;
    const interval = setInterval(() => loadAlerts(session.accessToken!), 30000);
    return () => clearInterval(interval);
  }, [session?.accessToken]);

  const enriched = patients.map((p) => ({
    ...p,
    vitals: vitalsMap[p.id] ?? p.vitals,
    news2: news2Map[p.id] ?? p.news2,
    last_alert: activeAlerts.find((a) => a.patient_id === p.id && !a.acknowledged),
    alert_count: activeAlerts.filter((a) => a.patient_id === p.id && !a.acknowledged).length,
  }));

  const filtered = enriched
    .filter((p) => {
      const q = searchQuery.toLowerCase();
      return !q || p.name.toLowerCase().includes(q) || (p.room ?? "").toLowerCase().includes(q);
    })
    .sort((a, b) => (b.news2?.news2_score ?? 0) - (a.news2?.news2_score ?? 0));

  const unackedAlerts = activeAlerts.filter((a) => !a.acknowledged);
  const criticalCount = enriched.filter((p) => (p.news2?.news2_score ?? 0) >= 7).length;

  return (
    <div
      className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      <AlertBanner
        alerts={unackedAlerts}
        onAcknowledge={(id) => session?.user?.id && acknowledgeAlert(id, session.user.id)}
        maxVisible={2}
      />

      {/* Header */}
      <div className="px-6 pt-8 pb-5 max-w-screen-xl mx-auto">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="p-2.5 bg-teal-600/20 border border-teal-500/30 rounded-xl">
                <Activity className="h-6 w-6 text-teal-400" />
              </div>
              <h1 className="text-3xl font-bold text-white tracking-tight">Ward Monitor</h1>
            </div>
            <div className="flex items-center gap-3 ml-[52px]">
              <div
                className={`flex items-center gap-1.5 text-xs font-medium ${
                  isConnected ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {isConnected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
                {isConnected ? "Live monitoring active" : "Reconnecting..."}
              </div>
            </div>
          </div>

          {/* Quick stats */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-4 py-2 bg-yellow-950/40 border border-yellow-800/30 rounded-xl">
              <Bell className="h-4 w-4 text-yellow-400" />
              <span className="text-sm font-bold text-white">{unackedAlerts.length}</span>
              <span className="text-xs text-gray-400">alerts</span>
            </div>
            {criticalCount > 0 && (
              <div className="flex items-center gap-2 px-4 py-2 bg-red-950/40 border border-red-800/30 rounded-xl animate-pulse">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                <span className="text-sm font-bold text-white">{criticalCount}</span>
                <span className="text-xs text-gray-400">critical</span>
              </div>
            )}
            {unackedAlerts.length > 0 && (
              <button
                onClick={() =>
                  unackedAlerts.forEach(
                    (a) => session?.user?.id && acknowledgeAlert(a.id, session.user.id)
                  )
                }
                className="flex items-center gap-2 px-4 py-2.5 bg-white/5 border border-white/10 hover:bg-white/10 text-gray-300 rounded-xl text-sm font-medium transition-colors"
              >
                <CheckCheck className="h-4 w-4" />
                Ack All
              </button>
            )}
          </div>
        </div>

        {/* Search */}
        <div className="relative max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search patients, rooms..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-gray-800/60 border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          />
        </div>
      </div>

      {/* Table */}
      <div className="max-w-screen-xl mx-auto px-6 pb-16">
        <div className="bg-gray-900/80 border border-white/10 rounded-2xl overflow-hidden">
          {/* Column headers */}
          <div className="flex items-center gap-4 px-5 py-3 border-b border-white/10 bg-gray-800/30">
            <div className="w-1 flex-shrink-0" />
            <div className="w-44 flex-shrink-0 text-[10px] text-gray-500 uppercase tracking-widest font-semibold">
              Patient
            </div>
            <div className="w-32 flex-shrink-0 text-[10px] text-gray-500 uppercase tracking-widest font-semibold">
              EWS
            </div>
            <div className="flex-1 grid grid-cols-5 gap-2 text-[10px] text-gray-500 uppercase tracking-widest font-semibold">
              <span>HR</span>
              <span>SpO₂</span>
              <span>BP</span>
              <span>Temp</span>
              <span>RR</span>
            </div>
            <div className="w-40 flex-shrink-0 text-[10px] text-gray-500 uppercase tracking-widest font-semibold text-right">
              Status
            </div>
          </div>

          {isLoadingPatients ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 text-teal-400 animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <Activity className="h-10 w-10 text-gray-600 mb-3" />
              <p className="text-gray-400 text-sm">
                {searchQuery ? "No patients match your search" : "No monitored patients"}
              </p>
            </div>
          ) : (
            filtered.map((patient) => (
              <PatientRow
                key={patient.id}
                patient={patient as MonitoredPatient & { alert_count: number }}
                onAcknowledge={(alertId) =>
                  session?.user?.id && acknowledgeAlert(alertId, session.user.id)
                }
                userId={session?.user?.id || ""}
              />
            ))
          )}
        </div>

        <p className="text-xs text-gray-600 text-center mt-4">
          Sorted by NEWS2 risk · Updates in real time · Showing {filtered.length} of {patients.length} patients
        </p>
      </div>
    </div>
  );
}
