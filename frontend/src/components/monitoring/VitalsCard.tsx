"use client";

/**
 * VitalsCard.tsx — Real-time updating vitals card for the monitoring wall.
 * Shows all vital signs for a patient with color-coded status, NEWS2 badge,
 * and last-update timestamp. Animates on data refresh.
 */

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Heart,
  Activity,
  Thermometer,
  Wind,
  Droplets,
  Zap,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Clock,
} from "lucide-react";
import { PatientVitals, News2Score, MonitoredPatient } from "@/store/monitoringStore";
import { EWSBadge } from "./EWSBadge";
import { cn } from "@/lib/utils";

// ─────────────────────────────────────────────────────────────────────────────
// Vital sign config
// ─────────────────────────────────────────────────────────────────────────────

const VITAL_DEFS = [
  {
    key: "heart_rate" as keyof PatientVitals,
    label: "HR",
    unit: "bpm",
    icon: Heart,
    iconColor: "text-rose-400",
    normalRange: [60, 100] as [number, number],
    format: (v: number) => v.toFixed(0),
  },
  {
    key: "spo2" as keyof PatientVitals,
    label: "SpO₂",
    unit: "%",
    icon: Activity,
    iconColor: "text-sky-400",
    normalRange: [95, 100] as [number, number],
    format: (v: number) => v.toFixed(1),
  },
  {
    key: "systolic_bp" as keyof PatientVitals,
    label: "BP",
    unit: "mmHg",
    icon: Zap,
    iconColor: "text-violet-400",
    normalRange: [90, 130] as [number, number],
    format: (v: number) => v.toFixed(0),
  },
  {
    key: "temperature_c" as keyof PatientVitals,
    label: "Temp",
    unit: "°C",
    icon: Thermometer,
    iconColor: "text-amber-400",
    normalRange: [36.1, 37.2] as [number, number],
    format: (v: number) => v.toFixed(1),
  },
  {
    key: "respiratory_rate" as keyof PatientVitals,
    label: "RR",
    unit: "/min",
    icon: Wind,
    iconColor: "text-teal-400",
    normalRange: [12, 20] as [number, number],
    format: (v: number) => v.toFixed(0),
  },
  {
    key: "blood_glucose_mgdl" as keyof PatientVitals,
    label: "Glu",
    unit: "mg/dL",
    icon: Droplets,
    iconColor: "text-emerald-400",
    normalRange: [70, 140] as [number, number],
    format: (v: number) => v.toFixed(0),
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// Mini vital cell
// ─────────────────────────────────────────────────────────────────────────────

function VitalCell({
  def,
  vitals,
  diastolic,
}: {
  def: (typeof VITAL_DEFS)[0];
  vitals: PatientVitals;
  diastolic?: number;
}) {
  const Icon = def.icon;
  const value = vitals[def.key] as number | undefined;
  const hasValue = value !== undefined && value !== null;
  const [lo, hi] = def.normalRange;
  const isAbnormal = hasValue && (value < lo || value > hi);

  return (
    <div
      className={cn(
        "flex flex-col items-start p-2 rounded-xl bg-white/5 border transition-all",
        isAbnormal
          ? "border-red-700/50 bg-red-950/20"
          : "border-white/5"
      )}
    >
      <div className="flex items-center gap-1 mb-1">
        <Icon
          className={cn(
            "h-3 w-3",
            isAbnormal ? "text-red-400" : def.iconColor
          )}
        />
        <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">
          {def.label}
        </span>
      </div>
      {hasValue ? (
        <span
          className={cn(
            "text-sm font-bold tabular-nums",
            isAbnormal ? "text-red-300" : "text-white"
          )}
        >
          {def.format(value)}
          {def.key === "systolic_bp" && diastolic !== undefined && (
            <span className="font-normal text-gray-400">/{diastolic.toFixed(0)}</span>
          )}
          <span className="text-[10px] font-normal text-gray-500 ml-0.5">{def.unit}</span>
        </span>
      ) : (
        <span className="text-sm font-bold text-gray-600">—</span>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VitalsCard
// ─────────────────────────────────────────────────────────────────────────────

interface VitalsCardProps {
  patient: MonitoredPatient;
  vitals?: PatientVitals;
  news2?: News2Score;
  hasUnacknowledgedAlert?: boolean;
  alertLevel?: 1 | 2 | 3;
  href?: string;
}

export function VitalsCard({
  patient,
  vitals,
  news2,
  hasUnacknowledgedAlert = false,
  alertLevel,
  href,
}: VitalsCardProps) {
  const [flash, setFlash] = useState(false);
  const prevVitals = useRef<PatientVitals | undefined>(vitals);

  // Flash animation on vitals update
  useEffect(() => {
    if (vitals && vitals !== prevVitals.current) {
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 800);
      prevVitals.current = vitals;
      return () => clearTimeout(t);
    }
  }, [vitals]);

  const news2Score = news2?.news2_score ?? 0;
  const riskLevel = news2?.risk_level ?? "Low";
  const isHighRisk = news2Score >= 5;
  const isCritical = news2Score >= 7 || alertLevel === 3;

  const cardBorder = isCritical
    ? "border-red-700/60 shadow-red-950/50"
    : isHighRisk
    ? "border-orange-700/40"
    : hasUnacknowledgedAlert
    ? "border-yellow-700/40"
    : "border-white/10";

  const lastUpdate = vitals?._timestamp
    ? new Date(vitals._timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : null;

  const cardContent = (
    <div
      className={cn(
        "relative bg-gray-900/80 border rounded-2xl p-4 backdrop-blur-sm transition-all duration-300 overflow-hidden",
        cardBorder,
        isCritical && "shadow-lg",
        flash && "ring-1 ring-white/20",
        href && "hover:border-white/20 hover:bg-gray-900/90 cursor-pointer"
      )}
    >
      {/* Critical pulse border overlay */}
      {isCritical && (
        <span className="absolute inset-0 rounded-2xl animate-ping ring-1 ring-red-500/30 pointer-events-none" />
      )}

      {/* Top row — patient info + EWS badge */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="text-sm font-bold text-white truncate">{patient.name}</p>
          <div className="flex items-center gap-2 mt-0.5">
            {patient.room && (
              <span className="text-[10px] text-gray-500 font-medium">
                Room {patient.room}
              </span>
            )}
            {patient.age && (
              <span className="text-[10px] text-gray-500">· {patient.age}y</span>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <EWSBadge score={news2Score} riskLevel={riskLevel} size="sm" showLabel={false} />
          {hasUnacknowledgedAlert && (
            <span className="flex items-center gap-1 text-[10px] text-yellow-400 font-medium">
              <AlertTriangle className="h-2.5 w-2.5" /> Alert
            </span>
          )}
        </div>
      </div>

      {/* Vitals grid */}
      {vitals ? (
        <div className="grid grid-cols-3 gap-1.5 mb-3">
          {VITAL_DEFS.map((def) => (
            <VitalCell
              key={def.key}
              def={def}
              vitals={vitals}
              diastolic={
                def.key === "systolic_bp"
                  ? (vitals.diastolic_bp as number | undefined)
                  : undefined
              }
            />
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center py-6 mb-3 bg-gray-800/30 rounded-xl border border-dashed border-white/5">
          <p className="text-xs text-gray-600">No vitals data</p>
        </div>
      )}

      {/* Footer — last update + status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <Clock className="h-3 w-3" />
          {lastUpdate ? `Updated ${lastUpdate}` : "Awaiting data"}
        </div>
        {vitals && (
          <div className="flex items-center gap-1 text-[10px]">
            {hasUnacknowledgedAlert ? (
              <span className="text-yellow-500 font-medium flex items-center gap-0.5">
                <AlertTriangle className="h-2.5 w-2.5" />
                Needs attention
              </span>
            ) : (
              <span className="text-emerald-500 font-medium flex items-center gap-0.5">
                <CheckCircle className="h-2.5 w-2.5" />
                Stable
              </span>
            )}
          </div>
        )}
        {href && <ChevronRight className="h-3.5 w-3.5 text-gray-600" />}
      </div>
    </div>
  );

  if (href) {
    return <Link href={href}>{cardContent}</Link>;
  }
  return cardContent;
}
