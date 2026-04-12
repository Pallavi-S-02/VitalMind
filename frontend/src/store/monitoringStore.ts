/**
 * monitoringStore.ts — Zustand store for real-time patient monitoring.
 *
 * Manages:
 *  - Socket.IO connection to the /monitoring namespace
 *  - Live vitals map (patient_id → latest vitals)
 *  - NEWS2 scores map (patient_id → score/risk)
 *  - Active monitoring alerts (unacknowledged)
 *  - Patient list from REST API
 */

import { create } from "zustand";
import { io, Socket } from "socket.io-client";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface PatientVitals {
  heart_rate?: number;
  spo2?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  temperature_c?: number;
  respiratory_rate?: number;
  blood_glucose_mgdl?: number;
  _timestamp?: string;
  _source?: string;
}

export interface News2Score {
  news2_score: number;
  risk_level: "Low" | "Low-Medium" | "Medium" | "High" | "Unknown";
  escalation_level: 0 | 1 | 2 | 3;
  component_scores?: Record<string, number>;
  recommended_action?: string;
}

export interface MonitoringAlert {
  id: string;
  patient_id: string;
  patient_name?: string;
  type: string;
  level: 1 | 2 | 3;
  severity: "MODERATE" | "HIGH" | "CRITICAL";
  message: string;
  news2_score: number;
  vitals_summary?: string;
  timestamp: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
}

export interface MonitoredPatient {
  id: string;
  name: string;
  room?: string;
  age?: number;
  diagnosis?: string;
  vitals?: PatientVitals;
  news2?: News2Score;
  last_alert?: MonitoringAlert;
  alert_count?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Store interface
// ─────────────────────────────────────────────────────────────────────────────

interface MonitoringState {
  // Connection
  socket: Socket | null;
  isConnected: boolean;
  connectionError: string | null;

  // Live data (keyed by patient_id)
  vitalsMap: Record<string, PatientVitals>;
  news2Map: Record<string, News2Score>;

  // Alerts
  activeAlerts: MonitoringAlert[];
  alertCount: number;

  // Patient roster
  patients: MonitoredPatient[];
  isLoadingPatients: boolean;

  // Actions
  connect: (token: string) => void;
  disconnect: () => void;
  joinPatientRoom: (patientId: string) => void;
  leavePatientRoom: (patientId: string) => void;
  acknowledgeAlert: (alertId: string, userId: string) => void;
  loadAlerts: (token: string, patientId?: string) => Promise<void>;
  loadPatients: (token: string) => Promise<void>;
  setPatientVitals: (patientId: string, vitals: PatientVitals) => void;
  setPatientNews2: (patientId: string, news2: News2Score) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Store implementation
// ─────────────────────────────────────────────────────────────────────────────

export const useMonitoringStore = create<MonitoringState>((set, get) => ({
  socket: null,
  isConnected: false,
  connectionError: null,
  vitalsMap: {},
  news2Map: {},
  activeAlerts: [],
  alertCount: 0,
  patients: [],
  isLoadingPatients: false,

  connect: (token: string) => {
    const { socket: existing } = get();
    if (existing) existing.disconnect();

    const wsUrl =
      process.env.NEXT_PUBLIC_WS_URL || "http://localhost:5000";

    const socket = io(`${wsUrl}/monitoring`, {
      path: "/socket.io",
      auth: { token },
      transports: ["websocket", "polling"],
    });

    socket.on("connect", () => {
      set({ isConnected: true, connectionError: null });
    });

    socket.on("disconnect", () => {
      set({ isConnected: false });
    });

    socket.on("connect_error", (err) => {
      set({
        connectionError: `Connection error: ${err.message}`,
        isConnected: false,
      });
    });

    socket.on("monitoring_connected", (data) => {
      console.log("[MonitoringStore] Connected to monitoring namespace", data);
    });

    // Real-time vitals update
    socket.on("vitals_update", (data: { patient_id: string; vitals: PatientVitals }) => {
      const { patient_id, vitals } = data;
      set((state) => ({
        vitalsMap: {
          ...state.vitalsMap,
          [patient_id]: { ...vitals, _timestamp: new Date().toISOString() },
        },
        // Update the patient roster entry
        patients: state.patients.map((p) =>
          p.id === patient_id
            ? { ...p, vitals: { ...vitals, _timestamp: new Date().toISOString() } }
            : p
        ),
      }));
    });

    // Real-time NEWS2 score update
    socket.on(
      "news2_update",
      (data: {
        patient_id: string;
        news2_score: number;
        risk_level: string;
        escalation_level: number;
      }) => {
        const { patient_id, news2_score, risk_level, escalation_level } = data;
        const news2: News2Score = {
          news2_score,
          risk_level: risk_level as News2Score["risk_level"],
          escalation_level: escalation_level as News2Score["escalation_level"],
        };
        set((state) => ({
          news2Map: { ...state.news2Map, [patient_id]: news2 },
          patients: state.patients.map((p) =>
            p.id === patient_id ? { ...p, news2 } : p
          ),
        }));
      }
    );

    // Monitoring alert (level 1–2)
    socket.on("monitoring_alert", (data: MonitoringAlert) => {
      set((state) => {
        const exists = state.activeAlerts.some((a) => a.id === data.id);
        if (exists) return {};
        return {
          activeAlerts: [data, ...state.activeAlerts].slice(0, 100),
          alertCount: state.alertCount + 1,
          patients: state.patients.map((p) =>
            p.id === data.patient_id
              ? {
                  ...p,
                  last_alert: data,
                  alert_count: (p.alert_count || 0) + 1,
                }
              : p
          ),
        };
      });
    });

    // Emergency alert (level 3)
    socket.on("emergency_alert", (data: MonitoringAlert) => {
      set((state) => {
        const exists = state.activeAlerts.some((a) => a.id === data.id);
        if (exists) return {};
        return {
          activeAlerts: [data, ...state.activeAlerts].slice(0, 100),
          alertCount: state.alertCount + 1,
          patients: state.patients.map((p) =>
            p.id === data.patient_id
              ? {
                  ...p,
                  last_alert: data,
                  alert_count: (p.alert_count || 0) + 1,
                }
              : p
          ),
        };
      });
    });

    // Alert acknowledged by someone else
    socket.on(
      "alert_acknowledged",
      (data: { alert_id: string; acknowledged_by: string }) => {
        set((state) => ({
          activeAlerts: state.activeAlerts.map((a) =>
            a.id === data.alert_id
              ? { ...a, acknowledged: true, acknowledged_by: data.acknowledged_by }
              : a
          ),
        }));
      }
    );

    set({ socket });
  },

  disconnect: () => {
    const { socket } = get();
    socket?.disconnect();
    set({ socket: null, isConnected: false });
  },

  joinPatientRoom: (patientId: string) => {
    const { socket } = get();
    socket?.emit("join_patient_room", { patient_id: patientId });
  },

  leavePatientRoom: (patientId: string) => {
    const { socket } = get();
    socket?.emit("leave_patient_room", { patient_id: patientId });
  },

  acknowledgeAlert: (alertId: string, userId: string) => {
    const { socket } = get();
    // Optimistic update
    set((state) => ({
      activeAlerts: state.activeAlerts.map((a) =>
        a.id === alertId
          ? { ...a, acknowledged: true, acknowledged_by: userId }
          : a
      ),
    }));
    // Send via socket for real-time broadcast
    socket?.emit("acknowledge_alert", {
      alert_id: alertId,
      acknowledged_by: userId,
    });
  },

  loadAlerts: async (token: string, patientId?: string) => {
    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
      const url = new URL(`${apiUrl}/api/v1/monitoring/alerts`);
      if (patientId) url.searchParams.set("patient_id", patientId);
      url.searchParams.set("acknowledged", "false");
      url.searchParams.set("limit", "50");

      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;

      const data = await res.json();
      set({
        activeAlerts: data.alerts || [],
        alertCount: (data.alerts || []).length,
      });
    } catch (err) {
      console.error("[MonitoringStore] Failed to load alerts:", err);
    }
  },

  loadPatients: async (token: string) => {
    set({ isLoadingPatients: true });
    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
      // Use the patients endpoint to get the list
      const res = await fetch(`${apiUrl}/api/v1/patients`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        set({ isLoadingPatients: false });
        return;
      }
      const data = await res.json();
      const patients: MonitoredPatient[] = (data.patients || data || []).map(
        (p: Record<string, unknown>) => ({
          id: String(p.id || p.user_id || ""),
          name: String(p.name || p.full_name || "Unknown Patient"),
          room: String(p.room || ""),
          age: Number(p.age) || undefined,
          diagnosis: String(p.primary_diagnosis || ""),
          vitals: undefined,
          news2: undefined,
          last_alert: undefined,
          alert_count: 0,
        })
      );
      set({ patients, isLoadingPatients: false });
    } catch (err) {
      console.error("[MonitoringStore] Failed to load patients:", err);
      set({ isLoadingPatients: false });
    }
  },

  setPatientVitals: (patientId: string, vitals: PatientVitals) => {
    set((state) => ({
      vitalsMap: { ...state.vitalsMap, [patientId]: vitals },
      patients: state.patients.map((p) =>
        p.id === patientId ? { ...p, vitals } : p
      ),
    }));
  },

  setPatientNews2: (patientId: string, news2: News2Score) => {
    set((state) => ({
      news2Map: { ...state.news2Map, [patientId]: news2 },
      patients: state.patients.map((p) =>
        p.id === patientId ? { ...p, news2 } : p
      ),
    }));
  },
}));
