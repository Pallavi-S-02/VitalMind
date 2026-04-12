"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  Calendar, Clock, ChevronLeft, ChevronRight, Video,
  MapPin, PhoneCall, Loader2, CheckCircle2, User
} from "lucide-react";
import {
  format, addDays, subDays, startOfDay, isSameDay,
  parseISO, isAfter
} from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Doctor {
  id: string;
  first_name: string;
  last_name: string;
  specialization?: string;
  avatar_url?: string;
}

interface Slot {
  start: string;
  end: string;
  available: boolean;
}

const APPOINTMENT_TYPES = [
  { value: "in-person", label: "In-person", icon: <MapPin className="w-4 h-4" /> },
  { value: "video", label: "Video call", icon: <Video className="w-4 h-4" /> },
  { value: "voice", label: "Phone call", icon: <PhoneCall className="w-4 h-4" /> },
];

export default function BookAppointmentPage() {
  const { data: session } = useSession();
  const router = useRouter();

  // Step state: "doctor" → "slot" → "confirm" → "done"
  const [step, setStep] = useState<"doctor" | "slot" | "confirm" | "done">("doctor");

  // Doctor selection
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [selectedDoctor, setSelectedDoctor] = useState<Doctor | null>(null);
  const [doctorsLoading, setDoctorsLoading] = useState(true);

  // Slot selection
  const [selectedDate, setSelectedDate] = useState(startOfDay(new Date()));
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);

  // Form data
  const [apptType, setApptType] = useState("in-person");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [bookedId, setBookedId] = useState<string | null>(null);

  // ── Load doctors ─────────────────────────────────────────────
  useEffect(() => {
    if (!session?.accessToken) return;
    fetch(`${API}/api/v1/doctors/`, {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setDoctors(Array.isArray(data) ? data : data.doctors || []);
      })
      .catch(console.error)
      .finally(() => setDoctorsLoading(false));
  }, [session]);

  // ── Load availability when doctor or date changes ─────────────
  const loadSlots = useCallback(async () => {
    if (!selectedDoctor || !session?.accessToken) return;
    setSlotsLoading(true);
    setSelectedSlot(null);
    try {
      const dateStr = format(selectedDate, "yyyy-MM-dd");
      const res = await fetch(
        `${API}/api/v1/appointments/availability/${selectedDoctor.id}/${dateStr}`,
        { headers: { Authorization: `Bearer ${session.accessToken}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setSlots(data.slots || []);
      }
    } catch (err) { console.error(err); }
    finally { setSlotsLoading(false); }
  }, [selectedDoctor, selectedDate, session]);

  useEffect(() => {
    if (step === "slot") loadSlots();
  }, [step, loadSlots]);

  // ── Book appointment ──────────────────────────────────────────
  const handleBook = async () => {
    if (!selectedDoctor || !selectedSlot || !session?.accessToken || !session?.user?.id) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API}/api/v1/appointments/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          patient_id: session.user.id,
          doctor_id: selectedDoctor.id,
          start_time: selectedSlot.start,
          end_time: selectedSlot.end,
          type: apptType,
          reason,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setBookedId(data.appointment?.id);
        setStep("done");
      } else {
        const err = await res.json();
        alert(err.message || "Booking failed. Please try a different slot.");
      }
    } catch (err) { console.error(err); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <button
          onClick={() => {
            if (step === "slot") setStep("doctor");
            else if (step === "confirm") setStep("slot");
            else router.push("/patient/appointments");
          }}
          className="p-2 rounded-full hover:bg-gray-100 transition-colors"
        >
          <ChevronLeft className="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Book Appointment</h1>
          <div className="flex items-center gap-2 mt-1.5">
            {["doctor", "slot", "confirm"].map((s, i) => (
              <React.Fragment key={s}>
                <div className={`flex items-center gap-1.5 text-xs font-medium ${
                  step === s ? "text-indigo-600" :
                  ["doctor", "slot", "confirm"].indexOf(step) > i ? "text-emerald-600" : "text-gray-400"
                }`}>
                  <div className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                    step === s ? "bg-indigo-600 text-white" :
                    ["doctor", "slot", "confirm"].indexOf(step) > i ? "bg-emerald-500 text-white" : "bg-gray-200 text-gray-500"
                  }`}>
                    {["doctor", "slot", "confirm"].indexOf(step) > i ? "✓" : i + 1}
                  </div>
                  {{ "doctor": "Choose Doctor", "slot": "Pick a Slot", "confirm": "Confirm" }[s]}
                </div>
                {i < 2 && <div className="flex-1 h-px bg-gray-200 max-w-8" />}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      {/* ── Step 1: Choose Doctor ── */}
      {step === "doctor" && (
        <div className="space-y-3">
          {doctorsLoading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-7 h-7 animate-spin text-indigo-400" /></div>
          ) : doctors.length === 0 ? (
            <p className="text-gray-500 text-center py-12">No doctors available</p>
          ) : (
            doctors.map((doc) => (
              <button
                key={doc.id}
                onClick={() => { setSelectedDoctor(doc); setStep("slot"); }}
                className="w-full flex items-center gap-4 p-4 bg-white border border-gray-100 rounded-2xl hover:border-indigo-200 hover:shadow-sm transition-all text-left group"
              >
                <div className="h-12 w-12 rounded-full bg-indigo-50 flex items-center justify-center flex-shrink-0">
                  <User className="w-6 h-6 text-indigo-400" />
                </div>
                <div className="flex-1">
                  <div className="font-semibold text-gray-900">Dr. {doc.first_name} {doc.last_name}</div>
                  {doc.specialization && <div className="text-sm text-gray-500">{doc.specialization}</div>}
                </div>
                <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-indigo-500 transition-colors" />
              </button>
            ))
          )}
        </div>
      )}

      {/* ── Step 2: Pick Slot ── */}
      {step === "slot" && selectedDoctor && (
        <div className="space-y-6">
          {/* Date navigator */}
          <div className="bg-white border border-gray-100 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={() => setSelectedDate((d) => subDays(d, 1))}
                disabled={isSameDay(selectedDate, startOfDay(new Date()))}
                className="p-2 rounded-full hover:bg-gray-100 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <div className="text-center">
                <div className="font-semibold text-gray-900">{format(selectedDate, "EEEE, MMMM d")}</div>
                {isSameDay(selectedDate, new Date()) && (
                  <span className="text-xs text-indigo-600 font-medium">Today</span>
                )}
              </div>
              <button
                onClick={() => setSelectedDate((d) => addDays(d, 1))}
                className="p-2 rounded-full hover:bg-gray-100 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Quick day pills */}
            <div className="flex gap-2 overflow-x-auto pb-1">
              {Array.from({ length: 7 }).map((_, i) => {
                const d = addDays(startOfDay(new Date()), i);
                const isSelected = isSameDay(d, selectedDate);
                return (
                  <button
                    key={i}
                    onClick={() => setSelectedDate(d)}
                    className={`flex-shrink-0 flex flex-col items-center px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                      isSelected
                        ? "bg-indigo-600 text-white"
                        : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    <span>{format(d, "EEE")}</span>
                    <span className="text-base font-bold mt-0.5">{format(d, "d")}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Time slots */}
          {slotsLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-indigo-400" /></div>
          ) : (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                Available Times with Dr. {selectedDoctor.first_name} {selectedDoctor.last_name}
              </p>
              <div className="grid grid-cols-4 gap-2">
                {slots.map((slot, i) => {
                  const start = parseISO(slot.start);
                  const inPast = !isAfter(start, new Date());
                  const disabled = !slot.available || inPast;
                  const isSelected = selectedSlot?.start === slot.start;
                  return (
                    <button
                      key={i}
                      onClick={() => !disabled && setSelectedSlot(slot)}
                      disabled={disabled}
                      className={`py-2.5 px-3 rounded-xl text-sm font-medium transition-all border ${
                        isSelected
                          ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                          : disabled
                          ? "bg-gray-50 text-gray-300 border-gray-100 cursor-not-allowed"
                          : "bg-white text-gray-700 border-gray-200 hover:border-indigo-300 hover:bg-indigo-50"
                      }`}
                    >
                      {format(start, "h:mm a")}
                    </button>
                  );
                })}
              </div>
              {slots.every((s) => !s.available || !isAfter(parseISO(s.start), new Date())) && (
                <p className="text-center text-gray-400 text-sm mt-6">No available slots on this date</p>
              )}
            </div>
          )}

          {selectedSlot && (
            <button
              onClick={() => setStep("confirm")}
              className="w-full py-3 bg-indigo-600 text-white font-semibold rounded-2xl hover:bg-indigo-700 transition-colors shadow-sm"
            >
              Continue →
            </button>
          )}
        </div>
      )}

      {/* ── Step 3: Confirm ── */}
      {step === "confirm" && selectedDoctor && selectedSlot && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-100 rounded-2xl p-6 space-y-4">
            <h3 className="font-semibold text-gray-900">Appointment Summary</h3>

            <div className="flex items-center gap-3 p-4 bg-indigo-50 rounded-xl">
              <User className="w-8 h-8 text-indigo-400" />
              <div>
                <div className="font-semibold text-gray-900">Dr. {selectedDoctor.first_name} {selectedDoctor.last_name}</div>
                {selectedDoctor.specialization && <div className="text-sm text-gray-500">{selectedDoctor.specialization}</div>}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-xl">
                <Calendar className="w-4 h-4 text-gray-400" />
                <div>
                  <div className="text-xs text-gray-400">Date</div>
                  <div className="text-sm font-medium text-gray-900">
                    {format(parseISO(selectedSlot.start), "EEE, MMM d")}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-xl">
                <Clock className="w-4 h-4 text-gray-400" />
                <div>
                  <div className="text-xs text-gray-400">Time</div>
                  <div className="text-sm font-medium text-gray-900">
                    {format(parseISO(selectedSlot.start), "h:mm a")}
                  </div>
                </div>
              </div>
            </div>

            {/* Appointment type */}
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-gray-400 block mb-2">
                Appointment Type
              </label>
              <div className="flex gap-2">
                {APPOINTMENT_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setApptType(t.value)}
                    className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium border transition-all ${
                      apptType === t.value
                        ? "bg-indigo-600 text-white border-indigo-600"
                        : "bg-gray-50 text-gray-600 border-gray-200 hover:border-indigo-200"
                    }`}
                  >
                    {t.icon} {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Reason */}
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-gray-400 block mb-2">
                Reason for Visit
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Briefly describe why you're booking this appointment..."
                className="w-full border border-gray-200 rounded-xl p-3 text-sm text-gray-800 focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-50 resize-none transition-all"
                rows={3}
              />
            </div>
          </div>

          <button
            onClick={handleBook}
            disabled={submitting}
            className="w-full py-3.5 bg-indigo-600 text-white font-bold rounded-2xl hover:bg-indigo-700 transition-colors shadow-md disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {submitting ? <Loader2 className="w-5 h-5 animate-spin" /> : null}
            {submitting ? "Booking…" : "Confirm Appointment"}
          </button>
        </div>
      )}

      {/* ── Step 4: Done ── */}
      {step === "done" && (
        <div className="flex flex-col items-center gap-6 py-16 text-center">
          <div className="h-20 w-20 bg-emerald-100 rounded-full flex items-center justify-center">
            <CheckCircle2 className="w-10 h-10 text-emerald-500" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">You're booked!</h2>
            <p className="text-gray-500 mt-2">
              Your appointment has been confirmed. A confirmation email has been sent to your registered email address. You'll also receive a reminder before it starts.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => router.push("/patient/appointments")}
              className="px-5 py-2.5 bg-indigo-600 text-white font-semibold rounded-full hover:bg-indigo-700 transition-colors"
            >
              View Appointments
            </button>
            <button
              onClick={() => { setStep("doctor"); setSelectedDoctor(null); setSelectedSlot(null); setReason(""); }}
              className="px-5 py-2.5 bg-gray-100 text-gray-700 font-medium rounded-full hover:bg-gray-200 transition-colors"
            >
              Book Another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
