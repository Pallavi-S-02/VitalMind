"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { Pill, Calendar, Clock, ArrowLeft, Loader2, Info } from "lucide-react";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Prescription {
  id: string;
  medication_name: string;
  dosage: string;
  frequency: string;
  route: string | null;
  start_date: string;
  end_date: string | null;
  instructions: string | null;
  status: string;
}

export default function PatientPrescriptionsPage() {
  const { data: session } = useSession();
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (session?.user?.id && session?.accessToken) {
      fetchPrescriptions();
    }
  }, [session]);

  const fetchPrescriptions = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API}/api/v1/medications/prescriptions/patient/${session?.user?.id}`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
        cache: "no-store",
      });

      if (!res.ok) throw new Error("Failed to fetch prescriptions");

      const data = await res.json();
      setPrescriptions(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500 pb-20">
      <div className="flex flex-col space-y-4">
        <Link
          href="/patient/dashboard"
          className="inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors w-fit"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Dashboard
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 font-outfit">Active Prescriptions</h1>
          <p className="text-gray-500 mt-1">
            View your doctor-prescribed medications and dosage instructions.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-24 bg-white rounded-3xl border border-gray-100 shadow-sm">
          <Loader2 className="h-10 w-10 text-rose-500 animate-spin mb-4" />
          <p className="text-gray-500 font-medium">Loading your prescriptions...</p>
        </div>
      ) : prescriptions.length === 0 ? (
        <div className="bg-white rounded-3xl border border-gray-100 p-16 text-center shadow-sm">
          <div className="mx-auto w-16 h-16 bg-rose-50 rounded-2xl flex items-center justify-center mb-6">
            <Pill className="h-8 w-8 text-rose-500" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 font-outfit">No active prescriptions</h2>
          <p className="text-gray-500 mt-2 max-w-sm mx-auto">
            You don't have any formal prescriptions on file yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {prescriptions.map((px) => (
            <div
              key={px.id}
              className="group bg-white rounded-3xl border border-gray-100 p-8 shadow-sm hover:shadow-xl hover:border-rose-100 transition-all duration-500"
            >
              <div className="flex justify-between items-start mb-6">
                <div className="flex items-center space-x-5">
                  <div className="p-4 bg-rose-50 rounded-2xl text-rose-600 group-hover:bg-rose-600 group-hover:text-white transition-all duration-500">
                    <Pill className="h-7 w-7" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900 font-outfit group-hover:text-rose-700 transition-colors">
                      {px.medication_name}
                    </h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                        px.status === "active" ? "bg-green-100 text-green-700" :
                        px.status === "completed" ? "bg-blue-100 text-blue-700" :
                        "bg-gray-100 text-gray-700"
                      }`}>
                        {px.status.charAt(0).toUpperCase() + px.status.slice(1)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gray-50/80 rounded-2xl p-5 border border-gray-100/50 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 block mb-1">
                      Dosage
                    </span>
                    <span className="text-sm font-semibold text-gray-800">{px.dosage} ({px.route || "oral"})</span>
                  </div>
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 block mb-1">
                      Frequency
                    </span>
                    <span className="flex items-center text-sm font-semibold text-gray-800">
                      <Clock className="h-3 w-3 mr-1.5 text-rose-500" />
                      {px.frequency}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 block mb-1">
                      Start Date
                    </span>
                    <span className="flex items-center text-sm text-gray-600">
                      <Calendar className="h-3 w-3 mr-1.5" />
                      {px.start_date ? format(new Date(px.start_date), "MMM dd, yyyy") : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 block mb-1">
                      End Date
                    </span>
                    <span className="flex items-center text-sm text-gray-600">
                      <Calendar className="h-3 w-3 mr-1.5" />
                      {px.end_date ? format(new Date(px.end_date), "MMM dd, yyyy") : "Ongoing"}
                    </span>
                  </div>
                </div>

                {px.instructions && (
                  <div className="pt-4 border-t border-gray-200">
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 block mb-1">
                      Doctor's Instructions
                    </span>
                    <div className="flex items-start bg-rose-50/50 p-3 rounded-xl border border-rose-100/50">
                      <Info className="h-4 w-4 text-rose-500 mr-2 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-gray-700 leading-relaxed italic">
                        "{px.instructions}"
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
