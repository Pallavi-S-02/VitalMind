"use client";

import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  Calendar, Clock, Video, MapPin, Plus, CheckCircle2,
  XCircle, AlertCircle, Loader2, ChevronRight, PhoneCall
} from "lucide-react";
import { format, isPast, isToday, parseISO } from "date-fns";

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
  notes: string | null;
  meeting_link: string | null;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  scheduled: { label: "Scheduled", color: "bg-blue-50 text-blue-700 border-blue-100", icon: <Clock className="w-3 h-3" /> },
  confirmed: { label: "Confirmed", color: "bg-emerald-50 text-emerald-700 border-emerald-100", icon: <CheckCircle2 className="w-3 h-3" /> },
  completed: { label: "Completed", color: "bg-gray-100 text-gray-500 border-gray-200", icon: <CheckCircle2 className="w-3 h-3" /> },
  cancelled: { label: "Cancelled", color: "bg-red-50 text-red-600 border-red-100", icon: <XCircle className="w-3 h-3" /> },
  "no-show": { label: "No Show", color: "bg-amber-50 text-amber-700 border-amber-100", icon: <AlertCircle className="w-3 h-3" /> },
};

const TYPE_ICON: Record<string, React.ReactNode> = {
  video: <Video className="w-4 h-4 text-cyan-500" />,
  voice: <PhoneCall className="w-4 h-4 text-purple-500" />,
  "in-person": <MapPin className="w-4 h-4 text-indigo-400" />,
};

export default function PatientAppointmentsPage() {
  const { data: session } = useSession();
  const router = useRouter();

  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const fetchAppointments = async () => {
    if (!session?.accessToken || !session?.user?.id) return;
    try {
      const res = await fetch(`${API}/api/v1/appointments/patient/${session.user.id}`, {
        headers: { Authorization: `Bearer ${session.accessToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAppointments(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAppointments(); }, [session]);

  const handleCancel = async (id: string) => {
    if (!confirm("Cancel this appointment?")) return;
    setCancellingId(id);
    try {
      const res = await fetch(`${API}/api/v1/appointments/${id}/cancel`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason: "Cancelled by patient" }),
      });
      if (res.ok) await fetchAppointments();
    } catch (err) { console.error(err); }
    finally { setCancellingId(null); }
  };

  const handleJoinVideo = (appt: Appointment) => {
    router.push(`/patient/telemedicine/${appt.id}`);
  };

  const upcoming = appointments.filter(
    (a) => !isPast(parseISO(a.start_time)) && a.status !== "cancelled"
  );
  const past = appointments.filter(
    (a) => isPast(parseISO(a.start_time)) || a.status === "cancelled"
  );

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Appointments</h1>
          <p className="text-sm text-gray-500 mt-1">
            {upcoming.length} upcoming · {past.length} past
          </p>
        </div>
        <button
          onClick={() => router.push("/patient/appointments/book")}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-full hover:bg-indigo-700 transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Book Appointment
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
        </div>
      ) : (
        <>
          {/* Upcoming */}
          <section className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400 px-1">Upcoming</h2>
            {upcoming.length === 0 ? (
              <div className="bg-gray-50 border border-gray-100 rounded-2xl p-8 text-center">
                <Calendar className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 font-medium">No upcoming appointments</p>
                <button
                  onClick={() => router.push("/patient/appointments/book")}
                  className="mt-4 text-sm text-indigo-600 hover:underline font-medium"
                >
                  Book one now →
                </button>
              </div>
            ) : (
              upcoming.map((appt) => (
                <AppointmentCard
                  key={appt.id}
                  appt={appt}
                  onCancel={() => handleCancel(appt.id)}
                  onJoin={() => handleJoinVideo(appt)}
                  cancelling={cancellingId === appt.id}
                />
              ))
            )}
          </section>

          {/* Past */}
          {past.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400 px-1">Past & Cancelled</h2>
              {past.slice(0, 5).map((appt) => (
                <AppointmentCard key={appt.id} appt={appt} past />
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}

function AppointmentCard({
  appt, onCancel, onJoin, cancelling = false, past = false,
}: {
  appt: Appointment;
  onCancel?: () => void;
  onJoin?: () => void;
  cancelling?: boolean;
  past?: boolean;
}) {
  const status = STATUS_CONFIG[appt.status] || STATUS_CONFIG.scheduled;
  const startDt = parseISO(appt.start_time);
  const isVideoAppt = appt.type === "video";
  const canJoin = isVideoAppt && appt.status !== "cancelled" && !isPast(parseISO(appt.end_time));
  const isStartingToday = isToday(startDt);

  return (
    <div className={`bg-white border rounded-2xl p-5 flex items-start gap-5 transition-all hover:shadow-sm ${past ? "opacity-60" : ""}`}>
      {/* Date badge */}
      <div className="flex-shrink-0 w-14 text-center">
        <div className={`rounded-xl py-2 ${isStartingToday ? "bg-indigo-600 text-white" : "bg-gray-50 text-gray-700"}`}>
          <div className="text-xs font-medium">{format(startDt, "MMM")}</div>
          <div className="text-xl font-bold leading-none">{format(startDt, "d")}</div>
          <div className="text-xs">{format(startDt, "EEE")}</div>
        </div>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          {TYPE_ICON[appt.type] || TYPE_ICON["in-person"]}
          <span className="font-semibold text-gray-900 text-sm capitalize">{appt.type} Consultation</span>
          <span className={`ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${status.color}`}>
            {status.icon} {status.label}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-gray-500 text-sm">
          <Clock className="w-3.5 h-3.5" />
          {format(startDt, "hh:mm a")} – {format(parseISO(appt.end_time), "hh:mm a")}
        </div>
        {appt.reason && (
          <p className="text-gray-400 text-xs mt-1.5 truncate">{appt.reason}</p>
        )}
      </div>

      {/* Actions */}
      {!past && (
        <div className="flex items-center gap-2 flex-shrink-0">
          {canJoin && (
            <button
              onClick={onJoin}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-600 text-white text-xs font-semibold rounded-lg hover:bg-cyan-700 transition-colors"
            >
              <Video className="w-3.5 h-3.5" /> Join
            </button>
          )}
          {appt.status === "scheduled" && (
            <button
              onClick={onCancel}
              disabled={cancelling}
              className="flex items-center gap-1 px-3 py-1.5 border border-red-200 text-red-500 text-xs font-medium rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              {cancelling ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
              Cancel
            </button>
          )}
        </div>
      )}
    </div>
  );
}
