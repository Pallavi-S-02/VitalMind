"use client";

/**
 * VitalsChart.tsx — Recharts time-series line chart for vitals history.
 * Shows up to 6 vitals fields over a configurable time window.
 * Used in the patient deep-dive monitoring page.
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface VitalsDataPoint {
  timestamp: string;
  heart_rate?: number;
  spo2?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  temperature_c?: number;
  respiratory_rate?: number;
  blood_glucose_mgdl?: number;
}

interface VitalsChartProps {
  data: VitalsDataPoint[];
  title?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Series config
// ─────────────────────────────────────────────────────────────────────────────

const SERIES = [
  {
    key: "heart_rate",
    label: "Heart Rate",
    color: "#fb7185",
    unit: "bpm",
    normalMin: 60,
    normalMax: 100,
  },
  {
    key: "spo2",
    label: "SpO₂",
    color: "#38bdf8",
    unit: "%",
    normalMin: 95,
    normalMax: 100,
  },
  {
    key: "systolic_bp",
    label: "Systolic BP",
    color: "#a78bfa",
    unit: "mmHg",
    normalMin: 90,
    normalMax: 130,
  },
  {
    key: "temperature_c",
    label: "Temperature",
    color: "#fbbf24",
    unit: "°C",
    normalMin: 36.1,
    normalMax: 37.2,
  },
  {
    key: "respiratory_rate",
    label: "Resp. Rate",
    color: "#2dd4bf",
    unit: "/min",
    normalMin: 12,
    normalMax: 20,
  },
  {
    key: "blood_glucose_mgdl",
    label: "Blood Glucose",
    color: "#34d399",
    unit: "mg/dL",
    normalMin: 70,
    normalMax: 140,
  },
] as const;

type SeriesKey = (typeof SERIES)[number]["key"];

// ─────────────────────────────────────────────────────────────────────────────
// Custom tooltip
// ─────────────────────────────────────────────────────────────────────────────

function CustomTooltip({
  active,
  payload,
  label,
  activeSeries,
}: {
  active?: boolean;
  payload?: Array<{ color: string; name: string; value: number; unit?: string }>;
  label?: string;
  activeSeries: Set<SeriesKey>;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-gray-900 border border-white/10 rounded-xl p-3 shadow-2xl text-sm">
      <p className="text-gray-400 text-xs mb-2">{label}</p>
      {payload.map((item) => (
        <div key={item.name} className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full flex-shrink-0"
              style={{ background: item.color }}
            />
            <span className="text-gray-300">{item.name}</span>
          </div>
          <span className="text-white font-bold tabular-nums">
            {item.value?.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main chart
// ─────────────────────────────────────────────────────────────────────────────

export function VitalsChart({ data, title }: VitalsChartProps) {
  const [activeSeries, setActiveSeries] = useState<Set<SeriesKey>>(
    () => new Set<SeriesKey>(["heart_rate", "spo2", "systolic_bp"])
  );
  const [focusedSeries, setFocusedSeries] = useState<SeriesKey | null>(null);

  const toggleSeries = (key: SeriesKey) => {
    setActiveSeries((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Format timestamp for x-axis
  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return ts;
    }
  };

  const chartData = data.map((d) => ({
    ...d,
    _time: formatTime(d.timestamp),
  }));

  const activeSrs = SERIES.filter((s) => activeSeries.has(s.key));
  const focusedSrs = focusedSeries
    ? SERIES.find((s) => s.key === focusedSeries)
    : null;

  return (
    <div className="bg-gray-900/80 border border-white/10 rounded-2xl p-5">
      {title && (
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">
          {title}
        </h3>
      )}

      {/* Series toggles */}
      <div className="flex flex-wrap gap-2 mb-5">
        {SERIES.map((s) => {
          const isActive = activeSeries.has(s.key);
          return (
            <button
              key={s.key}
              onClick={() => toggleSeries(s.key)}
              onMouseEnter={() => setFocusedSeries(s.key)}
              onMouseLeave={() => setFocusedSeries(null)}
              className="flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-medium transition-all border"
              style={{
                borderColor: isActive ? s.color + "60" : "rgba(255,255,255,0.08)",
                background: isActive ? s.color + "20" : "rgba(255,255,255,0.03)",
                color: isActive ? s.color : "#6b7280",
              }}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: isActive ? s.color : "#4b5563" }}
              />
              {s.label}
              <span className="opacity-60">{s.unit}</span>
            </button>
          );
        })}
      </div>

      {/* Chart */}
      {data.length === 0 ? (
        <div className="flex items-center justify-center h-48 bg-gray-800/30 rounded-xl border border-dashed border-white/5">
          <p className="text-sm text-gray-600">No historical data available</p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="_time"
              tick={{ fill: "#6b7280", fontSize: 10 }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#6b7280", fontSize: 10 }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
            />
            <Tooltip
              content={<CustomTooltip activeSeries={activeSeries} />}
              cursor={{ stroke: "rgba(255,255,255,0.1)", strokeWidth: 1 }}
            />

            {/* Normal range reference lines for focused series */}
            {focusedSrs && (
              <>
                <ReferenceLine
                  y={focusedSrs.normalMin}
                  stroke={focusedSrs.color + "40"}
                  strokeDasharray="4 4"
                  label={{
                    value: `Low ${focusedSrs.normalMin}`,
                    fill: focusedSrs.color + "80",
                    fontSize: 9,
                  }}
                />
                <ReferenceLine
                  y={focusedSrs.normalMax}
                  stroke={focusedSrs.color + "40"}
                  strokeDasharray="4 4"
                  label={{
                    value: `High ${focusedSrs.normalMax}`,
                    fill: focusedSrs.color + "80",
                    fontSize: 9,
                  }}
                />
              </>
            )}

            {activeSrs.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={focusedSeries === s.key ? 2.5 : 1.5}
                dot={false}
                activeDot={{ r: 4, fill: s.color }}
                opacity={
                  focusedSeries && focusedSeries !== s.key ? 0.2 : 1
                }
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
