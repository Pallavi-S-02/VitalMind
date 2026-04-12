"use client";

/**
 * EWSBadge.tsx — Color-coded Early Warning Score badge.
 * Displays NEWS2 score with appropriate risk color and label.
 */

import { cn } from "@/lib/utils";

interface EWSBadgeProps {
  score: number;
  riskLevel?: string;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

const RISK_CONFIG = {
  0: {
    label: "Low",
    bg: "bg-emerald-900/60",
    border: "border-emerald-700/50",
    text: "text-emerald-300",
    dot: "bg-emerald-400",
    ring: "shadow-emerald-900/30",
  },
  1: {
    label: "Low-Med",
    bg: "bg-yellow-900/60",
    border: "border-yellow-700/50",
    text: "text-yellow-300",
    dot: "bg-yellow-400",
    ring: "shadow-yellow-900/30",
  },
  2: {
    label: "Medium",
    bg: "bg-orange-900/60",
    border: "border-orange-700/50",
    text: "text-orange-300",
    dot: "bg-orange-400",
    ring: "shadow-orange-900/30",
  },
  3: {
    label: "HIGH",
    bg: "bg-red-900/60",
    border: "border-red-700/50",
    text: "text-red-300",
    dot: "bg-red-400",
    ring: "shadow-red-900/30",
  },
};

function getRiskLevel(score: number): 0 | 1 | 2 | 3 {
  if (score === 0) return 0;
  if (score <= 4) return 1;
  if (score <= 6) return 2;
  return 3;
}

export function EWSBadge({
  score,
  riskLevel,
  size = "md",
  showLabel = true,
  className,
}: EWSBadgeProps) {
  const level = getRiskLevel(score);
  const cfg = RISK_CONFIG[level];
  const isEmergency = level === 3;

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs gap-1",
    md: "px-2.5 py-1 text-sm gap-1.5",
    lg: "px-3.5 py-1.5 text-base gap-2",
  };

  const scoreSize = {
    sm: "text-xs font-bold",
    md: "text-sm font-bold",
    lg: "text-lg font-bold",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-xl border font-semibold transition-all",
        sizeClasses[size],
        cfg.bg,
        cfg.border,
        cfg.text,
        isEmergency && "animate-pulse shadow-lg",
        isEmergency && cfg.ring,
        className
      )}
      title={`NEWS2 Score: ${score} — Risk: ${riskLevel || cfg.label}`}
    >
      <span className={cn("rounded-full flex-shrink-0", cfg.dot, size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2")} />
      <span className={scoreClasses[size]}>NEWS2 {score}</span>
      {showLabel && (
        <span className="opacity-80 font-medium">
          · {riskLevel || cfg.label}
        </span>
      )}
    </span>
  );
}

const scoreClasses: Record<string, string> = {
  sm: "text-xs font-bold",
  md: "text-sm font-bold",
  lg: "text-lg font-bold",
};
