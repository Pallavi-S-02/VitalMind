"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { 
  ArrowLeft, 
  Pill, 
  Clock, 
  ShieldCheck, 
  AlertTriangle,
  Loader2,
  Plus,
  Info,
  X,
  Search,
  CheckCircle2,
  AlertCircle,
  BrainCircuit,
  MessageSquare,
  Sparkles
} from "lucide-react";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Prescription {
  id: string;
  medication_name: string;
  dosage: string;
  frequency: string;
  route: string;
  status: string;
  start_date: string;
  end_date: string | null;
  instructions: string;
}

interface MedicationCatalogItem {
  id: string;
  name: string;
  description: string;
}

interface AnalysisResult {
  overall_safety_rating: "SAFE" | "CAUTION" | "UNSAFE" | "CRITICAL";
  response: string;
  critical_alerts: string[];
  moderate_warnings: string[];
  total_interactions: number;
}

export default function PatientMedicationsPage() {
  const { patientId } = useParams();
  const { data: session } = useSession();
  
  // Data States
  const [medications, setMedications] = useState<Prescription[]>([]);
  const [catalog, setCatalog] = useState<MedicationCatalogItem[]>([
    { id: "med-1", name: "Amoxicillin", description: "Antibiotic" },
    { id: "med-2", name: "Lisinopril", description: "Blood pressure" },
    { id: "med-3", name: "Metformin", description: "Diabetes" },
    { id: "med-4", name: "Amlodipine", description: "Blood pressure" },
    { id: "med-5", name: "Metoprolol", description: "Beta blocker" },
    { id: "med-6", name: "Omeprazole", description: "Proton pump inhibitor" },
    { id: "med-7", name: "Losartan", description: "Blood pressure" },
    { id: "med-8", name: "Atorvastatin", description: "Cholesterol" },
    { id: "med-9", name: "Levothyroxine", description: "Thyroid" },
    { id: "med-10", name: "Albuterol", description: "Inhaler" },
    { id: "med-11", name: "Gabapentin", description: "Nerve pain" },
    { id: "med-12", name: "Aspirin", description: "Pain relief/Blood thinner" },
  ]);
  
  // UI Loading States
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Interaction/Prescribe States
  const [isPrescribing, setIsPrescribing] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  
  // Form State
  const [formData, setFormData] = useState({
    medication_id: "",
    dosage: "",
    frequency: "",
    route: "oral",
    instructions: "",
    start_date: format(new Date(), "yyyy-MM-dd")
  });

  useEffect(() => {
    if (session?.accessToken && patientId) {
      fetchMedications();
      fetchCatalog();
    }
  }, [session, patientId]);

  const fetchMedications = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/api/v1/medications/patient/${patientId}`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (!res.ok) throw new Error("Failed to load medication profile");
      const data = await res.json();
      setMedications(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load medications");
    } finally {
      setLoading(false);
    }
  };

  const fetchCatalog = async () => {
    try {
      const res = await fetch(`${API}/api/v1/medications/catalog`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          // If the backend actually has drugs, combine them with our hardcoded list
          // ensuring no duplicates by ID
          setCatalog(prev => {
            const newCatalog = [...prev];
            data.forEach((d: MedicationCatalogItem) => {
              if (!newCatalog.find(c => c.id === d.id)) {
                newCatalog.push(d);
              }
            });
            return newCatalog;
          });
        }
      }
    } catch (err) {
      console.error("Failed to load catalog", err);
    }
  };

  const handlePrescribe = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/api/v1/medications/prescriptions`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}` 
        },
        body: JSON.stringify({
          ...formData,
          patient_id: patientId,
          doctor_id: session?.user?.id
        }),
      });

      if (!res.ok) throw new Error("Failed to create prescription");
      
      setIsPrescribing(false);
      fetchMedications();
      setFormData({
        medication_id: "",
        dosage: "",
        frequency: "",
        route: "oral",
        instructions: "",
        start_date: format(new Date(), "yyyy-MM-dd")
      });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Error prescribing medication");
    }
  };

  const checkInteractions = async () => {
    try {
      setIsAnalyzing(true);
      setAnalysisResult(null);
      const res = await fetch(`${API}/api/v1/medications/check-interactions`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}` 
        },
        body: JSON.stringify({ patient_id: patientId }),
      });

      if (!res.ok) throw new Error("Interaction check failed");
      const result = await res.json();
      setAnalysisResult(result);
    } catch (err) {
      setError("AI Analysis failed. Please try again.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500 relative">
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
            <h1 className="text-3xl font-bold tracking-tight text-gray-900">Medication Profile</h1>
            <p className="text-gray-500 mt-1">
              Active prescriptions and medication adherence records.
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <button 
              onClick={checkInteractions}
              disabled={isAnalyzing || medications.length === 0}
              className="inline-flex items-center px-4 py-2 bg-white border border-gray-200 text-gray-700 text-sm font-semibold rounded-xl hover:bg-gray-50 transition-all disabled:opacity-50"
            >
              {isAnalyzing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <ShieldCheck className="mr-2 h-4 w-4 text-green-500" />
              )}
              Check Interactions
            </button>
            <button 
              onClick={() => setIsPrescribing(true)}
              className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl transition-all shadow-md shadow-blue-200"
            >
              <Plus className="mr-2 h-4 w-4" />
              Prescribe
            </button>
          </div>
        </div>
      </div>

      {/* AI Analysis Result Panel */}
      {analysisResult && (
        <div className="bg-white rounded-3xl border border-gray-100 shadow-xl overflow-hidden animate-in slide-in-from-top duration-500">
          <div className={`px-6 py-4 flex items-center justify-between ${
            analysisResult.overall_safety_rating === 'SAFE' ? 'bg-emerald-50' : 
            analysisResult.overall_safety_rating === 'CAUTION' ? 'bg-amber-50' : 'bg-red-50'
          }`}>
            <div className="flex items-center space-x-3">
              <BrainCircuit className={`h-6 w-6 ${
                analysisResult.overall_safety_rating === 'SAFE' ? 'text-emerald-600' : 
                analysisResult.overall_safety_rating === 'CAUTION' ? 'text-amber-600' : 'text-red-600'
              }`} />
              <h2 className="font-bold text-gray-900 uppercase tracking-tight">AI Safety Screening</h2>
            </div>
            <button onClick={() => setAnalysisResult(null)} className="p-1 hover:bg-black/5 rounded-lg transition-colors">
              <X className="h-5 w-5 text-gray-500" />
            </button>
          </div>
          <div className="p-6 space-y-6">
            <div className="flex items-start space-x-4">
              <div className={`flex-shrink-0 w-12 h-12 rounded-2xl flex items-center justify-center ${
                analysisResult.overall_safety_rating === 'SAFE' ? 'bg-emerald-100' : 
                analysisResult.overall_safety_rating === 'CAUTION' ? 'bg-amber-100' : 'bg-red-100'
              }`}>
                {analysisResult.overall_safety_rating === 'SAFE' ? (
                  <CheckCircle2 className="h-6 w-6 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-6 w-6 text-red-600" />
                )}
              </div>
              <div className="flex-1">
                <p className="text-sm font-bold text-gray-400 uppercase tracking-widest">Overall Rating</p>
                <p className={`text-2xl font-black ${
                  analysisResult.overall_safety_rating === 'SAFE' ? 'text-emerald-600' : 
                  analysisResult.overall_safety_rating === 'CAUTION' ? 'text-amber-600' : 'text-red-600'
                }`}>
                  {analysisResult.overall_safety_rating}
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-start space-x-3 bg-gray-50 p-4 rounded-2xl border border-gray-100">
                <MessageSquare className="h-5 w-5 text-blue-500 mt-1 flex-shrink-0" />
                <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap italic">
                  {analysisResult.response}
                </p>
              </div>

              {analysisResult.critical_alerts.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-red-500 uppercase tracking-widest flex items-center">
                    <AlertTriangle className="h-3 w-3 mr-1" /> Critical Alerts
                  </h4>
                  {analysisResult.critical_alerts.map((alert, i) => (
                    <div key={i} className="text-sm text-red-700 bg-red-50 px-3 py-2 rounded-xl border border-red-100 leading-relaxed font-medium">
                      {alert}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="px-6 py-3 bg-gray-50 border-t border-gray-100 text-[10px] text-gray-400 font-medium flex items-center justify-center italic">
            <Sparkles className="h-3 w-3 mr-1" /> Powered by VitalMind Clinical Intelligence Agent
          </div>
        </div>
      )}

      {/* Main List */}
      <div className="space-y-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 bg-white rounded-3xl border border-gray-100 shadow-sm">
            <Loader2 className="h-10 w-10 text-blue-500 animate-spin mb-4" />
            <p className="text-gray-500 animate-pulse font-medium">Loading medication records...</p>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-100 p-6 rounded-3xl flex items-center space-x-4">
            <div className="p-3 bg-red-100 rounded-2xl text-red-600">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-red-800 font-bold">Error loading medications</h3>
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          </div>
        ) : medications.length === 0 ? (
          <div className="bg-white rounded-3xl border border-gray-100 p-16 text-center shadow-sm">
            <div className="mx-auto w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mb-6">
              <Pill className="h-8 w-8 text-blue-500" />
            </div>
            <h2 className="text-xl font-bold text-gray-900">No active medications</h2>
            <p className="text-gray-500 mt-2 max-w-sm mx-auto">
              This patient doesn't have any active prescriptions on record.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {medications.map((med) => (
              <div 
                key={med.id}
                className={`bg-white rounded-3xl border p-6 shadow-sm hover:shadow-lg transition-all duration-300 ${
                  med.status === 'active' ? 'border-gray-100' : 'border-gray-50 opacity-75'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex items-center space-x-4">
                    <div className={`p-3 rounded-2xl ${
                      med.status === 'active' ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-500'
                    }`}>
                      <Pill className="h-6 w-6" />
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <h3 className="text-lg font-bold text-gray-900">{med.medication_name}</h3>
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                          med.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                        }`}>
                          {med.status}
                        </span>
                      </div>
                      <div className="flex items-center text-sm text-gray-500 mt-1">
                        <Clock className="h-3.5 w-3.5 mr-1" />
                        {med.dosage} • {med.frequency}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-tighter">Started</p>
                    <p className="text-sm font-medium text-gray-700">
                      {format(new Date(med.start_date), "MMM d, yyyy")}
                    </p>
                  </div>
                </div>

                {med.instructions && (
                  <div className="mt-6 p-4 bg-gray-50 rounded-2xl flex items-start space-x-3">
                    <Info className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-gray-600 leading-relaxed">
                      <span className="font-bold text-gray-700 mr-1">Instructions:</span>
                      {med.instructions}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Prescribe Modal Overlay */}
      {isPrescribing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-white rounded-[2rem] w-full max-w-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
            <div className="px-8 py-6 bg-blue-600 flex items-center justify-between text-white">
              <div className="flex items-center space-x-3">
                <Pill className="h-6 w-6" />
                <h2 className="text-xl font-bold">New Prescription</h2>
              </div>
              <button onClick={() => setIsPrescribing(false)} className="p-2 hover:bg-white/10 rounded-xl transition-colors">
                <X className="h-6 w-6" />
              </button>
            </div>
            
            <form onSubmit={handlePrescribe} className="p-8 space-y-6">
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-widest ml-1">Medication Selection</label>
                  <div className="relative">
                    <select 
                      required
                      value={formData.medication_id}
                      onChange={(e) => setFormData({...formData, medication_id: e.target.value})}
                      className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-4 py-3 text-gray-900 appearance-none focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all font-medium"
                    >
                      <option value="">Select a drug...</option>
                      {catalog.map(med => (
                        <option key={med.id} value={med.id}>{med.name}</option>
                      ))}
                    </select>
                    <Search className="absolute right-4 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-widest ml-1">Dosage</label>
                    <input 
                      type="text" 
                      placeholder="e.g. 500mg"
                      required
                      value={formData.dosage}
                      onChange={(e) => setFormData({...formData, dosage: e.target.value})}
                      className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-4 py-3 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all" 
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-widest ml-1">Frequency</label>
                    <input 
                      type="text" 
                      placeholder="e.g. Twice Daily"
                      required
                      value={formData.frequency}
                      onChange={(e) => setFormData({...formData, frequency: e.target.value})}
                      className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-4 py-3 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all" 
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-widest ml-1">Special Instructions</label>
                  <textarea 
                    rows={3} 
                    placeholder="Take after full meal, avoid alcohol..."
                    value={formData.instructions}
                    onChange={(e) => setFormData({...formData, instructions: e.target.value})}
                    className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-4 py-3 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all resize-none" 
                  />
                </div>
              </div>

              <div className="flex space-x-3 pt-2">
                <button 
                  type="button"
                  onClick={() => setIsPrescribing(false)}
                  className="flex-1 px-4 py-3.5 bg-gray-100 text-gray-600 font-bold rounded-2xl hover:bg-gray-200 transition-all"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  className="flex-[2] px-4 py-3.5 bg-blue-600 text-white font-bold rounded-2xl hover:bg-blue-700 transition-all shadow-lg shadow-blue-200"
                >
                  Issue Prescription
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
