"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { FileText, Save, Loader2, ArrowLeft, CheckCircle2 } from "lucide-react";
import { AmbientSoap } from "@/store/voiceStore";

interface Report {
  id: string;
  title: string;
  summary: string;
  structured_data: {
    soap: AmbientSoap;
    session_id?: string;
  };
  created_at: string;
}

export default function EditClinicalNotePage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();

  const patientId = params.patientId as string;
  const reportId = params.reportId as string;

  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  
  // Editable string state for simplicity
  const [subjective, setSubjective] = useState("");
  const [objective, setObjective] = useState("");
  const [assessment, setAssessment] = useState("");
  const [plan, setPlan] = useState("");
  const [summary, setSummary] = useState("");

  useEffect(() => {
    if (session?.accessToken && reportId) {
      fetchReport();
    }
  }, [session, reportId]);

  const fetchReport = async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/api/v1/reports/${reportId}`, {
        headers: { "Authorization": `Bearer ${session?.accessToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setReport(data);
        setSummary(data.summary || "");
        
        // Flatten JSON objects to text for editing
        const soap = data.structured_data?.soap || {};
        setSubjective(jsonToText(soap.subjective));
        setObjective(jsonToText(soap.objective));
        setAssessment(jsonToText(soap.assessment));
        setPlan(jsonToText(soap.plan));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!session?.accessToken) return;
    setSaving(true);
    setSaveSuccess(false);

    try {
      // Send back as updated raw text objects
      const updatedSoap = {
        subjective: { notes: subjective },
        objective: { notes: objective },
        assessment: { notes: assessment },
        plan: { notes: plan }
      };

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000"}/api/v1/reports/${reportId}`, {
        method: "PUT",
        headers: { 
          "Authorization": `Bearer ${session.accessToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          summary,
          structured_data: { soap: updatedSoap }
        })
      });

      if (res.ok) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  // Helper to convert GPT SOAP JSON back into a readable block for textarea
  const jsonToText = (obj: any): string => {
    if (!obj) return "";
    const lines: string[] = [];
    Object.entries(obj).forEach(([k, v]) => {
      // capitalize and clean key
      const key = k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      if (typeof v === "string") {
        if (v.trim() !== "") lines.push(`${key}: ${v}`);
      } else if (Array.isArray(v)) {
        if (v.length > 0) lines.push(`${key}:\n- ${v.join('\n- ')}`);
      } else if (typeof v === "object" && v !== null) {
         // handle nested
         const nested = jsonToText(v);
         if (nested) lines.push(`${key}:\n${nested}`);
      }
    });
    return lines.join('\n\n');
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-gray-50">
         <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!report) {
    return <div className="p-8 text-red-500">Failed to load clinical note.</div>;
  }

  return (
    <div className="flex flex-col h-full bg-gray-50 overflow-y-auto">
      <div className="max-w-5xl mx-auto w-full px-8 py-8 space-y-6">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
             <button 
               onClick={() => router.push(`/doctor/patients/${patientId}`)}
               className="p-2 hover:bg-gray-200 rounded-full transition-colors"
             >
               <ArrowLeft className="w-5 h-5 text-gray-600" />
             </button>
             <div>
               <h1 className="text-2xl font-bold flex items-center gap-2 text-gray-900">
                 <FileText className="w-6 h-6 text-blue-600" />
                 Review AI Clinical Note
               </h1>
               <p className="text-sm text-gray-500">
                 Auto-generated from recent consultation. Please edit and finalize before saving to patient record.
               </p>
             </div>
          </div>
          
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white font-medium rounded-full hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-75"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 
             saveSuccess ? <CheckCircle2 className="w-4 h-4 text-emerald-300" /> : <Save className="w-4 h-4" />}
            {saving ? "Saving..." : saveSuccess ? "Saved!" : "Save to Record"}
          </button>
        </div>

        {/* Editor */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden divide-y divide-gray-100">
          
          {/* Summary Box */}
          <div className="p-6 bg-blue-50/50">
            <label className="block text-sm font-semibold text-blue-900 uppercase tracking-wider mb-2">Visit Summary</label>
            <textarea
               value={summary}
               onChange={(e) => setSummary(e.target.value)}
               className="w-full bg-white border border-blue-100 rounded-xl p-4 text-sm text-gray-800 focus:ring-2 ring-blue-100 outline-none transition-all resize-none"
               rows={2}
            />
          </div>

          <div className="p-6">
            <label className="block text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Subjective</label>
            <textarea
               value={subjective}
               onChange={(e) => setSubjective(e.target.value)}
               className="w-full bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-800 focus:bg-white focus:ring-2 ring-gray-100 outline-none transition-all"
               rows={5}
            />
          </div>

          <div className="p-6">
            <label className="block text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Objective</label>
            <textarea
               value={objective}
               onChange={(e) => setObjective(e.target.value)}
               className="w-full bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-800 focus:bg-white focus:ring-2 ring-gray-100 outline-none transition-all"
               rows={4}
            />
          </div>

          <div className="p-6">
            <label className="block text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Assessment</label>
            <textarea
               value={assessment}
               onChange={(e) => setAssessment(e.target.value)}
               className="w-full bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-800 focus:bg-white focus:ring-2 ring-gray-100 outline-none transition-all"
               rows={4}
            />
          </div>

          <div className="p-6 bg-green-50/30">
            <label className="block text-sm font-semibold text-green-700 uppercase tracking-wider mb-2">Plan</label>
            <textarea
               value={plan}
               onChange={(e) => setPlan(e.target.value)}
               className="w-full bg-white border border-green-100 rounded-xl p-4 text-sm text-gray-800 focus:ring-2 ring-green-100 outline-none transition-all"
               rows={5}
            />
          </div>

        </div>
      </div>
    </div>
  );
}
