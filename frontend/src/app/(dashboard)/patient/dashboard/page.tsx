"use client";

import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  HeartPulse, Calendar, Pill, AlertCircle,
  TrendingUp, TrendingDown, Minus, ArrowRight,
  Activity, Target, BookOpen, Bot, Mic, Zap,
  ChevronRight, Stethoscope,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface PatientAnalytics {
  patient_id: string;
  appointments: { upcoming: number; last_visit: string | null; total: number };
  care_plan: { active: boolean; title: string | null; adherence_pct: number | null; tasks_done: number; tasks_total: number };
  medications: { active_count: number };
  alerts: { open_count: number };
  vitals_trend: Record<string, unknown>[];
}

// ─── Skeleton Loader ───
function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-xl animate-pulse ${className}`}
      style={{ background: "rgba(255,255,255,0.06)" }}
    />
  );
}

// ─── Premium Stat Card ───
function StatCard({
  icon, label, value, sub, gradient, glowColor, onClick,
}: {
  icon: React.ReactNode; label: string; value: string | number;
  sub?: string; gradient: string; glowColor: string; onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group relative overflow-hidden rounded-2xl p-5 text-left w-full transition-all duration-300 hover:-translate-y-1"
      style={{
        background: "rgba(10,18,40,0.7)",
        border: "1px solid rgba(255,255,255,0.07)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
      }}
    >
      {/* Hover glow */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl"
        style={{ background: `radial-gradient(circle at 20% 20%, ${glowColor}, transparent 70%)` }}
      />
      {/* Top gradient line */}
      <div className="absolute top-0 left-0 right-0 h-px" style={{ background: gradient }} />

      <div className="relative z-10">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
          style={{ background: glowColor, boxShadow: `0 0 16px ${glowColor}` }}
        >
          {icon}
        </div>
        <div className="text-3xl font-black text-white mb-1">{value}</div>
        <div className="text-sm font-medium text-slate-400">{label}</div>
        {sub && <div className="text-xs text-slate-600 mt-1">{sub}</div>}
        {onClick && (
          <div className="flex items-center gap-1 text-xs font-semibold mt-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
            style={{ color: glowColor.includes("6,182,212") ? "#22d3ee" : "#a78bfa" }}>
            View details <ArrowRight className="w-3 h-3" />
          </div>
        )}
      </div>
    </button>
  );
}

// ─── Adherence Ring ───
function AdherenceRing({ pct, size = 96 }: { pct: number; size?: number }) {
  const color = pct >= 70 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
  const r = 15.9;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" className="-rotate-90">
      <circle cx="18" cy="18" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
      <circle
        cx="18" cy="18" r={r} fill="none"
        stroke={color} strokeWidth="3"
        strokeDasharray={`${dash.toFixed(2)} ${(circ - dash).toFixed(2)}`}
        strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 4px ${color})` }}
      />
    </svg>
  );
}

// ─── Vitals Grid ───
function VitalsGrid({ vitals }: { vitals: Record<string, unknown>[] }) {
  if (!vitals?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-3">
        <HeartPulse className="w-8 h-8 text-slate-700" />
        <p className="text-sm text-slate-600">No recent vitals recorded</p>
      </div>
    );
  }
  const latest = vitals[0];
  const entries = Object.entries(latest)
    .filter(([k]) => !["patient_id", "timestamp", "device_id"].includes(k))
    .slice(0, 4);
  const vitalColors = ["cyan", "emerald", "indigo", "rose"];
  return (
    <div className="grid grid-cols-2 gap-3">
      {entries.map(([key, val], i) => (
        <div
          key={key}
          className="rounded-xl p-3 border border-white/[0.05]"
          style={{ background: "rgba(255,255,255,0.03)" }}
        >
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600 mb-1">
            {key.replace(/_/g, " ")}
          </div>
          <div className={`text-xl font-black text-${vitalColors[i]}-400`}>
            {String(val)}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function PatientDashboardPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [analytics, setAnalytics] = useState<PatientAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch_ = async () => {
      if (!session?.accessToken || !session?.user?.id) return;
      try {
        const res = await fetch(`${API}/api/v1/analytics/patient/${session.user.id}`, {
          headers: { Authorization: `Bearer ${session.accessToken}` },
        });
        if (res.ok) setAnalytics(await res.json());
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    };
    fetch_();
  }, [session]);

  const a = analytics;
  const adherence = a?.care_plan?.adherence_pct ?? null;
  const firstName = session?.user?.name?.split(" ")[0] || "";
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="max-w-6xl mx-auto space-y-8">

      {/* ─── Greeting bar ─── */}
      <div
        className="rounded-2xl p-6 relative overflow-hidden border border-white/[0.06]"
        style={{
          background: "linear-gradient(135deg, rgba(6,182,212,0.08) 0%, rgba(99,102,241,0.06) 50%, rgba(10,18,40,0.8) 100%)",
        }}
      >
        <div
          className="absolute inset-0 rounded-2xl"
          style={{
            backgroundImage: "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.03) 1px, transparent 0)",
            backgroundSize: "24px 24px",
          }}
        />
        <div className="absolute top-0 left-0 right-0 h-px"
          style={{ background: "linear-gradient(90deg, transparent, rgba(6,182,212,0.4), transparent)" }} />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
              </span>
              <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest">Health Monitoring Active</span>
            </div>
            <h1 className="text-2xl font-black text-white">
              {greeting}{firstName ? `, ${firstName}` : ""}! 👋
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })} · Here&apos;s your health overview.
            </p>
          </div>
          <div className="hidden md:flex items-center gap-3">
            <button
              onClick={() => router.push("/patient/ai-doctor")}
              className="group flex items-center gap-2.5 px-5 py-3 rounded-xl font-bold text-sm text-white transition-all hover:-translate-y-0.5 hover:shadow-[0_0_20px_rgba(6,182,212,0.3)]"
              style={{ background: "linear-gradient(135deg, #0891b2, #4f46e5)" }}
            >
              <Bot className="w-4 h-4" />
              Talk to Dr. Janvi AI
            </button>
          </div>
        </div>
      </div>

      {/* ─── Stats row ─── */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-36" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon={<Calendar className="w-5 h-5 text-indigo-300" />}
            label="Upcoming Appointments"
            value={a?.appointments.upcoming ?? 0}
            sub={a?.appointments.last_visit ? `Last: ${new Date(a.appointments.last_visit).toLocaleDateString()}` : "No past visits"}
            gradient="linear-gradient(90deg, rgba(99,102,241,0.8), transparent)"
            glowColor="rgba(99,102,241,0.18)"
            onClick={() => router.push("/patient/appointments")}
          />
          <StatCard
            icon={<Target className="w-5 h-5 text-emerald-300" />}
            label="Care Plan Tasks"
            value={a?.care_plan.tasks_done != null ? `${a.care_plan.tasks_done}/${a.care_plan.tasks_total}` : "—"}
            sub={a?.care_plan.title || "No active plan"}
            gradient="linear-gradient(90deg, rgba(52,211,153,0.8), transparent)"
            glowColor="rgba(52,211,153,0.15)"
            onClick={() => router.push("/patient/care-plan")}
          />
          <StatCard
            icon={<Pill className="w-5 h-5 text-cyan-300" />}
            label="Active Medications"
            value={a?.medications.active_count ?? 0}
            gradient="linear-gradient(90deg, rgba(6,182,212,0.8), transparent)"
            glowColor="rgba(6,182,212,0.15)"
            onClick={() => router.push("/patient/medications")}
          />
          <StatCard
            icon={<AlertCircle className="w-5 h-5 text-amber-300" />}
            label="Open Alerts"
            value={a?.alerts.open_count ?? 0}
            gradient="linear-gradient(90deg, rgba(245,158,11,0.8), transparent)"
            glowColor="rgba(245,158,11,0.15)"
          />
        </div>
      )}

      {/* ─── Middle row: Adherence + Vitals ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Adherence */}
        <div
          className="rounded-2xl p-6 border border-white/[0.06]"
          style={{ background: "rgba(10,18,40,0.7)", backdropFilter: "blur(12px)" }}
        >
          <div className="absolute top-0 left-0 right-0 h-px" />
          <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500 mb-5 flex items-center gap-2">
            <Target className="w-3.5 h-3.5 text-emerald-500" /> Care Plan Adherence
          </h2>
          {loading ? (
            <div className="flex items-center gap-6">
              <Skeleton className="w-24 h-24 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
                <Skeleton className="h-6 w-24 rounded-full" />
              </div>
            </div>
          ) : adherence !== null ? (
            <div className="flex items-center gap-6">
              <div className="relative flex-shrink-0">
                <AdherenceRing pct={adherence} size={96} />
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-2xl font-black text-white">{adherence}%</span>
                </div>
              </div>
              <div>
                <div className="text-base font-bold text-white">{a?.care_plan.title}</div>
                <div className="text-sm text-slate-500 mt-1">
                  {a?.care_plan.tasks_done} of {a?.care_plan.tasks_total} tasks done
                </div>
                <div className={`inline-flex items-center gap-1.5 mt-3 text-xs font-bold px-3 py-1.5 rounded-full ${
                  adherence >= 70 ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : adherence >= 40 ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                  : "bg-red-500/10 text-red-400 border border-red-500/20"
                }`}>
                  {adherence >= 70 ? <TrendingUp className="w-3 h-3" />
                    : adherence >= 40 ? <Minus className="w-3 h-3" />
                    : <TrendingDown className="w-3 h-3" />}
                  {adherence >= 70 ? "On track" : adherence >= 40 ? "Needs attention" : "Behind schedule"}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center py-8 gap-3 text-center">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center border border-white/[0.06]"
                style={{ background: "rgba(255,255,255,0.03)" }}>
                <Target className="w-6 h-6 text-slate-600" />
              </div>
              <p className="text-slate-500 text-sm">No active care plan</p>
              <button
                onClick={() => router.push("/patient/care-plan")}
                className="text-sm font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
              >
                Generate one <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Latest Vitals */}
        <div
          className="rounded-2xl p-6 border border-white/[0.06]"
          style={{ background: "rgba(10,18,40,0.7)", backdropFilter: "blur(12px)" }}
        >
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500 flex items-center gap-2">
              <HeartPulse className="w-3.5 h-3.5 text-rose-500" /> Latest Vitals
            </h2>
            <button
              onClick={() => router.push("/patient/vitals")}
              className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
            >
              View all <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          {loading ? (
            <div className="grid grid-cols-2 gap-3">
              {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-16" />)}
            </div>
          ) : (
            <VitalsGrid vitals={a?.vitals_trend || []} />
          )}
        </div>
      </div>

      {/* ─── Quick Actions ─── */}
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-600 mb-4">Quick Actions</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            {
              label: "Book Appointment",
              icon: <Calendar className="w-5 h-5" />,
              href: "/patient/appointments/book",
              gradient: "linear-gradient(135deg, #4f46e5, #7c3aed)",
              glow: "rgba(99,102,241,0.3)",
            },
            {
              label: "Active Prescriptions",
              icon: <Pill className="w-5 h-5" />,
              href: "/patient/prescriptions",
              gradient: "linear-gradient(135deg, #e11d48, #be123c)",
              glow: "rgba(225,29,72,0.3)",
            },
            {
              label: "Health Education",
              icon: <BookOpen className="w-5 h-5" />,
              href: "/patient/education",
              gradient: "linear-gradient(135deg, #059669, #047857)",
              glow: "rgba(5,150,105,0.3)",
            },
            {
              label: "Voice Assistant",
              icon: <Mic className="w-5 h-5" />,
              href: "/patient/voice-assistant",
              gradient: "linear-gradient(135deg, #0891b2, #0e7490)",
              glow: "rgba(8,145,178,0.3)",
            },
          ].map((item) => (
            <button
              key={item.label}
              onClick={() => router.push(item.href)}
              className="group relative overflow-hidden flex items-center gap-3 text-white rounded-2xl px-5 py-4 font-semibold text-sm transition-all duration-300 hover:-translate-y-1"
              style={{
                background: item.gradient,
                boxShadow: `0 4px 20px ${item.glow}`,
              }}
            >
              <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-colors duration-300" />
              <span className="relative z-10 flex items-center gap-3">
                {item.icon}
                {item.label}
              </span>
              <ChevronRight className="w-4 h-4 ml-auto relative z-10 opacity-50 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
            </button>
          ))}
        </div>
      </div>

      {/* ─── AI Doctor Promo Banner ─── */}
      <div
        className="rounded-2xl p-6 relative overflow-hidden border border-cyan-500/20 cursor-pointer group"
        style={{ background: "linear-gradient(135deg, rgba(6,182,212,0.08), rgba(99,102,241,0.06), rgba(10,18,40,0.9))" }}
        onClick={() => router.push("/patient/ai-doctor")}
      >
        <div className="absolute top-0 left-0 right-0 h-px"
          style={{ background: "linear-gradient(90deg, transparent, rgba(6,182,212,0.5), transparent)" }} />
        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl"
          style={{ background: "rgba(6,182,212,0.04)" }} />
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-5">
            <div className="w-14 h-14 rounded-2xl border border-cyan-500/20 flex items-center justify-center flex-shrink-0"
              style={{ background: "rgba(6,182,212,0.1)", boxShadow: "0 0 20px rgba(6,182,212,0.15)" }}>
              <Stethoscope className="w-7 h-7 text-cyan-400" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
                </span>
                <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">Dr. Janvi Available Now</span>
              </div>
              <h3 className="text-base font-black text-white">Start an AI Health Consultation</h3>
              <p className="text-sm text-slate-400 mt-0.5">Voice-powered diagnosis, prescription review, and 24/7 triage.</p>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm text-white transition-all group-hover:-translate-x-0.5"
            style={{ background: "linear-gradient(135deg, #0891b2, #4f46e5)" }}>
            <Zap className="w-4 h-4" />
            Consult Now
          </div>
        </div>
      </div>

    </div>
  );
}
