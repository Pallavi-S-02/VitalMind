"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { 
  ArrowLeft, 
  FileText, 
  Calendar, 
  ChevronRight, 
  Plus,
  Loader2,
  AlertCircle,
  X,
  Save,
  Info
} from "lucide-react";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface ClinicalNote {
  id: string;
  title: string;
  type: string;
  date: string;
  summary: string;
  structured_data?: {
    soap?: {
      subjective?: string;
      objective?: string;
      assessment?: string;
      plan?: string;
    };
  };
}

export default function PatientNotesPage() {
  const { patientId } = useParams();
  const { data: session } = useSession();
  const [notes, setNotes] = useState<ClinicalNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    subjective: "",
    objective: "",
    assessment: "",
    plan: ""
  });

  useEffect(() => {
    if (session?.accessToken && patientId) {
      fetchNotes();
    }
  }, [session, patientId]);

  const fetchNotes = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/api/v1/reports/patient/${patientId}`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      
      if (!res.ok) throw new Error("Failed to load notes");
      
      const data = await res.json();
      const filteredNotes = data.filter((report: any) => report.type === "clinical_note");
      setNotes(filteredNotes.sort((a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load clinical notes");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session?.accessToken) return;

    try {
      setIsSubmitting(true);
      const res = await fetch(`${API}/api/v1/reports/notes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`
        },
        body: JSON.stringify({
          ...formData,
          patient_id: patientId
        })
      });

      if (!res.ok) throw new Error("Failed to create note");

      setIsModalOpen(false);
      setFormData({ title: "", subjective: "", objective: "", assessment: "", plan: "" });
      fetchNotes();
    } catch (err) {
      alert("Error creating clinical note. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col space-y-4">
        <Link 
          href={`/doctor/patients/${patientId}`}
          className="inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors w-fit"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Patient Profile
        </Link>
        
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 font-outfit uppercase tracking-wider">Clinical Notes</h1>
            <p className="text-gray-500 mt-1">
              History of consultations and medical progress records.
            </p>
          </div>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-2xl transition-all shadow-lg hover:shadow-blue-200 hover:-translate-y-0.5 active:translate-y-0"
          >
            <Plus className="mr-2 h-5 w-5" />
            New Clinical Note
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-3xl border border-gray-100 shadow-sm">
          <Loader2 className="h-10 w-10 text-blue-500 animate-spin mb-4" />
          <p className="text-gray-500 animate-pulse font-medium">Fetching clinical records...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-100 p-6 rounded-3xl flex items-center space-x-4">
          <div className="p-3 bg-red-100 rounded-2xl text-red-600">
            <AlertCircle className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-red-800 font-bold">Error loading records</h3>
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        </div>
      ) : notes.length === 0 ? (
        <div className="bg-white rounded-3xl border border-gray-100 p-16 text-center shadow-sm">
          <div className="mx-auto w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mb-6">
            <FileText className="h-8 w-8 text-blue-500" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 font-outfit">No clinical notes recorded</h2>
          <p className="text-gray-500 mt-2 max-w-sm mx-auto">
            This patient doesn't have any formal consultation notes on file yet.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {notes.map((note) => (
            <div 
              key={note.id}
              className="group bg-white rounded-3xl border border-gray-100 p-8 shadow-sm hover:shadow-xl hover:border-blue-100 transition-all duration-500"
            >
              <div className="flex justify-between items-start mb-6">
                <div className="flex items-center space-x-5">
                  <div className="p-4 bg-blue-50 rounded-2xl text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-all duration-500">
                    <Calendar className="h-7 w-7" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900 font-outfit group-hover:text-blue-700 transition-colors">
                      {note.title}
                    </h3>
                    <div className="flex items-center text-sm text-gray-500 mt-1">
                      <span className="font-semibold text-gray-700 bg-gray-100 px-3 py-1 rounded-full">
                        {format(new Date(note.date), "MMMM dd, yyyy")}
                      </span>
                      <span className="mx-2">•</span>
                      <span className="text-blue-600 font-medium">Standard Consultation</span>
                    </div>
                  </div>
                </div>
                <button className="p-3 hover:bg-blue-50 rounded-2xl transition-colors text-gray-400 hover:text-blue-600">
                  <ChevronRight className="h-6 w-6" />
                </button>
              </div>

              <div className="bg-gray-50/80 rounded-3xl p-6 border border-gray-100/50">
                <div className="flex items-start mb-4">
                  <Info className="h-5 w-5 text-blue-500 mr-3 mt-1 flex-shrink-0" />
                  <p className="text-gray-800 text-base leading-relaxed font-medium">
                    {note.summary}
                  </p>
                </div>
                
                {note.structured_data?.soap && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-6 border-t border-gray-200">
                    {[
                      { keyPath: 'subjective', label: 'Subjective' },
                      { keyPath: 'objective', label: 'Objective' },
                      { keyPath: 'assessment', label: 'Assessment' },
                      { keyPath: 'plan', label: 'Plan' }
                    ].map((section) => {
                      const content = (note.structured_data?.soap as any)[section.keyPath];
                      const isEmpty = !content || (typeof content === 'object' && Object.keys(content).length === 0) || content === "";
                      
                      return (
                        <div key={section.keyPath} className="space-y-2">
                          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 block">
                            {section.label}
                          </span>
                          <div className="text-sm text-gray-600 line-clamp-3">
                            {isEmpty ? (
                              <span className="text-gray-300 italic">No record</span>
                            ) : (
                              typeof content === 'string' ? content : "View detailed record →"
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* New Note Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div 
            className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm animate-in fade-in duration-300" 
            onClick={() => setIsModalOpen(false)}
          />
          <div className="relative bg-white w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-[2.5rem] shadow-2xl border border-white/20 animate-in zoom-in-95 self-center duration-300 flex flex-col">
            {/* Modal Header */}
            <div className="p-8 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-blue-50/50 to-transparent">
              <div>
                <h2 className="text-2xl font-black text-gray-900 font-outfit uppercase tracking-tight">Record Clinical Note</h2>
                <p className="text-gray-500 mt-1 font-medium italic">Standard SOAP format (Subjective, Objective, Assessment, Plan)</p>
              </div>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="p-3 hover:bg-gray-100 rounded-2xl transition-all"
              >
                <X className="h-6 w-6 text-gray-400" />
              </button>
            </div>

            {/* Modal Content */}
            <form onSubmit={handleCreateNote} className="flex-1 overflow-y-auto p-8 space-y-8 scrollbar-hide">
              {/* Title Section */}
              <div className="space-y-4">
                <label className="text-xs font-black uppercase tracking-widest text-blue-600 flex items-center">
                  <div className="w-2 h-2 bg-blue-600 rounded-full mr-2" />
                  Visit Metadata
                </label>
                <input
                  required
                  type="text"
                  placeholder="e.g. Routine Hypertension Follow-up"
                  className="w-full p-4 rounded-2xl bg-gray-50 border-none focus:ring-2 focus:ring-blue-100 transition-all font-bold text-lg placeholder:text-gray-300"
                  value={formData.title}
                  onChange={(e) => setFormData({...formData, title: e.target.value})}
                />
              </div>

              {/* SOAP Sections */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Subjective */}
                <div className="space-y-3">
                  <label className="text-xs font-black uppercase tracking-widest text-gray-400">Subjective</label>
                  <textarea
                    rows={4}
                    placeholder="Patient history, symptoms, chief complaint..."
                    className="w-full p-5 rounded-3xl bg-gray-50 border-none focus:ring-2 focus:ring-blue-100 transition-all text-sm leading-relaxed"
                    value={formData.subjective}
                    onChange={(e) => setFormData({...formData, subjective: e.target.value})}
                  />
                </div>

                {/* Objective */}
                <div className="space-y-3">
                  <label className="text-xs font-black uppercase tracking-widest text-gray-400">Objective</label>
                  <textarea
                    rows={4}
                    placeholder="Vitals, physical exams, observastions..."
                    className="w-full p-5 rounded-3xl bg-gray-50 border-none focus:ring-2 focus:ring-blue-100 transition-all text-sm leading-relaxed"
                    value={formData.objective}
                    onChange={(e) => setFormData({...formData, objective: e.target.value})}
                  />
                </div>

                {/* Assessment */}
                <div className="space-y-3">
                  <label className="text-xs font-black uppercase tracking-widest text-gray-400">Assessment</label>
                  <textarea
                    rows={4}
                    placeholder="Diagnosis, clinical impression, severity..."
                    className="w-full p-5 rounded-3xl bg-gray-50 border-none focus:ring-2 focus:ring-blue-100 transition-all text-sm leading-relaxed"
                    value={formData.assessment}
                    onChange={(e) => setFormData({...formData, assessment: e.target.value})}
                  />
                </div>

                {/* Plan */}
                <div className="space-y-3">
                  <label className="text-xs font-black uppercase tracking-widest text-gray-400">Treatment Plan</label>
                  <textarea
                    rows={4}
                    placeholder="Medications, referrals, follow-up date..."
                    className="w-full p-5 rounded-3xl bg-gray-50 border-none focus:ring-2 focus:ring-blue-100 transition-all text-sm leading-relaxed"
                    value={formData.plan}
                    onChange={(e) => setFormData({...formData, plan: e.target.value})}
                  />
                </div>
              </div>
            </form>

            {/* Modal Footer */}
            <div className="p-8 border-t border-gray-100 flex justify-end space-x-4 bg-gray-50/50">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-6 py-3 text-gray-500 font-bold hover:text-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                onClick={handleCreateNote}
                className="inline-flex items-center px-10 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-black rounded-2xl transition-all shadow-xl shadow-blue-200 uppercase tracking-wider text-sm"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-5 w-5" />
                    Finalize Note
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
