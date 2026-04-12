"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Video, Calendar, Clock, ArrowRight, User } from "lucide-react";
import Link from "next/link";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  start_time: string;
  end_time: string;
  type: string;
  status: string;
  reason: string;
  patient_name?: string;
}

export default function DoctorTelemedicinePage() {
  const { data: session } = useSession();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session?.user?.id && session?.accessToken) {
      fetchTelemedicineAppointments();
    }
  }, [session]);

  const fetchTelemedicineAppointments = async () => {
    try {
      setIsLoading(true);
      // Fetch all appointments for the doctor
      const res = await fetch(`${API}/api/v1/appointments/doctor/${session?.user?.id}`, {
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (!res.ok) {
        throw new Error("Failed to fetch appointments");
      }

      const data = await res.json();
      const allAppts = Array.isArray(data) ? data : [];
      
      // Filter for telemedicine and not cancelled
      const activeTelemedicine = allAppts.filter(
        (a: Appointment) => a.type === "telemedicine" && a.status !== "cancelled"
      );
      
      setAppointments(activeTelemedicine);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">Telemedicine Lobby</h1>
          <p className="text-gray-500 mt-1">
            Manage and launch your upcoming virtual consultations.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2].map((i) => (
            <div key={i} className="h-40 bg-gray-100 animate-pulse rounded-2xl border border-gray-100" />
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-50 p-6 rounded-2xl border border-red-100 text-red-600">
          <p className="font-semibold">Error Loading Sessions</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      ) : appointments.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-dashed border-gray-200">
          <div className="bg-blue-50 p-4 rounded-full mb-4">
            <Video className="h-10 w-10 text-blue-500" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900">No Telemedicine Sessions</h3>
          <p className="text-gray-500 mt-1 max-w-sm text-center">
            You don't have any upcoming video consultations scheduled at the moment.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {appointments.map((appt) => {
            const startDate = new Date(appt.start_time);
            return (
              <div 
                key={appt.id} 
                className="flex flex-col p-6 bg-white rounded-2xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden"
              >
                {appt.status === 'scheduled' && (
                  <div className="absolute top-0 right-0 py-1.5 px-4 bg-green-50 text-green-700 text-xs font-bold rounded-bl-xl border-b border-l border-green-100">
                    UPCOMING
                  </div>
                )}
                
                <h3 className="text-lg font-bold text-gray-900 pr-16">
                  {appt.reason || "General Consultation"}
                </h3>
                
                <div className="mt-4 space-y-2">
                  <div className="flex items-center text-sm text-gray-600">
                    <User className="h-4 w-4 mr-2 text-gray-400" />
                    Patient ID: {appt.patient_id.substring(0, 8)}...
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <Calendar className="h-4 w-4 mr-2 text-gray-400" />
                    {format(startDate, "MMM d, yyyy")}
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <Clock className="h-4 w-4 mr-2 text-gray-400" />
                    {format(startDate, "h:mm a")}
                  </div>
                </div>
                
                <div className="mt-6 pt-4 border-t border-gray-100">
                  <Link
                    href={`/doctor/telemedicine/${appt.id}`}
                    className="flex w-full items-center justify-center py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-colors"
                  >
                    <Video className="w-4 h-4 mr-2" />
                    Launch Virtual Room
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
