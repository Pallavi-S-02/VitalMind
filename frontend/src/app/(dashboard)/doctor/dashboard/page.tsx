"use client";

import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  Users, Calendar, CheckCircle2, AlertTriangle, Clock,
  ArrowRight, Video, MapPin, PhoneCall, BarChart3,
} from "lucide-react";
import { format, parseISO } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface DoctorAnalytics {
  doctor_id: string;
  today_appointments: Array<{
    id: string; start_time: string; end_time: string; status: string;
    type: string; reason: string | null; patient_name: string;
  }>;
  stats: {
    active_patients: number; pending_alerts: number;
    completion_rate_pct: number; total_appointments_30d: number;
  };
  risk_distribution: { low: number; medium: number; high: number; critical: number };
}

const STATUS_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  scheduled:  { bg: "rgba(59,130,246,0.1)",  text: "#60a5fa", border: "rgba(59,130,246,0.2)" },
  confirmed:  { bg: "rgba(52,211,153,0.1)",  text: "#34d399", border: "rgba(52,211,153,0.2)" },
  completed:  { bg: "rgba(100,116,139,0.1)", text: "#94a3b8", border: "rgba(100,116,139,0.2)" },
  cancelled:  { bg: "rgba(244,63,94,0.1)",   text: "#f87171", border: "rgba(244,63,94,0.2)" },
  "no-show":  { bg: "rgba(245,158,11,0.1)",  text: "#fbbf24", border: "rgba(245,158,11,0.15)" },
};

const TYPE_ICON: Record<string, React.ReactNode> = {
  video:       <Video className="w-3.5 h-3.5 text-cyan-400" />,
  voice:       <PhoneCall className="w-3.5 h-3.5 text-purple-400" />,
  "in-person": <MapPin className="w-3.5 h-3.5 text-indigo-400" />,
};

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`rounded-xl animate-pulse ${className}`}
      style={{ background: "rgba(255,255,255,0.06)" }} />
  );
}

function StatCard({
  icon, label, value, gradient, glowColor,
}: {
  icon: React.ReactNode; label: string; value: string | number;
  gradient: string; glowColor: string;
}) {
  return (
    <div
      className="group relative overflow-hidden rounded-2xl p-5 transition-all duration-300 hover:-translate-y-1"
      style={{
        background: "rgba(10,18,40,0.7)",
        border: "1px solid rgba(255,255,255,0.07)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
      }}
    >
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl"
        style={{ background: `radial-gradient(circle at 20% 20%, ${glowColor}, transparent 70%)` }} />
      <div className="absolute top-0 left-0 right-0 h-px" style={{ background: gradient }} />
      <div className="relative z-10">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
          style={{ background: glowColor, boxShadow: `0 0 16px ${glowColor}` }}>
          {icon}
        </div>
        <div className="text-3xl font-black text-white mb-1">{value}</div>
        <div className="text-sm font-medium text-slate-400">{label}</div>
      </div>
    </div>
  );
}

function MiniBarChart({ data }: { data: number[] }) {
  const max = Math.max(...data, 1);
  return (
    <div className="flex items-end gap-0.5 h-20 w-full">
      {data.map((v, i) => (
        <div
          key={i}
          style={{
            height: `${(v / max) * 100}%`,
            background: `linear-gradient(to top, rgba(6,182,212,0.8), rgba(99,102,241,0.6))`,
            boxShadow: v > 0 ? "0 0 4px rgba(6,182,212,0.4)" : "none",
          }}
          className="flex-1 rounded-sm min-h-[2px] transition-all duration-300"
        />
      ))}
    </div>
  );
}

export default function DoctorDashboardPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [analytics, setAnalytics] = useState<DoctorAnalytics | null>(null);
  const [historyData, setHistoryData] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch_ = async () => {
      if (!session?.accessToken || !session?.user?.id) return;
      try {
        const [analyticsRes, histRes] = await Promise.all([
          fetch(`${API}/api/v1/analytics/doctor/${session.user.id}`, {
            headers: { Authorization: `Bearer ${session.accessToken}` },
          }),
          fetch(`${API}/api/v1/analytics/doctor/${session.user.id}/history?days=14`, {
            headers: { Authorization: `Bearer ${session.accessToken}` },
          }),
        ]);
        if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
        if (histRes.ok) {
          const hist = await histRes.json();
          setHistoryData((hist as { count: number }[]).map((d) => d.count));
        }
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    };
    fetch_();
  }, [session]);

  const a = analytics;
  const todayAppts = a?.today_appointments || [];
  const stats = a?.stats || { active_patients: 0, pending_alerts: 0, completion_rate_pct: 0, total_appointments_30d: 0 };
  const hour = new Date().getHours();
  const timeOfDay = hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
  const lastName = session?.user?.name?.split(" ").slice(-1)[0] || "Doctor";

  return (
    <div className="max-w-6xl mx-auto space-y-8">

      {/* ─── Greeting Bar ─── */}
      <div
        className="rounded-2xl p-6 relative overflow-hidden border border-indigo-500/20"
        style={{
          background: "linear-gradient(135deg, rgba(99,102,241,0.1) 0%, rgba(139,92,246,0.06) 50%, rgba(10,18,40,0.8) 100%)",
        }}
      >
        <div className="absolute top-0 left-0 right-0 h-px"
          style={{ background: "linear-gradient(90deg, transparent, rgba(99,102,241,0.5), transparent)" }} />
        <div
          className="absolute inset-0 rounded-2xl"
          style={{
            backgroundImage: "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.03) 1px, transparent 0)",
            backgroundSize: "24px 24px",
          }}
        />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-indigo-400 uppercase tracking-widest mb-1">
              {format(new Date(), "EEEE, MMMM d")}
            </p>
            <h1 className="text-2xl font-black text-white">
              Good {timeOfDay}, Dr. {lastName} 👋
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              {todayAppts.length} appointment{todayAppts.length !== 1 ? "s" : ""} scheduled today
            </p>
          </div>
          <button
            onClick={() => router.push("/doctor/schedule")}
            className="group relative overflow-hidden flex items-center gap-2 px-5 py-3 rounded-xl font-bold text-sm text-white transition-all hover:-translate-y-0.5 hover:shadow-[0_0_20px_rgba(99,102,241,0.3)]"
            style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)" }}
          >
            <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-colors" />
            <Calendar className="w-4 h-4 relative z-10" />
            <span className="relative z-10">Full Schedule</span>
          </button>
        </div>
      </div>

      {/* ─── Stats ─── */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-36" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon={<Users className="w-5 h-5 text-indigo-300" />}
            label="Active Patients"
            value={stats.active_patients}
            gradient="linear-gradient(90deg, rgba(99,102,241,0.8), transparent)"
            glowColor="rgba(99,102,241,0.18)"
          />
          <StatCard
            icon={<Calendar className="w-5 h-5 text-cyan-300" />}
            label="Appointments (30d)"
            value={stats.total_appointments_30d}
            gradient="linear-gradient(90deg, rgba(6,182,212,0.8), transparent)"
            glowColor="rgba(6,182,212,0.15)"
          />
          <StatCard
            icon={<CheckCircle2 className="w-5 h-5 text-emerald-300" />}
            label="Completion Rate"
            value={`${stats.completion_rate_pct}%`}
            gradient="linear-gradient(90deg, rgba(52,211,153,0.8), transparent)"
            glowColor="rgba(52,211,153,0.15)"
          />
          <StatCard
            icon={<AlertTriangle className="w-5 h-5 text-amber-300" />}
            label="Pending Alerts"
            value={stats.pending_alerts}
            gradient="linear-gradient(90deg, rgba(245,158,11,0.8), transparent)"
            glowColor="rgba(245,158,11,0.15)"
          />
        </div>
      )}

      {/* ─── Schedule + Chart ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Today's appointments */}
        <div
          className="lg:col-span-2 rounded-2xl overflow-hidden border border-white/[0.06]"
          style={{ background: "rgba(10,18,40,0.7)", backdropFilter: "blur(12px)" }}
        >
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.05]">
            <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500 flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-indigo-400" /> Today&apos;s Appointments
            </h2>
            <button
              onClick={() => router.push("/doctor/schedule")}
              className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
            >
              All <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {loading ? (
            <div className="p-4 space-y-3">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}
            </div>
          ) : todayAppts.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-14 text-center">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center border border-white/[0.06]"
                style={{ background: "rgba(255,255,255,0.03)" }}>
                <Calendar className="w-6 h-6 text-slate-600" />
              </div>
              <p className="text-slate-500 text-sm">No appointments today</p>
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {todayAppts.map((appt) => {
                const s = STATUS_STYLES[appt.status] || STATUS_STYLES.scheduled;
                return (
                  <div
                    key={appt.id}
                    className="flex items-center gap-4 px-6 py-4 hover:bg-white/[0.02] transition-colors group"
                  >
                    <div className="text-xs text-slate-600 font-mono w-16 flex-shrink-0">
                      {appt.start_time ? format(parseISO(appt.start_time), "h:mm a") : "—"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {TYPE_ICON[appt.type] || TYPE_ICON["in-person"]}
                        <span className="font-semibold text-white text-sm truncate">
                          {appt.patient_name || "Patient"}
                        </span>
                      </div>
                      {appt.reason && (
                        <p className="text-xs text-slate-600 truncate mt-0.5">{appt.reason}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span
                        className="text-[11px] font-bold px-2.5 py-1 rounded-full border capitalize"
                        style={{ background: s.bg, color: s.text, borderColor: s.border }}
                      >
                        {appt.status}
                      </span>
                      {appt.type === "video" && appt.status !== "cancelled" && (
                        <button
                          onClick={() => router.push(`/doctor/telemedicine/${appt.id}`)}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-bold text-white transition-all hover:scale-105"
                          style={{ background: "linear-gradient(135deg, #0891b2, #0e7490)", boxShadow: "0 0 10px rgba(8,145,178,0.3)" }}
                        >
                          <Video className="w-3 h-3" /> Join
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 14-day volume chart */}
        <div
          className="rounded-2xl p-6 flex flex-col border border-white/[0.06]"
          style={{ background: "rgba(10,18,40,0.7)", backdropFilter: "blur(12px)" }}
        >
          <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500 flex items-center gap-2 mb-5">
            <BarChart3 className="w-3.5 h-3.5 text-indigo-400" /> Volume (14d)
          </h2>

          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <Skeleton className="w-full h-24" />
            </div>
          ) : historyData.length > 0 ? (
            <>
              <div className="flex-1">
                <MiniBarChart data={historyData.slice(-14)} />
              </div>
              <div className="flex justify-between text-[10px] text-slate-700 mt-2 mb-4">
                <span>14d ago</span><span>Today</span>
              </div>
              <div className="pt-4 border-t border-white/[0.05]">
                <div className="text-3xl font-black text-white">
                  {historyData.reduce((a, b) => a + b, 0)}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">Total appointments</div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center gap-2">
              <BarChart3 className="w-8 h-8 text-slate-700" />
              <p className="text-slate-600 text-sm">No data yet</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
