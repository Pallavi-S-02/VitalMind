"use client";

import { useState, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import {
  Heart,
  Activity,
  Thermometer,
  Wind,
  Droplets,
  Weight,
  Zap,
  RefreshCw,
  Plus,
  AlertTriangle,
  CheckCircle,
  Clock,
  Wifi,
  WifiOff,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface Vitals {
  heart_rate?: number;
  spo2?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  temperature_c?: number;
  respiratory_rate?: number;
  blood_glucose_mgdl?: number;
  weight_kg?: number;
  _timestamp?: string;
  _source?: string;
}

interface LogEntry {
  id: string;
  timestamp: string;
  heart_rate?: number;
  spo2?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  temperature_c?: number;
  source?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Vitals configuration
// ─────────────────────────────────────────────────────────────────────────────

interface VitalConfig {
  label: string;
  field: keyof Vitals;
  unit: string;
  icon: React.ElementType;
  iconColor: string;
  bgGradient: string;
  normalRange: [number, number];
  format: (v: number) => string;
}

const VITAL_CONFIGS: VitalConfig[] = [
  {
    label: "Heart Rate",
    field: "heart_rate",
    unit: "bpm",
    icon: Heart,
    iconColor: "text-rose-400",
    bgGradient: "from-rose-950/60 to-rose-900/30",
    normalRange: [60, 100],
    format: (v) => v.toFixed(0),
  },
  {
    label: "SpO₂",
    field: "spo2",
    unit: "%",
    icon: Activity,
    iconColor: "text-sky-400",
    bgGradient: "from-sky-950/60 to-sky-900/30",
    normalRange: [95, 100],
    format: (v) => v.toFixed(1),
  },
  {
    label: "Blood Pressure",
    field: "systolic_bp",
    unit: "mmHg",
    icon: Zap,
    iconColor: "text-violet-400",
    bgGradient: "from-violet-950/60 to-violet-900/30",
    normalRange: [90, 130],
    format: (v) => v.toFixed(0),
  },
  {
    label: "Temperature",
    field: "temperature_c",
    unit: "°C",
    icon: Thermometer,
    iconColor: "text-amber-400",
    bgGradient: "from-amber-950/60 to-amber-900/30",
    normalRange: [36.1, 37.2],
    format: (v) => v.toFixed(1),
  },
  {
    label: "Respiratory Rate",
    field: "respiratory_rate",
    unit: "br/min",
    icon: Wind,
    iconColor: "text-teal-400",
    bgGradient: "from-teal-950/60 to-teal-900/30",
    normalRange: [12, 20],
    format: (v) => v.toFixed(0),
  },
  {
    label: "Blood Glucose",
    field: "blood_glucose_mgdl",
    unit: "mg/dL",
    icon: Droplets,
    iconColor: "text-emerald-400",
    bgGradient: "from-emerald-950/60 to-emerald-900/30",
    normalRange: [70, 140],
    format: (v) => v.toFixed(1),
  },
  {
    label: "Weight",
    field: "weight_kg",
    unit: "kg",
    icon: Weight,
    iconColor: "text-indigo-400",
    bgGradient: "from-indigo-950/60 to-indigo-900/30",
    normalRange: [0, 999],
    format: (v) => v.toFixed(1),
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// VitalCard component
// ─────────────────────────────────────────────────────────────────────────────

function VitalCard({
  config,
  value,
  diastolic,
  animate,
}: {
  config: VitalConfig;
  value?: number;
  diastolic?: number;
  animate: boolean;
}) {
  const Icon = config.icon;
  const hasValue = value !== undefined && value !== null;
  const [lo, hi] = config.normalRange;
  const isAbnormal = hasValue && (value < lo || value > hi);

  return (
    <div
      className={`relative bg-gradient-to-br ${config.bgGradient} border rounded-2xl p-5 overflow-hidden transition-all duration-300 ${
        isAbnormal ? "border-red-600/60 shadow-lg shadow-red-900/20" : "border-white/10"
      } ${animate && hasValue ? "ring-1 ring-white/20" : ""}`}
    >
      {/* Pulse ring animation on new data */}
      {animate && hasValue && (
        <span className="absolute inset-0 rounded-2xl animate-ping ring-1 ring-white/10 opacity-30" />
      )}

      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
            {config.label}
          </p>
          {isAbnormal && (
            <span className="text-[10px] font-bold text-red-400 flex items-center gap-1 mt-0.5">
              <AlertTriangle className="h-3 w-3" /> Out of range
            </span>
          )}
        </div>
        <div
          className={`p-2 rounded-xl bg-white/5 ${
            isAbnormal ? "bg-red-900/30" : ""
          }`}
        >
          <Icon className={`h-5 w-5 ${isAbnormal ? "text-red-400" : config.iconColor}`} />
        </div>
      </div>

      <div className="flex items-end gap-2">
        {hasValue ? (
          <>
            <span className="text-3xl font-bold text-white tabular-nums">
              {config.format(value)}
              {config.field === "systolic_bp" && diastolic !== undefined && (
                <span className="text-xl text-gray-400 font-normal">/{diastolic.toFixed(0)}</span>
              )}
            </span>
            <span className="text-sm text-gray-400 mb-1">{config.unit}</span>
          </>
        ) : (
          <span className="text-2xl font-bold text-gray-600">—</span>
        )}
      </div>

      {hasValue && !isAbnormal && (
        <div className="flex items-center gap-1 mt-2 text-emerald-400 text-xs font-medium">
          <CheckCircle className="h-3 w-3" /> Normal
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Manual entry form
// ─────────────────────────────────────────────────────────────────────────────

function ManualEntryForm({
  onSubmit,
  onClose,
}: {
  onSubmit: (data: Record<string, string>) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<Record<string, string>>({});

  const fields = [
    { key: "heart_rate", label: "Heart Rate (bpm)" },
    { key: "spo2", label: "SpO₂ (%)" },
    { key: "systolic_bp", label: "Systolic BP (mmHg)" },
    { key: "diastolic_bp", label: "Diastolic BP (mmHg)" },
    { key: "temperature", label: "Temperature (°C)" },
    { key: "respiratory_rate", label: "Respiratory Rate (br/min)" },
    { key: "blood_glucose", label: "Blood Glucose (mg/dL)" },
    { key: "weight", label: "Weight (kg)" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-gray-900 border border-white/10 rounded-2xl p-6 shadow-2xl">
        <h2 className="text-lg font-bold text-white mb-4">Log Vitals Manually</h2>
        <div className="grid grid-cols-2 gap-3 mb-5">
          {fields.map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs text-gray-400 mb-1">{label}</label>
              <input
                type="number"
                step="any"
                value={form[key] || ""}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                className="w-full bg-gray-800 border border-white/10 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                placeholder="—"
              />
            </div>
          ))}
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => onSubmit(form)}
            className="flex-1 py-2.5 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-semibold text-sm transition-colors"
          >
            Save Vitals
          </button>
          <button
            onClick={onClose}
            className="px-5 py-2.5 bg-white/5 hover:bg-white/10 text-gray-300 rounded-xl text-sm transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function PatientVitalsPage() {
  const { data: session } = useSession();
  const [vitals, setVitals] = useState<Vitals | null>(null);
  const [history, setHistory] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [animateCards, setAnimateCards] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout>();

  const fetchVitals = async (showLoader = true) => {
    if (!session?.user?.id || !session?.accessToken) return;
    if (showLoader) setIsRefreshing(true);
    setError(null);
    try {
      const [curRes, histRes] = await Promise.all([
        fetch(`${API}/api/v1/vitals/${session.user.id}/current`, {
          headers: { Authorization: `Bearer ${session.accessToken}` },
        }),
        fetch(`${API}/api/v1/vitals/${session.user.id}/audit?limit=10`, {
          headers: { Authorization: `Bearer ${session.accessToken}` },
        }),
      ]);

      if (curRes.ok) {
        const data = await curRes.json();
        setVitals(data);
        setAnimateCards(true);
        setTimeout(() => setAnimateCards(false), 1500);
      }
      if (histRes.ok) {
        const data = await histRes.json();
        setHistory(data.readings || []);
      }
    } catch {
      setError("Unable to load vitals. Check your connection.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchVitals(false);
    // Poll every 30s for fresh data from devices
    intervalRef.current = setInterval(() => fetchVitals(false), 30000);
    return () => clearInterval(intervalRef.current);
  }, [session]);

  const handleManualSubmit = async (form: Record<string, string>) => {
    const cleanPayload: Record<string, number> = {};
    for (const [key, val] of Object.entries(form)) {
      if (val.trim()) cleanPayload[key] = parseFloat(val);
    }
    try {
      const res = await fetch(`${API}/api/v1/devices/vitals/manual`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify(cleanPayload),
      });
      if (!res.ok) throw new Error("Failed to save vitals");
      setShowManualEntry(false);
      setSubmitSuccess(true);
      setTimeout(() => setSubmitSuccess(false), 3000);
      fetchVitals(true);
    } catch {
      setError("Failed to save vitals. Please try again.");
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-10 w-10 text-rose-400 animate-pulse" />
          <p className="text-gray-400">Loading vitals...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      {showManualEntry && (
        <ManualEntryForm
          onSubmit={handleManualSubmit}
          onClose={() => setShowManualEntry(false)}
        />
      )}

      {/* Header */}
      <div className="px-6 pt-8 pb-6 max-w-6xl mx-auto">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="p-2.5 bg-rose-600/20 border border-rose-500/30 rounded-xl">
                <Activity className="h-6 w-6 text-rose-400" />
              </div>
              <h1 className="text-3xl font-bold text-white tracking-tight">My Vitals</h1>
            </div>
            <div className="flex items-center gap-2 ml-[52px]">
              <Wifi className="h-3.5 w-3.5 text-emerald-400" />
              <p className="text-sm text-gray-400">
                Auto-refreshes every 30 seconds · Last updated:{" "}
                {vitals?._timestamp
                  ? new Date(vitals._timestamp).toLocaleTimeString()
                  : "Never"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchVitals(true)}
              disabled={isRefreshing}
              className="p-2.5 bg-white/5 border border-white/10 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={() => setShowManualEntry(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-medium text-sm transition-colors shadow-lg shadow-violet-900/40"
            >
              <Plus className="h-4 w-4" />
              Log Vitals
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 pb-16 space-y-6">
        {/* Success Toast */}
        {submitSuccess && (
          <div className="flex items-center gap-3 bg-emerald-900/30 border border-emerald-700/40 rounded-xl px-5 py-3 text-emerald-200 text-sm animate-in fade-in slide-in-from-top-2">
            <CheckCircle className="h-5 w-5" />
            Vitals saved successfully
          </div>
        )}

        {error && (
          <div className="flex items-center gap-3 bg-red-900/20 border border-red-800/40 rounded-xl px-5 py-3 text-red-300 text-sm">
            <AlertTriangle className="h-5 w-5" />
            {error}
          </div>
        )}

        {/* Vitals grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {VITAL_CONFIGS.map((cfg) => (
            <VitalCard
              key={cfg.field}
              config={cfg}
              value={vitals?.[cfg.field] as number | undefined}
              diastolic={cfg.field === "systolic_bp" ? (vitals?.diastolic_bp as number | undefined) : undefined}
              animate={animateCards}
            />
          ))}
        </div>

        {/* Source badge */}
        {vitals?._source && vitals._source !== "none" && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Wifi className="h-3.5 w-3.5" />
            Data source: <span className="font-medium text-gray-400">{vitals._source}</span>
          </div>
        )}

        {/* Recent readings */}
        {history.length > 0 && (
          <div className="bg-gray-900/80 border border-white/10 rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-white/5">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
                Recent Readings
              </h2>
            </div>
            <div className="divide-y divide-white/5">
              {history.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-center justify-between px-6 py-3.5 hover:bg-white/5 transition-colors text-sm"
                >
                  <div className="flex items-center gap-3 text-gray-400">
                    <Clock className="h-4 w-4 flex-shrink-0" />
                    <span>{new Date(entry.timestamp).toLocaleString()}</span>
                    <span className="text-xs px-2 py-0.5 bg-white/5 rounded-full">
                      {entry.source || "manual"}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-gray-300 flex-wrap justify-end">
                    {entry.heart_rate && (
                      <span>
                        <span className="text-gray-500 mr-1">HR</span>
                        <span className="text-rose-300 font-medium">{entry.heart_rate}</span>
                      </span>
                    )}
                    {entry.spo2 && (
                      <span>
                        <span className="text-gray-500 mr-1">SpO₂</span>
                        <span className="text-sky-300 font-medium">{entry.spo2}%</span>
                      </span>
                    )}
                    {entry.systolic_bp && (
                      <span>
                        <span className="text-gray-500 mr-1">BP</span>
                        <span className="text-violet-300 font-medium">
                          {entry.systolic_bp}/{entry.diastolic_bp}
                        </span>
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* No data state */}
        {(!vitals || vitals._source === "none") && history.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 bg-gray-900/60 border border-dashed border-white/10 rounded-2xl text-center">
            <Activity className="h-12 w-12 text-gray-600 mb-4" />
            <h3 className="text-white font-semibold">No vitals recorded yet</h3>
            <p className="text-gray-400 text-sm mt-1 mb-6 max-w-xs">
              Connect an IoT device or log your vitals manually to get started.
            </p>
            <button
              onClick={() => setShowManualEntry(true)}
              className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-medium text-sm transition-colors"
            >
              Log First Reading
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
