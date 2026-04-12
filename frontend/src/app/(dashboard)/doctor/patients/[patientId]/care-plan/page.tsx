"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { 
  ArrowLeft, 
  HeartPulse, 
  Target, 
  CheckCircle2, 
  Clock, 
  Loader2,
  Plus,
  ChevronRight,
  TrendingUp,
  AlertCircle,
  X,
  Sparkles,
  Zap,
  Calendar
} from "lucide-react";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface CarePlanTask {
  id: string;
  title: string;
  type: string;
  frequency: string;
  status: string;
}

interface CarePlanGoal {
  id: string;
  title: string;
  description: string;
  priority: string;
  target_metric: string;
  timeframe_weeks: number;
}

interface CarePlan {
  id: string;
  title: string;
  description: string;
  status: string;
  start_date: string;
  end_date: string | null;
  goals: Record<string, CarePlanGoal>;
  tasks?: CarePlanTask[];
}

export default function PatientCarePlanPage() {
  const { patientId } = useParams();
  const { data: session } = useSession();
  const [plans, setPlans] = useState<CarePlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal & Generation State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [durationWeeks, setDurationWeeks] = useState(8);

  useEffect(() => {
    if (session?.accessToken && patientId) {
      fetchCarePlans();
    }
  }, [session, patientId]);

  const fetchCarePlans = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/api/v1/care-plans/${patientId}`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      
      if (!res.ok) throw new Error("Failed to load care plans");
      
      const data = await res.json();
      setPlans(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load care plans");
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePlan = async () => {
    if (!session?.accessToken) return;

    try {
      setIsGenerating(true);
      const res = await fetch(`${API}/api/v1/care-plans/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`
        },
        body: JSON.stringify({
          patient_id: patientId,
          duration_weeks: durationWeeks
        })
      });

      if (!res.ok) throw new Error("Care plan generation failed.");

      setIsModalOpen(false);
      fetchCarePlans();
    } catch (err) {
      alert("AI Agent encountered an error while building the care plan. Please try again.");
    } finally {
      setIsGenerating(false);
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
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 font-outfit uppercase tracking-wider">Care Plans</h1>
            <p className="text-gray-500 mt-1">
              Personalized health trajectories and adherence monitoring.
            </p>
          </div>
          <button 
            disabled={isGenerating}
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-2xl transition-all shadow-lg hover:shadow-blue-200 hover:-translate-y-0.5"
          >
            {isGenerating ? (
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            ) : (
              <Plus className="mr-2 h-5 w-5" />
            )}
            Create AI Care Plan
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-[2.5rem] border border-gray-100 shadow-sm">
          <Loader2 className="h-10 w-10 text-blue-500 animate-spin mb-4" />
          <p className="text-gray-500 animate-pulse font-medium">Analyzing care trajectories...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-100 p-6 rounded-[2.5rem] flex items-center space-x-4">
          <div className="p-3 bg-red-100 rounded-2xl text-red-600">
            <AlertCircle className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-red-800 font-bold font-outfit">Error loading care plans</h3>
            <p className="text-red-600 text-sm">{error}</p>
          </div>
        </div>
      ) : plans.length === 0 ? (
        <div className="bg-white rounded-[2.5rem] border border-gray-100 p-20 text-center shadow-sm">
          <div className="mx-auto w-20 h-20 bg-blue-50 rounded-3xl flex items-center justify-center mb-8 animate-bounce duration-1000">
            <HeartPulse className="h-10 w-10 text-blue-500" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 font-outfit uppercase tracking-tighter">No active care plans</h2>
          <p className="text-gray-500 mt-4 max-w-sm mx-auto text-lg leading-relaxed">
            Build a personalized health roadmap to track patient progress and adherence. 
            Click the "Create" button to start.
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {plans.map((plan) => (
            <div 
              key={plan.id}
              className="group bg-white rounded-[2.5rem] border border-gray-100 overflow-hidden shadow-sm hover:shadow-2xl hover:border-blue-100 transition-all duration-500"
            >
              <div className="p-8">
                <div className="flex justify-between items-start mb-8">
                  <div className="flex items-center space-x-5">
                    <div className="p-4 bg-blue-50 rounded-2xl text-blue-500 group-hover:bg-blue-600 group-hover:text-white transition-all duration-500">
                      <TrendingUp className="h-8 w-8" />
                    </div>
                    <div>
                      <div className="flex items-center space-x-3">
                        <h3 className="text-2xl font-black text-gray-900 font-outfit">{plan.title}</h3>
                        <span className={`text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full ${
                          plan.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                        }`}>
                          {plan.status}
                        </span>
                      </div>
                      <div className="flex items-center text-sm text-gray-500 mt-1 font-medium bg-gray-50 rounded-full px-3 py-1 w-fit">
                        <Clock className="h-3.5 w-3.5 mr-2 text-blue-400" />
                        Started {format(new Date(plan.start_date), "MMM d, yyyy")}
                      </div>
                    </div>
                  </div>
                  <button className="text-sm font-bold text-blue-600 hover:text-blue-700 flex items-center bg-blue-50/50 hover:bg-blue-50 px-4 py-2 rounded-xl transition-all">
                    Full Details
                    <ChevronRight className="ml-1 h-5 w-5" />
                  </button>
                </div>

                <p className="text-gray-600 text-lg leading-relaxed mb-10 max-w-3xl font-medium italic">
                  "{plan.description}"
                </p>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  {/* Goals Section */}
                  <div className="space-y-5">
                    <div className="flex items-center space-x-3 border-b border-gray-50 pb-4">
                      <Target className="h-5 w-5 text-blue-500" />
                      <h4 className="text-xs font-black text-gray-900 uppercase tracking-[0.2em]">Active Goals</h4>
                    </div>
                    <div className="space-y-4">
                      {Object.values(plan.goals?.goals || {}).map((goal: any, idx: number) => (
                        <div key={idx} className="flex items-start space-x-4 bg-gray-50/50 p-5 rounded-3xl border border-gray-100/50 hover:bg-white hover:shadow-lg hover:border-blue-50 transition-all duration-300">
                          <CheckCircle2 className="h-5 w-5 text-green-500 mt-1 flex-shrink-0" />
                          <div>
                            <p className="text-base text-gray-900 font-bold font-outfit">{goal.title || goal}</p>
                            {goal.description && <p className="text-xs text-gray-500 mt-1 leading-relaxed line-clamp-2">{goal.description}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Tasks Summary Section */}
                  <div className="space-y-5">
                    <div className="flex items-center space-x-3 border-b border-gray-50 pb-4">
                      <Clock className="h-5 w-5 text-orange-500" />
                      <h4 className="text-xs font-black text-gray-900 uppercase tracking-[0.2em]">Adherence Tasks</h4>
                    </div>
                    <div className="bg-gradient-to-br from-blue-50 to-blue-50/10 rounded-[2.5rem] p-8 border border-blue-100 flex flex-col items-center text-center">
                      <div className="relative w-32 h-32 flex items-center justify-center mb-6">
                        {/* Circular Progress (SVG) */}
                        <svg className="w-full h-full transform -rotate-90">
                          <circle cx="64" cy="64" r="58" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-gray-100" />
                          <circle cx="64" cy="64" r="58" stroke="currentColor" strokeWidth="8" fill="transparent" strokeDasharray="364.4" strokeDashoffset="54.6" className="text-blue-600 transition-all duration-1000 ease-out" />
                        </svg>
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                          <span className="text-3xl font-black text-gray-900 font-outfit">85%</span>
                          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Compliance</span>
                        </div>
                      </div>
                      <h5 className="text-lg font-bold text-gray-900 font-outfit">On-Track Performance</h5>
                      <p className="text-sm text-gray-500 mt-2 max-w-[220px]">
                        Patient is following daily medication and exercise tasks at high adherence levels.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Generation Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div 
            className="absolute inset-0 bg-gray-900/60 backdrop-blur-md animate-in fade-in duration-300" 
            onClick={() => !isGenerating && setIsModalOpen(false)}
          />
          <div className="relative bg-white w-full max-w-xl overflow-hidden rounded-[2.5rem] shadow-2xl border border-white/20 animate-in zoom-in-95 self-center duration-300">
            {isGenerating ? (
              <div className="p-12 flex flex-col items-center text-center space-y-8 min-h-[400px] justify-center">
                <div className="relative">
                  <div className="absolute inset-0 bg-blue-100 rounded-full animate-ping opacity-25" />
                  <div className="relative p-8 bg-blue-50 rounded-full text-blue-600">
                    <Sparkles className="h-16 w-16 animate-pulse" />
                  </div>
                </div>
                <div className="space-y-4">
                  <h3 className="text-3xl font-black text-gray-900 font-outfit uppercase tracking-tight">AI Agent at work</h3>
                  <p className="text-gray-500 font-medium italic text-lg pb-4">
                    Analyzing clinical records, vitals history, and previous consultations to build a high-fidelity care roadmap...
                  </p>
                  <div className="flex items-center justify-center space-x-2">
                    <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" />
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col">
                <div className="p-10 border-b border-gray-50 flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 bg-blue-600 rounded-2xl text-white">
                      <Zap className="h-6 w-6" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-black text-gray-900 font-outfit uppercase tracking-tight">Build Care Roadmap</h2>
                      <p className="text-gray-400 font-semibold italic text-sm">Automated clinical goal setting</p>
                    </div>
                  </div>
                  <button onClick={() => setIsModalOpen(false)} className="p-3 hover:bg-gray-50 rounded-2xl transition-all">
                    <X className="h-6 w-6 text-gray-400" />
                  </button>
                </div>

                <div className="p-10 space-y-10">
                  <div className="space-y-6">
                    <label className="text-xs font-black uppercase tracking-[0.2em] text-blue-600 flex items-center">
                      <Calendar className="mr-2 h-4 w-4" />
                      Plan Duration
                    </label>
                    <div className="grid grid-cols-3 gap-4">
                      {[4, 8, 12].map((weeks) => (
                        <button
                          key={weeks}
                          onClick={() => setDurationWeeks(weeks)}
                          className={`p-6 rounded-3xl border-2 transition-all flex flex-col items-center justify-center space-y-2 ${
                            durationWeeks === weeks
                              ? 'border-blue-600 bg-blue-50/50 text-blue-600 ring-4 ring-blue-100 shadow-lg'
                              : 'border-gray-100 hover:border-blue-200 text-gray-400'
                          }`}
                        >
                          <span className="text-3xl font-black font-outfit">{weeks}</span>
                          <span className="text-[10px] font-black uppercase tracking-widest">Weeks</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="bg-orange-50 rounded-3xl p-6 border border-orange-100/50 flex items-start space-x-4 italic">
                    <AlertCircle className="h-6 w-6 text-orange-500 mt-1 flex-shrink-0" />
                    <p className="text-sm text-orange-800 leading-relaxed font-semibold">
                      Note: The AI agent will ingest the last 3 months of vitals, medical history, and clinical notes to generate these goals.
                    </p>
                  </div>

                  <button
                    onClick={handleGeneratePlan}
                    className="w-full py-6 bg-blue-600 hover:bg-blue-700 text-white font-black rounded-3xl transition-all shadow-xl shadow-blue-200 flex items-center justify-center text-lg uppercase tracking-wider"
                  >
                    <Sparkles className="mr-3 h-6 w-6" />
                    Start Intelligence Sweep
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
