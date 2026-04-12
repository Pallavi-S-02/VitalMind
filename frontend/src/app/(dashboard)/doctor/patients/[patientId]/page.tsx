"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { 
  User, 
  Activity, 
  Thermometer, 
  Droplet, 
  Wind, 
  Scale, 
  Ruler, 
  Calendar, 
  ChevronLeft, 
  Loader2,
  Stethoscope,
  AlertTriangle,
  History,
  Pill,
  ClipboardList,
  FileText,
  MessageCircle,
  Video,
  ExternalLink,
  Plus
} from "lucide-react";
import { format, parseISO, differenceInYears } from "date-fns";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface PatientProfile {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  date_of_birth: string | null;
  gender: string;
  blood_type: string;
  height_cm: number | null;
  weight_kg: number | null;
  medical_history: string[];
  allergies: string[];
  chronic_diseases: string[];
}

interface Vitals {
  heart_rate?: number;
  systolic_bp?: number;
  diastolic_bp?: number;
  spo2?: number;
  temperature_c?: number;
  respiratory_rate?: number;
  _cached_at?: string;
}

export default function PatientDetailPage() {
  const { patientId } = useParams();
  const { data: session } = useSession();
  const router = useRouter();
  
  const [patient, setPatient] = useState<PatientProfile | null>(null);
  const [latestVitals, setLatestVitals] = useState<Vitals | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPatientData = async () => {
      if (!session?.accessToken || !patientId) return;

      console.log(`Fetching patient data for ${patientId} from ${API}`);

      try {
        setLoading(true);
        // 1. Fetch Patient Profile
        const profileUrl = `${API}/api/v1/patients/${patientId}`;
        console.log(`Fetching profile from: ${profileUrl}`);
        
        const profileRes = await fetch(profileUrl, {
          headers: { 
            "Authorization": `Bearer ${session.accessToken}`,
            "Accept": "application/json"
          },
        });

        if (!profileRes.ok) {
          const errorData = await profileRes.json().catch(() => ({}));
          throw new Error(errorData.message || `Profile Fetch Failed: ${profileRes.status}`);
        }
        
        const profileData = await profileRes.json();
        setPatient(profileData);

        // 2. Fetch Latest Vitals
        const vitalsUrl = `${API}/api/v1/vitals/${patientId}/current`;
        console.log(`Fetching vitals from: ${vitalsUrl}`);
        
        const vitalsRes = await fetch(vitalsUrl, {
          headers: { 
            "Authorization": `Bearer ${session.accessToken}`,
            "Accept": "application/json"
          },
        });
        
        if (vitalsRes.ok) {
          const vitalsData = await vitalsRes.json();
          setLatestVitals(vitalsData);
        }
      } catch (err) {
        console.error("Fetch Error:", err);
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchPatientData();
  }, [session, patientId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        <p className="text-sm text-gray-500 font-medium">Loading clinical records...</p>
      </div>
    );
  }

  if (error || !patient) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-center px-4">
        <div className="h-12 w-12 bg-red-50 rounded-full flex items-center justify-center mb-4">
          <AlertTriangle className="h-6 w-6 text-red-500" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Patient Not Found</h2>
        <p className="text-gray-500 max-w-sm mb-6">{error || "The medical record you are looking for could not be found or you do not have permission to view it."}</p>
        <Button onClick={() => router.push("/doctor/patients")} variant="outline" className="gap-2">
          <ChevronLeft className="h-4 w-4" /> Back to Patient List
        </Button>
      </div>
    );
  }

  const age = patient.date_of_birth ? differenceInYears(new Date(), parseISO(patient.date_of_birth)) : "N/A";

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-20 animate-in fade-in duration-500">
      {/* Breadcrumb & Top Actions */}
      <div className="flex items-center justify-between">
        <Button 
          variant="ghost" 
          onClick={() => router.push("/doctor/patients")}
          className="group text-gray-500 hover:text-indigo-600 pl-0"
        >
          <ChevronLeft className="h-4 w-4 mr-1 transition-transform group-hover:-translate-x-1" />
          Back to Patients
        </Button>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" className="gap-2 border-gray-200">
            <MessageCircle className="h-4 w-4" /> Message
          </Button>
          <Button variant="outline" size="sm" className="gap-2 border-gray-200">
            <Video className="h-4 w-4" /> Teledoc
          </Button>
          <Button size="sm" className="gap-2 bg-indigo-600 hover:bg-indigo-700 shadow-md">
            <Plus className="h-4 w-4" /> New Record
          </Button>
        </div>
      </div>

      {/* Hero Profile Section */}
      <div className="relative overflow-hidden bg-white rounded-2xl border border-gray-100 shadow-sm">
        <div className="absolute top-0 right-0 p-8 pt-6">
          <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-100 uppercase tracking-widest text-[10px] px-3 font-bold">
            Active Record
          </Badge>
        </div>
        <div className="p-8 flex flex-col md:flex-row gap-8 items-start relative z-10">
          <div className="h-24 w-24 rounded-2xl bg-indigo-600 flex items-center justify-center text-white text-3xl font-bold border-4 border-indigo-50 flex-shrink-0">
            {patient.first_name?.[0]}{patient.last_name?.[0]}
          </div>
          <div className="space-y-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {patient.first_name} {patient.last_name}
              </h1>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-2 text-sm text-gray-500 font-medium">
                <span className="flex items-center gap-1.5">
                  <User className="h-4 w-4 text-indigo-400" /> {patient.gender || "Not specified"}
                </span>
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-4 w-4 text-indigo-400" /> {age} years · {patient.date_of_birth ? format(parseISO(patient.date_of_birth), "MMM d, yyyy") : "N/A"}
                </span>
                <span className="flex items-center gap-1.5">
                  <Droplet className="h-4 w-4 text-rose-500" /> {patient.blood_type || "N/A"}
                </span>
                <span className="text-gray-300">|</span>
                <span className="text-xs text-gray-400 font-mono select-all">MRN: {patient.id.slice(0, 8).toUpperCase()}</span>
              </div>
            </div>

            <div className="flex flex-wrap gap-4">
               <div className="bg-gray-50 rounded-xl px-4 py-2 border border-gray-100">
                  <span className="text-[10px] uppercase text-gray-400 font-bold block mb-0.5">Height</span>
                  <div className="flex items-baseline gap-1">
                    <span className="text-lg font-bold text-gray-900">{patient.height_cm || "—"}</span>
                    <span className="text-xs text-gray-500 font-medium">cm</span>
                  </div>
               </div>
               <div className="bg-gray-50 rounded-xl px-4 py-2 border border-gray-100">
                  <span className="text-[10px] uppercase text-gray-400 font-bold block mb-0.5">Weight</span>
                  <div className="flex items-baseline gap-1">
                    <span className="text-lg font-bold text-gray-900">{patient.weight_kg || "—"}</span>
                    <span className="text-xs text-gray-500 font-medium">kg</span>
                  </div>
               </div>
               <div className="bg-gray-50 rounded-xl px-4 py-2 border border-gray-100">
                  <span className="text-[10px] uppercase text-gray-400 font-bold block mb-0.5">BMI</span>
                  <div className="flex items-baseline gap-1">
                    <span className="text-lg font-bold text-gray-900">
                      {patient.height_cm && patient.weight_kg 
                        ? (patient.weight_kg / Math.pow(patient.height_cm/100, 2)).toFixed(1)
                        : "—"}
                    </span>
                  </div>
               </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Clinical Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Latest Vitals Overview */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="shadow-none border-gray-100 bg-rose-50/30">
              <CardContent className="p-4 pt-4">
                <div className="flex items-center justify-between mb-2">
                  <Activity className="h-4 w-4 text-rose-500" />
                  <span className="text-[10px] font-bold text-rose-600 uppercase">HR</span>
                </div>
                <div className="text-2xl font-bold">{latestVitals?.heart_rate || "—"} <span className="text-xs font-normal text-gray-400">bpm</span></div>
              </CardContent>
            </Card>
            <Card className="shadow-none border-gray-100 bg-sky-50/30">
              <CardContent className="p-4 pt-4">
                <div className="flex items-center justify-between mb-2">
                  <Droplet className="h-4 w-4 text-sky-500" />
                  <span className="text-[10px] font-bold text-sky-600 uppercase">SpO₂</span>
                </div>
                <div className="text-2xl font-bold">{latestVitals?.spo2 || "—"} <span className="text-xs font-normal text-gray-400">%</span></div>
              </CardContent>
            </Card>
            <Card className="shadow-none border-gray-100 bg-purple-50/30">
              <CardContent className="p-4 pt-4">
                <div className="flex items-center justify-between mb-2">
                  <History className="h-4 w-4 text-purple-500" />
                  <span className="text-[10px] font-bold text-purple-600 uppercase">Blood Pres.</span>
                </div>
                <div className="text-2xl font-bold">
                  {latestVitals?.systolic_bp || "—"}<span className="text-gray-300 font-light mx-0.5">/</span>{latestVitals?.diastolic_bp || "—"}
                </div>
              </CardContent>
            </Card>
            <Card className="shadow-none border-gray-100 bg-amber-50/30">
              <CardContent className="p-4 pt-4">
                <div className="flex items-center justify-between mb-2">
                  <Thermometer className="h-4 w-4 text-amber-500" />
                  <span className="text-[10px] font-bold text-amber-600 uppercase">Temp</span>
                </div>
                <div className="text-2xl font-bold">{latestVitals?.temperature_c || "—"} <span className="text-xs font-normal text-gray-400">°C</span></div>
              </CardContent>
            </Card>
          </div>

          {/* Clinical Profile Details */}
          <Card className="border-gray-100 shadow-sm overflow-hidden">
            <CardHeader className="bg-gray-50/50 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <Stethoscope className="h-5 w-5 text-indigo-500" />
                <CardTitle className="text-lg">Clinical Profile</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="p-8 space-y-8">
              {/* Medical Conditions */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                   Medical Conditions
                </h3>
                <div className="flex flex-wrap gap-2">
                  {patient.medical_history.length > 0 ? (
                    patient.medical_history.map(c => (
                      <Badge key={c} className="bg-indigo-50 text-indigo-700 border-indigo-100 px-3 py-1 font-medium capitalize">
                        {c}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-sm text-gray-400 italic">No recorded conditions.</span>
                  )}
                </div>
              </div>

              <Separator className="bg-gray-100" />

              {/* Chronic Diseases */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                   Chronic Diseases
                </h3>
                <div className="flex flex-wrap gap-2">
                  {patient.chronic_diseases.length > 0 ? (
                    patient.chronic_diseases.map(d => (
                      <Badge key={d} className="bg-violet-50 text-violet-700 border-violet-100 px-3 py-1 font-medium capitalize">
                        {d}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-sm text-gray-400 italic">No chronic diseases recorded.</span>
                  )}
                </div>
              </div>

              <Separator className="bg-gray-100" />

              {/* Allergies */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-rose-600 flex items-center gap-2 uppercase tracking-tight">
                   <AlertTriangle className="h-4 w-4" /> Known Allergies
                </h3>
                <div className="flex flex-wrap gap-2">
                  {patient.allergies.length > 0 ? (
                    patient.allergies.map(a => (
                      <Badge key={a} variant="destructive" className="bg-rose-50 text-rose-600 border-rose-100 hover:bg-rose-100 px-3 py-1 font-bold">
                        {a}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-sm text-emerald-600 font-medium">No known drug/food allergies.</span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar Actions & Links */}
        <div className="space-y-6">
          <Card className="border-gray-100 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm uppercase tracking-wider text-gray-400 font-bold">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button 
                onClick={() => router.push(`/doctor/patients/${patientId}/care-plan`)}
                className="w-full justify-start gap-3 h-12 bg-white text-gray-700 border-gray-200 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-100 transition-all font-semibold shadow-none"
                variant="outline"
              >
                <ClipboardList className="h-4 w-4 text-indigo-500" />
                Manage Care Plan
              </Button>
              <Button 
                onClick={() => router.push(`/doctor/patients/${patientId}/medications`)}
                className="w-full justify-start gap-3 h-12 bg-white text-gray-700 border-gray-200 hover:bg-sky-50 hover:text-sky-700 hover:border-sky-100 transition-all font-semibold shadow-none"
                variant="outline"
              >
                <Pill className="h-4 w-4 text-sky-500" />
                Prescriptions
              </Button>
              <Button 
                onClick={() => router.push(`/doctor/patients/${patientId}/notes`)}
                className="w-full justify-start gap-3 h-12 bg-white text-gray-700 border-gray-200 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-100 transition-all font-semibold shadow-none"
                variant="outline"
              >
                <FileText className="h-4 w-4 text-emerald-500" />
                Consultation Notes
              </Button>
            </CardContent>
          </Card>

          <Card className="border-indigo-100 bg-indigo-50/40 shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-indigo-700 font-bold flex items-center gap-2">
                <Activity className="h-4 w-4" /> Monitoring Agent
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
               <p className="text-xs text-indigo-600/80 leading-relaxed font-medium">
                  The AI Agent is continuously monitoring this patient's vitals for anomalies.
               </p>
               <Button variant="outline" className="w-full bg-white border-indigo-200 text-indigo-700 text-xs font-bold gap-2">
                  View Anomaly Logs <ExternalLink className="h-3 w-3" />
               </Button>
            </CardContent>
          </Card>

          {/* Contact Info (Hidden partially for PHI) */}
          <div className="bg-gray-100/50 rounded-2xl p-6 border border-gray-200/50 space-y-4 mt-8">
             <div>
                <span className="text-[10px] uppercase text-gray-400 font-extrabold block mb-1">Contact Email</span>
                <span className="text-sm font-bold text-gray-700">{patient.email}</span>
             </div>
             <Separator className="bg-gray-200/50" />
             <div className="group cursor-help">
                <span className="text-[10px] uppercase text-gray-400 font-extrabold block mb-1">Encrypted PHI (Address)</span>
                <div className="flex items-center gap-2">
                   <div className="flex gap-1">
                      {[1,2,3,4,5,6,7,8].map(i => (
                        <div key={i} className="h-1.5 w-1.5 rounded-full bg-gray-300" />
                      ))}
                   </div>
                   <Badge variant="outline" className="text-[9px] py-0 border-gray-200 text-gray-400 bg-white">SECURE</Badge>
                </div>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}
