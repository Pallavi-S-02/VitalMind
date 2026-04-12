"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  Activity,
  Bell,
  BellOff,
  RefreshCw,
  Wifi,
  WifiOff,
  AlertTriangle,
  Search,
  Users,
  CheckCheck,
  Loader2,
} from "lucide-react";
import { useMonitoringStore } from "@/store/monitoringStore";
import { VitalsCard } from "@/components/monitoring/VitalsCard";
import { AlertBanner } from "@/components/monitoring/AlertBanner";
import { EWSBadge } from "@/components/monitoring/EWSBadge";

// ─────────────────────────────────────────────────────────────────────────────
// Stats bar
// ─────────────────────────────────────────────────────────────────────────────

function StatsBar({
  totalPatients,
  activeAlerts,
  criticalCount,
  highRiskCount,
}: {
  totalPatients: number;
  activeAlerts: number;
  criticalCount: number;
  highRiskCount: number;
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {[
        {
          label: "Monitored",
          value: totalPatients,
          icon: Users,
          color: "text-sky-400",
          bg: "bg-sky-950/40 border-sky-800/30",
        },
        {
          label: "Active Alerts",
          value: activeAlerts,
          icon: Bell,
          color: "text-yellow-400",
          bg: "bg-yellow-950/40 border-yellow-800/30",
        },
        {
          label: "Critical (NEWS2≥7)",
          value: criticalCount,
          icon: AlertTriangle,
          color: "text-red-400",
          bg: "bg-red-950/40 border-red-800/30",
        },
        {
          label: "High Risk",
          value: highRiskCount,
          icon: Activity,
          color: "text-orange-400",
          bg: "bg-orange-950/40 border-orange-800/30",
        },
      ].map(({ label, value, icon: Icon, color, bg }) => (
        <div
          key={label}
          className={`flex items-center gap-3 rounded-2xl border px-4 py-3 ${bg}`}
        >
          <Icon className={`h-5 w-5 flex-shrink-0 ${color}`} />
          <div>
            <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
            <p className="text-xs text-gray-400 font-medium">{label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page — Doctor Monitoring Wall
// ─────────────────────────────────────────────────────────────────────────────

export default function DoctorMonitoringPage() {
  const { data: session } = useSession();
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<"name" | "news2" | "alerts">("news2");
  const [filterAlerts, setFilterAlerts] = useState(false);

  const {
    connect,
    disconnect,
    isConnected,
    connectionError,
    patients,
    vitalsMap,
    news2Map,
    activeAlerts,
    isLoadingPatients,
    acknowledgeAlert,
    loadAlerts,
    loadPatients,
  } = useMonitoringStore();

  // --- Connect to monitoring WebSocket ---
  useEffect(() => {
    if (session?.accessToken) {
      connect(session.accessToken);
      loadPatients(session.accessToken);
      loadAlerts(session.accessToken);
    }
    return () => disconnect();
  }, [session?.accessToken]);

  // --- Refresh alerts every 60s ---
  useEffect(() => {
    if (!session?.accessToken) return;
    const interval = setInterval(() => loadAlerts(session.accessToken!), 60000);
    return () => clearInterval(interval);
  }, [session?.accessToken]);

  // --- Enrich patients with live data from the store maps ---
  const enrichedPatients = patients.map((p) => ({
    ...p,
    vitals: vitalsMap[p.id] ?? p.vitals,
    news2: news2Map[p.id] ?? p.news2,
    last_alert: activeAlerts.find((a) => a.patient_id === p.id && !a.acknowledged),
    alert_count: activeAlerts.filter((a) => a.patient_id === p.id && !a.acknowledged).length,
  }));

  // --- Filter + sort ---
  const filtered = enrichedPatients
    .filter((p) => {
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        !q || p.name.toLowerCase().includes(q) || (p.room || "").toLowerCase().includes(q);
      const matchesAlertFilter = !filterAlerts || (p.alert_count ?? 0) > 0;
      return matchesSearch && matchesAlertFilter;
    })
    .sort((a, b) => {
      if (sortBy === "news2") {
        return (b.news2?.news2_score ?? 0) - (a.news2?.news2_score ?? 0);
      }
      if (sortBy === "alerts") {
        return (b.alert_count ?? 0) - (a.alert_count ?? 0);
      }
      return a.name.localeCompare(b.name);
    });

  // --- Stats ---
  const unacknowledgedAlerts = activeAlerts.filter((a) => !a.acknowledged);
  const criticalCount = enrichedPatients.filter((p) => (p.news2?.news2_score ?? 0) >= 7).length;
  const highRiskCount = enrichedPatients.filter(
    (p) => (p.news2?.news2_score ?? 0) >= 5 && (p.news2?.news2_score ?? 0) < 7
  ).length;

  const handleAcknowledge = (alertId: string) => {
    if (!session?.user?.id) return;
    acknowledgeAlert(alertId, session.user.id);
  };

  return (
    <div
      className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      {/* Alert Banners */}
      <AlertBanner
        alerts={unacknowledgedAlerts}
        onAcknowledge={handleAcknowledge}
        maxVisible={3}
      />

      {/* Header */}
      <div className="px-6 pt-8 pb-5 max-w-screen-2xl mx-auto">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="p-2.5 bg-cyan-600/20 border border-cyan-500/30 rounded-xl">
                <Activity className="h-6 w-6 text-cyan-400" />
              </div>
              <h1 className="text-3xl font-bold text-white tracking-tight">
                Monitoring Wall
              </h1>
            </div>
            <div className="flex items-center gap-3 ml-[52px]">
              <div
                className={`flex items-center gap-1.5 text-xs font-medium ${
                  isConnected ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {isConnected ? (
                  <Wifi className="h-3.5 w-3.5" />
                ) : (
                  <WifiOff className="h-3.5 w-3.5" />
                )}
                {isConnected ? "Live · Real-time updates" : "Reconnecting..."}
              </div>
              {connectionError && (
                <span className="text-xs text-red-400">{connectionError}</span>
              )}
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3">
            {unacknowledgedAlerts.length > 0 && (
              <button
                onClick={() =>
                  unacknowledgedAlerts.forEach((a) =>
                    handleAcknowledge(a.id)
                  )
                }
                className="flex items-center gap-2 px-4 py-2.5 bg-yellow-600/20 border border-yellow-700/40 hover:bg-yellow-600/30 text-yellow-300 rounded-xl text-sm font-medium transition-colors"
              >
                <CheckCheck className="h-4 w-4" />
                Ack All ({unacknowledgedAlerts.length})
              </button>
            )}
            <button
              onClick={() =>
                session?.accessToken &&
                loadPatients(session.accessToken)
              }
              className="p-2.5 bg-white/5 border border-white/10 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              title="Refresh patient list"
            >
              <RefreshCw className={`h-4 w-4 ${isLoadingPatients ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Stats Bar */}
        <StatsBar
          totalPatients={patients.length}
          activeAlerts={unacknowledgedAlerts.length}
          criticalCount={criticalCount}
          highRiskCount={highRiskCount}
        />

        {/* Filters Row */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-48 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search patients, rooms..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-800/60 border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
            />
          </div>

          <div className="flex items-center gap-1 bg-gray-800/40 border border-white/10 rounded-xl p-1">
            {(["news2", "alerts", "name"] as const).map((opt) => (
              <button
                key={opt}
                onClick={() => setSortBy(opt)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all capitalize ${
                  sortBy === opt
                    ? "bg-cyan-600 text-white"
                    : "text-gray-400 hover:text-gray-200"
                }`}
              >
                {opt === "news2" ? "By Risk" : opt === "alerts" ? "By Alerts" : "By Name"}
              </button>
            ))}
          </div>

          <button
            onClick={() => setFilterAlerts((v) => !v)}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-medium transition-all ${
              filterAlerts
                ? "bg-yellow-600/20 border-yellow-700/50 text-yellow-300"
                : "bg-white/5 border-white/10 text-gray-400"
            }`}
          >
            {filterAlerts ? (
              <Bell className="h-3.5 w-3.5" />
            ) : (
              <BellOff className="h-3.5 w-3.5" />
            )}
            Alerts only
          </button>
        </div>
      </div>

      {/* Patient Grid */}
      <div className="max-w-screen-2xl mx-auto px-6 pb-16">
        {isLoadingPatients ? (
          <div className="flex flex-col items-center justify-center py-24">
            <Loader2 className="h-10 w-10 text-cyan-400 animate-spin mb-4" />
            <p className="text-gray-400">Loading monitored patients...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 bg-gray-900/40 border border-dashed border-white/10 rounded-2xl">
            <Activity className="h-12 w-12 text-gray-600 mb-4" />
            <h3 className="text-white font-semibold">
              {searchQuery || filterAlerts ? "No matching patients" : "No monitored patients"}
            </h3>
            <p className="text-gray-400 text-sm mt-1">
              {searchQuery || filterAlerts
                ? "Try adjusting your filters"
                : "Patients with active IoT devices will appear here"}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.map((patient) => (
              <div key={patient.id} className="relative">
                {/* Risk level indicator stripe */}
                <div
                  className={`absolute left-0 top-3 bottom-3 w-0.5 rounded-r-full ${
                    (patient.news2?.news2_score ?? 0) >= 7
                      ? "bg-red-500"
                      : (patient.news2?.news2_score ?? 0) >= 5
                      ? "bg-orange-500"
                      : (patient.news2?.news2_score ?? 0) >= 1
                      ? "bg-yellow-500"
                      : "bg-emerald-500/30"
                  }`}
                />
                <div className="pl-3">
                  <VitalsCard
                    patient={patient}
                    vitals={patient.vitals}
                    news2={patient.news2}
                    hasUnacknowledgedAlert={(patient.alert_count ?? 0) > 0}
                    alertLevel={patient.last_alert?.level as 1 | 2 | 3 | undefined}
                    href={`/doctor/monitoring/${patient.id}`}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
