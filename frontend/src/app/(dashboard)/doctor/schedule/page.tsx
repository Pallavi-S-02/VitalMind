"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  ChevronLeft, ChevronRight, Video, MapPin, PhoneCall,
  Loader2, Clock, User, CheckCircle2, XCircle,
  AlertCircle, Calendar
} from "lucide-react";
import {
  format, addDays, subDays, startOfWeek, endOfWeek,
  startOfDay, isSameDay, parseISO, isToday, addWeeks, subWeeks
} from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  start_time: string;
  end_time: string;
  status: string;
  type: string;
  reason: string | null;
  meeting_link: string | null;
}

const STATUS_BADGE: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-700",
  confirmed: "bg-emerald-100 text-emerald-700",
  completed: "bg-gray-100 text-gray-500",
  cancelled: "bg-red-100 text-red-600",
  "no-show": "bg-amber-100 text-amber-700",
};

const TYPE_ICON: Record<string, React.ReactNode> = {
  video: <Video className="w-3.5 h-3.5" />,
  voice: <PhoneCall className="w-3.5 h-3.5" />,
  "in-person": <MapPin className="w-3.5 h-3.5" />,
};

export default function DoctorSchedulePage() {
  const { data: session } = useSession();
  const router = useRouter();

  const [weekStart, setWeekStart] = useState(startOfWeek(new Date(), { weekStartsOn: 1 })); // Mon
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAppt, setSelectedAppt] = useState<Appointment | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const weekDays = Array.from({ length: 7 }).map((_, i) => addDays(weekStart, i));

  const fetchAppointments = useCallback(async () => {
    if (!session?.accessToken || !session?.user?.id) return;
    setLoading(true);
    try {
      const res = await fetch(
        `${API}/api/v1/appointments/doctor/${session.user.id}?limit=100`,
        { headers: { Authorization: `Bearer ${session.accessToken}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setAppointments(Array.isArray(data) ? data : []);
      }
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [session]);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);

  const apptsByDay = (day: Date) =>
    appointments.filter((a) => isSameDay(parseISO(a.start_time), day));

  const handleStatusUpdate = async (apptId: string, status: string) => {
    setUpdatingId(apptId);
    try {
      const res = await fetch(`${API}/api/v1/appointments/${apptId}/status`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status }),
      });
      if (res.ok) {
        await fetchAppointments();
        setSelectedAppt(null);
      }
    } catch (err) { console.error(err); }
    finally { setUpdatingId(null); }
  };

  const handleStartVideo = (appt: Appointment) => {
    router.push(`/doctor/telemedicine/${appt.id}`);
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] bg-gray-50 rounded-2xl overflow-hidden">

      {/* ── Calendar Main ── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Calendar Header */}
        <div className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-indigo-500" />
              My Schedule
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {format(weekStart, "MMMM d")} – {format(endOfWeek(weekStart, { weekStartsOn: 1 }), "MMMM d, yyyy")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setWeekStart((w) => subWeeks(w, 1))}
              className="p-2 rounded-full hover:bg-gray-100 transition-colors"
            >
              <ChevronLeft className="w-4 h-4 text-gray-600" />
            </button>
            <button
              onClick={() => setWeekStart(startOfWeek(new Date(), { weekStartsOn: 1 }))}
              className="px-3 py-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors"
            >
              Today
            </button>
            <button
              onClick={() => setWeekStart((w) => addWeeks(w, 1))}
              className="p-2 rounded-full hover:bg-gray-100 transition-colors"
            >
              <ChevronRight className="w-4 h-4 text-gray-600" />
            </button>
          </div>
        </div>

        {/* Day columns */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          </div>
        ) : (
          <div className="flex-1 overflow-auto">
            <div className="grid grid-cols-7 divide-x divide-gray-100 min-h-full">
              {weekDays.map((day) => {
                const dayAppts = apptsByDay(day);
                const isCurrentDay = isToday(day);
                return (
                  <div key={day.toISOString()} className="flex flex-col">
                    {/* Day header */}
                    <div className={`sticky top-0 z-10 px-2 py-3 text-center border-b border-gray-100 ${isCurrentDay ? "bg-indigo-50" : "bg-white"}`}>
                      <div className={`text-xs font-semibold uppercase tracking-wider ${isCurrentDay ? "text-indigo-600" : "text-gray-400"}`}>
                        {format(day, "EEE")}
                      </div>
                      <div className={`text-xl font-bold mt-0.5 w-8 h-8 mx-auto rounded-full flex items-center justify-center ${
                        isCurrentDay ? "bg-indigo-600 text-white" : "text-gray-900"
                      }`}>
                        {format(day, "d")}
                      </div>
                    </div>

                    {/* Appointments */}
                    <div className="flex-1 p-2 space-y-1.5">
                      {dayAppts.length === 0 ? (
                        <div className="py-8 text-center text-xs text-gray-300 select-none">—</div>
                      ) : (
                        dayAppts.map((appt) => (
                          <button
                            key={appt.id}
                            onClick={() => setSelectedAppt(appt)}
                            className={`w-full text-left p-2.5 rounded-xl border transition-all hover:shadow-sm ${
                              selectedAppt?.id === appt.id
                                ? "border-indigo-300 bg-indigo-50 shadow-sm"
                                : "border-gray-100 bg-white"
                            } ${appt.status === "cancelled" ? "opacity-40" : ""}`}
                          >
                            <div className="flex items-center gap-1.5 mb-1">
                              <span className="text-gray-400">{TYPE_ICON[appt.type] || TYPE_ICON["in-person"]}</span>
                              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${STATUS_BADGE[appt.status] || STATUS_BADGE.scheduled}`}>
                                {appt.status}
                              </span>
                            </div>
                            <div className="text-xs font-semibold text-gray-900 leading-tight">
                              {format(parseISO(appt.start_time), "h:mm a")}
                            </div>
                            {appt.reason && (
                              <div className="text-[11px] text-gray-400 mt-0.5 truncate">{appt.reason}</div>
                            )}
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Detail Panel ── */}
      <div className="w-80 flex-shrink-0 bg-white border-l border-gray-100 flex flex-col">
        {selectedAppt ? (
          <>
            <div className="p-5 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Appointment Details</h2>
              <button onClick={() => setSelectedAppt(null)} className="p-1 hover:bg-gray-100 rounded-full transition-colors">
                <XCircle className="w-4 h-4 text-gray-400" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* Type + Time */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-gray-600 text-sm">
                  {TYPE_ICON[selectedAppt.type]}
                  <span className="capitalize font-medium">{selectedAppt.type} Consultation</span>
                </div>
                <div className="flex items-center gap-2 text-gray-600 text-sm">
                  <Clock className="w-3.5 h-3.5 text-gray-400" />
                  <span>{format(parseISO(selectedAppt.start_time), "EEE, MMM d · h:mm a")}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${STATUS_BADGE[selectedAppt.status] || ""}`}>
                    {selectedAppt.status === "completed" && <CheckCircle2 className="w-3 h-3" />}
                    {selectedAppt.status === "cancelled" && <XCircle className="w-3 h-3" />}
                    {selectedAppt.status === "no-show" && <AlertCircle className="w-3 h-3" />}
                    {selectedAppt.status.replace("-", " ")}
                  </span>
                </div>
              </div>

              {selectedAppt.reason && (
                <div className="bg-gray-50 rounded-xl p-3">
                  <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Reason</div>
                  <p className="text-sm text-gray-700">{selectedAppt.reason}</p>
                </div>
              )}

              <div className="bg-gray-50 rounded-xl p-3">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Patient ID</div>
                <div className="font-mono text-xs text-gray-600 truncate">{selectedAppt.patient_id}</div>
              </div>
            </div>

            {/* Actions */}
            {selectedAppt.status !== "cancelled" && selectedAppt.status !== "completed" && (
              <div className="p-4 border-t border-gray-100 space-y-2">
                {selectedAppt.type === "video" && (
                  <button
                    onClick={() => handleStartVideo(selectedAppt)}
                    className="w-full flex items-center justify-center gap-2 py-2.5 bg-cyan-600 text-white text-sm font-semibold rounded-xl hover:bg-cyan-700 transition-colors"
                  >
                    <Video className="w-4 h-4" /> Start Video Call
                  </button>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleStatusUpdate(selectedAppt.id, "completed")}
                    disabled={!!updatingId}
                    className="flex items-center justify-center gap-1.5 py-2 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-xl hover:bg-emerald-100 transition-colors disabled:opacity-50"
                  >
                    {updatingId === selectedAppt.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                    Complete
                  </button>
                  <button
                    onClick={() => handleStatusUpdate(selectedAppt.id, "no-show")}
                    disabled={!!updatingId}
                    className="flex items-center justify-center gap-1.5 py-2 bg-amber-50 text-amber-700 text-xs font-semibold rounded-xl hover:bg-amber-100 transition-colors disabled:opacity-50"
                  >
                    <AlertCircle className="w-3.5 h-3.5" /> No Show
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-8">
            <div className="h-14 w-14 bg-gray-100 rounded-full flex items-center justify-center">
              <Calendar className="w-7 h-7 text-gray-300" />
            </div>
            <div>
              <p className="font-medium text-gray-500 text-sm">Select an appointment</p>
              <p className="text-gray-400 text-xs mt-1">Click any event to view details and take actions</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
