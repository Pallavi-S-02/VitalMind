"use client";

/**
 * AlertBanner.tsx — Real-time floating alert banner for monitoring alerts.
 * Shows the latest unacknowledged alert with severity color, NEWS2 score,
 * and a one-click acknowledge button.
 */

import { useState, useEffect } from "react";
import { AlertTriangle, XCircle, Bell, CheckCheck, X } from "lucide-react";
import { MonitoringAlert } from "@/store/monitoringStore";
import { cn } from "@/lib/utils";

interface AlertBannerProps {
  alerts: MonitoringAlert[];
  onAcknowledge: (alertId: string) => void;
  maxVisible?: number;
}

const LEVEL_CONFIG = {
  1: {
    bg: "bg-yellow-950/95",
    border: "border-yellow-700/60",
    text: "text-yellow-200",
    icon: Bell,
    iconColor: "text-yellow-400",
    label: "Nurse Alert",
    pulse: false,
  },
  2: {
    bg: "bg-orange-950/95",
    border: "border-orange-700/60",
    text: "text-orange-200",
    icon: AlertTriangle,
    iconColor: "text-orange-400",
    label: "Physician Alert",
    pulse: false,
  },
  3: {
    bg: "bg-red-950/95",
    border: "border-red-700/60",
    text: "text-red-200",
    icon: XCircle,
    iconColor: "text-red-400",
    label: "🚨 EMERGENCY",
    pulse: true,
  },
};

function SingleAlertBanner({
  alert,
  onAcknowledge,
  onDismiss,
}: {
  alert: MonitoringAlert;
  onAcknowledge: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const cfg = LEVEL_CONFIG[alert.level as 1 | 2 | 3] || LEVEL_CONFIG[1];
  const Icon = cfg.icon;
  const timeAgo = getTimeAgo(alert.timestamp);

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-2xl border p-4 backdrop-blur-md shadow-2xl",
        "animate-in slide-in-from-top-2 fade-in duration-300",
        cfg.bg,
        cfg.border,
        cfg.pulse && "animate-pulse"
      )}
      role="alert"
    >
      <div className={cn("p-2 rounded-xl bg-white/5 flex-shrink-0", cfg.iconColor)}>
        <Icon className="h-5 w-5" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={cn("text-xs font-bold uppercase tracking-wider", cfg.iconColor)}>
            {cfg.label}
          </span>
          <span className="text-xs text-gray-500">·</span>
          <span className="text-xs text-gray-400">NEWS2 {alert.news2_score}</span>
          <span className="text-xs text-gray-500">·</span>
          <span className="text-xs text-gray-400">{timeAgo}</span>
        </div>

        {alert.patient_name && (
          <p className={cn("text-sm font-semibold", cfg.text)}>
            {alert.patient_name}
          </p>
        )}
        <p className={cn("text-sm leading-relaxed mt-0.5 line-clamp-2", cfg.text)}>
          {alert.message}
        </p>

        {alert.vitals_summary && (
          <p className="text-xs text-gray-400 mt-1 font-mono">{alert.vitals_summary}</p>
        )}
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {!alert.acknowledged && (
          <button
            onClick={() => onAcknowledge(alert.id)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-xl text-xs font-semibold text-white transition-colors"
            title="Acknowledge alert"
          >
            <CheckCheck className="h-3.5 w-3.5" />
            Ack
          </button>
        )}
        {alert.acknowledged && (
          <span className="text-xs text-emerald-400 flex items-center gap-1">
            <CheckCheck className="h-3.5 w-3.5" />
            Acked
          </span>
        )}
        <button
          onClick={() => onDismiss(alert.id)}
          className="p-1.5 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
          title="Dismiss from view"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function getTimeAgo(timestamp: string): string {
  try {
    const diff = Date.now() - new Date(timestamp).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
  } catch {
    return "just now";
  }
}

export function AlertBanner({ alerts, onAcknowledge, maxVisible = 3 }: AlertBannerProps) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const visible = alerts
    .filter((a) => !dismissed.has(a.id))
    .slice(0, maxVisible);

  const handleDismiss = (id: string) => {
    setDismissed((prev) => new Set([...Array.from(prev), id]));
  };

  if (visible.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 w-full max-w-md space-y-2">
      {visible.map((alert) => (
        <SingleAlertBanner
          key={alert.id}
          alert={alert}
          onAcknowledge={onAcknowledge}
          onDismiss={handleDismiss}
        />
      ))}
    </div>
  );
}
