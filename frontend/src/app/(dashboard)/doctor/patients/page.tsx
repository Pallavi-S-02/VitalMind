"use client";

import { useEffect, useState } from "react";
import { Users, Search, ArrowRight, Activity, Calendar } from "lucide-react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Patient {
  id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  date_of_birth: string;
  gender: string;
  blood_type: string;
}

export default function DoctorPatientsPage() {
  const { data: session } = useSession();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session?.accessToken) {
      fetchPatients();
    }
  }, [session]);

  const fetchPatients = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API}/api/v1/patients/`, {
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (!res.ok) {
        throw new Error("Failed to fetch patients");
      }

      const data = await res.json();
      // Ensure data is array
      setPatients(Array.isArray(data) ? data : data.patients || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">My Patients</h1>
          <p className="text-muted-foreground mt-1 text-gray-500">
            View and manage your patient profiles and medical records.
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-4 bg-white p-4 rounded-xl shadow-sm border border-gray-100">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search patients by name, email, or ID..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-48 bg-gray-100 animate-pulse rounded-2xl border border-gray-100" />
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-50 p-6 rounded-2xl border border-red-100 text-red-600">
          <p className="font-semibold">Error Loading Patients</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      ) : patients.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-dashed border-gray-200">
          <div className="bg-blue-50 p-4 rounded-full mb-4">
            <Users className="h-10 w-10 text-blue-500" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900">No patients found</h3>
          <p className="text-gray-500 mt-1 max-w-xs text-center">
            You don't have any assigned patients yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {patients.map((patient) => {
            const age = patient.date_of_birth 
              ? Math.floor((new Date().getTime() - new Date(patient.date_of_birth).getTime()) / 3.15576e+10)
              : 'Unknown';
              
            return (
              <div 
                key={patient.id} 
                className="group relative flex flex-col p-6 bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-xl hover:scale-[1.02] transition-all duration-300"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="p-3 bg-blue-50 rounded-xl">
                    <Users className="h-6 w-6 text-blue-600" />
                  </div>
                  {patient.blood_type && (
                    <span className="text-xs font-semibold px-2 py-1 rounded-full bg-red-50 text-red-700">
                      {patient.blood_type}
                    </span>
                  )}
                </div>
                
                <h3 className="text-xl font-bold text-gray-900 capitalize">
                  {patient.first_name} {patient.last_name}
                </h3>
                <p className="text-sm text-gray-500 mt-1 font-medium">
                  {age} yrs • {patient.gender || 'Not specified'}
                </p>
                
                <div className="mt-6 pt-6 border-t border-gray-50 flex items-center justify-between text-sm">
                  <Link
                    href={`/doctor/patients/${patient.id}`}
                    className="inline-flex items-center font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    View Profile
                    <ArrowRight className="ml-1.5 h-4 w-4" />
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
