"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { 
  ArrowLeft, 
  FileText, 
  Clock, 
  AlertCircle, 
  CheckCircle2, 
  Info, 
  Database, 
  MessageSquare, 
  ExternalLink,
  ChevronRight,
  TrendingDown,
  TrendingUp,
  Minus
} from "lucide-react";
import { useSession } from "next-auth/react";
import { format } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface LabResult {
  test_name: string;
  value: string;
  unit: string;
  reference_range: string;
  status: "NORMAL" | "HIGH" | "LOW" | "UNKNOWN";
}

interface ReportDetails {
  id: string;
  title: string;
  type: string;
  date: string;
  file_url: string;
  summary: string; // JSON string from backend
  structured_data: {
    status: "processing" | "completed" | "failed";
    results?: LabResult[];
    report_type?: string;
  };
}

export default function ReportDetailsPage() {
  const { id } = useParams();
  const router = useRouter();
  const { data: session } = useSession();
  const [report, setReport] = useState<ReportDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"summary" | "data">("summary");

  useEffect(() => {
    if (session?.user?.id && id) {
      fetchReportDetails();
    }
  }, [session, id]);

  const fetchReportDetails = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API}/api/v1/reports/${id}`, {
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("Report not found or you don't have permission to view it.");
        } else if (response.status === 401 || response.status === 403) {
          throw new Error("Session expired or unauthorized access.");
        }
        throw new Error(`Server error (${response.status}). Please try again later.`);
      }

      const data = await response.json();
      setReport(data);
      
      // If still processing, poll every 5 seconds
      if (data.structured_data?.status === "processing") {
        setTimeout(fetchReportDetails, 5000);
      }
    } catch (err) {
      console.error("Error fetching report details:", err);
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading && !report) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="h-12 w-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-500 font-medium">Loading your report analysis...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="max-w-2xl mx-auto py-20 text-center space-y-6">
        <div className="bg-red-50 p-6 rounded-full w-20 h-20 mx-auto flex items-center justify-center">
          <AlertCircle className="h-10 w-10 text-red-600" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900">Oops! Something went wrong</h2>
        <p className="text-gray-500">{error || "Report not found"}</p>
        <button
          onClick={() => router.push("/patient/reports")}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Back to Reports
        </button>
      </div>
    );
  }

  const parsedSummary = report.summary ? JSON.parse(report.summary) : null;
  const isProcessing = report.structured_data?.status === "processing";
  const results = report.structured_data?.results || [];

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => router.push("/patient/reports")}
            className="p-2 hover:bg-white rounded-xl shadow-sm border border-gray-100 transition-all text-gray-500"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 line-clamp-1">{report.title}</h1>
            <div className="flex items-center space-x-3 mt-1">
              <span className="text-sm font-semibold text-blue-600 px-2 py-0.5 bg-blue-50 rounded-md border border-blue-100">
                {report.type.toUpperCase().replace("_", " ")}
              </span>
              <span className="text-sm text-gray-400 font-medium">•</span>
              <span className="text-sm text-gray-500 font-medium">{format(new Date(report.date), "MMMM d, yyyy")}</span>
            </div>
          </div>
        </div>
        
        {report.file_url && (
          <a
            href={report.file_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center px-4 py-2 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors text-sm font-semibold text-gray-700 shadow-sm"
          >
            <ExternalLink className="mr-2 h-4 w-4" />
            View Original
          </a>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: AI Analysis */}
        <div className="lg:col-span-8 space-y-6">
          {isProcessing ? (
            <div className="bg-white p-12 rounded-3xl border border-blue-100 shadow-xl shadow-blue-50 flex flex-col items-center text-center space-y-6">
              <div className="relative">
                <div className="h-24 w-24 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <Database className="h-8 w-8 text-blue-600 animate-pulse" />
                </div>
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-gray-900">AI Analysis in Progress</h2>
                <p className="text-gray-500 max-w-sm mx-auto">
                  VitalMind is currently scanning your report, identifying abnormalities, and generating a plain-language summary. This usually takes 15-30 seconds.
                </p>
              </div>
              <div className="w-full max-w-xs h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-blue-600 animate-progress origin-left w-full" />
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-3xl shadow-xl shadow-blue-50 border border-gray-100 overflow-hidden flex flex-col h-full">
              <div className="flex border-b border-gray-100">
                <button
                  onClick={() => setActiveTab("summary")}
                  className={cn(
                    "flex-1 px-8 py-5 text-sm font-bold transition-all flex items-center justify-center space-x-2 border-b-2",
                    activeTab === "summary" 
                      ? "border-blue-600 text-blue-600 bg-blue-50/50" 
                      : "border-transparent text-gray-400 hover:text-gray-600 hover:bg-gray-50"
                  )}
                >
                  <MessageSquare className="h-5 w-5" />
                  <span>AI Summary & Explainer</span>
                </button>
                <button
                  onClick={() => setActiveTab("data")}
                  className={cn(
                    "flex-1 px-8 py-5 text-sm font-bold transition-all flex items-center justify-center space-x-2 border-b-2",
                    activeTab === "data" 
                      ? "border-blue-600 text-blue-600 bg-blue-50/50" 
                      : "border-transparent text-gray-400 hover:text-gray-600 hover:bg-gray-50"
                  )}
                >
                  <Database className="h-5 w-5" />
                  <span>Structured Lab Data</span>
                </button>
              </div>

              <div className="p-8">
                {activeTab === "summary" ? (
                  <div className="space-y-10 animate-in fade-in duration-500">
                    {/* Patient-facing Summary */}
                    <div className="space-y-4">
                      <div className="flex items-center space-x-2">
                        <div className="p-2 bg-blue-50 rounded-lg">
                          <Info className="h-5 w-5 text-blue-600" />
                        </div>
                        <h3 className="text-xl font-bold text-gray-900 italic">For You: In Plain English</h3>
                      </div>
                      <div className="p-6 bg-gradient-to-br from-blue-50/50 to-indigo-50/50 rounded-3xl border border-blue-100/50">
                        <p className="text-lg leading-relaxed text-gray-800 font-medium tracking-tight">
                          {parsedSummary?.patient_explanation || "No explanation generated."}
                        </p>
                      </div>
                    </div>

                    {/* Clinical Summary */}
                    <div className="space-y-4">
                      <div className="flex items-center space-x-2">
                        <div className="p-2 bg-gray-50 rounded-lg">
                          <FileText className="h-5 w-5 text-gray-600" />
                        </div>
                        <h3 className="text-xl font-bold text-gray-900 italic">For Your Doctor: Clinical Notes</h3>
                      </div>
                      <div className="p-6 bg-gray-50/50 rounded-3xl border border-gray-100 prose prose-blue max-w-none">
                        <p className="text-base leading-relaxed text-gray-600 font-medium whitespace-pre-wrap">
                          {parsedSummary?.doctor_summary || "No clinical summary generated."}
                        </p>
                      </div>
                    </div>

                    {/* Follow-up */}
                    {parsedSummary?.suggested_followup && parsedSummary.suggested_followup.length > 0 && (
                      <div className="space-y-4">
                        <h3 className="text-xl font-bold text-gray-900 border-l-4 border-orange-400 pl-4">Suggested Next Steps</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {parsedSummary.suggested_followup.map((step: string, i: number) => (
                            <div key={i} className="flex items-center p-4 bg-orange-50/30 rounded-2xl border border-orange-100 text-orange-800 font-bold text-sm">
                              <ChevronRight className="h-4 w-4 mr-2 text-orange-400 flex-shrink-0" />
                              {step}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-6 animate-in fade-in duration-500">
                    <div className="overflow-x-auto rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
                      <table className="w-full text-sm text-left">
                        <thead className="bg-gray-50/80 text-gray-500 font-bold uppercase tracking-wider text-[10px]">
                          <tr>
                            <th className="px-6 py-4">Test Name</th>
                            <th className="px-6 py-4">Result</th>
                            <th className="px-6 py-4">Unit</th>
                            <th className="px-6 py-4">Ref. Range</th>
                            <th className="px-6 py-4">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {results.map((res, i) => (
                            <tr key={i} className="hover:bg-gray-50 transition-colors group">
                              <td className="px-6 py-5 font-bold text-gray-900">{res.test_name}</td>
                              <td className="px-6 py-5 font-mono font-bold text-blue-600 bg-blue-50/20">{res.value}</td>
                              <td className="px-6 py-5 text-gray-500 italic font-medium">{res.unit}</td>
                              <td className="px-6 py-5 text-gray-400 font-medium tabular-nums">{res.reference_range}</td>
                              <td className="px-6 py-5">
                                <div className="flex items-center">
                                  {res.status === "HIGH" ? (
                                    <span className="flex items-center px-3 py-1 rounded-lg bg-red-100 text-red-800 font-black text-[10px] tracking-tighter">
                                      <TrendingUp className="h-3 w-3 mr-1" />
                                      HIGH
                                    </span>
                                  ) : res.status === "LOW" ? (
                                    <span className="flex items-center px-3 py-1 rounded-lg bg-orange-100 text-orange-800 font-black text-[10px] tracking-tighter">
                                      <TrendingDown className="h-3 w-3 mr-1" />
                                      LOW
                                    </span>
                                  ) : res.status === "NORMAL" ? (
                                    <span className="flex items-center px-3 py-1 rounded-lg bg-green-100 text-green-800 font-black text-[10px] tracking-tighter">
                                      <CheckCircle2 className="h-3 w-3 mr-1" />
                                      NORMAL
                                    </span>
                                  ) : (
                                    <span className="flex items-center px-3 py-1 rounded-lg bg-gray-100 text-gray-600 font-black text-[10px] tracking-tighter">
                                      <Minus className="h-3 w-3 mr-1" />
                                      {res.status}
                                    </span>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Original Viewport */}
        <div className="lg:col-span-4 sticky top-6">
          <div className="bg-white rounded-3xl shadow-xl border border-gray-100 overflow-hidden h-[750px] relative">
            <div className="absolute top-0 left-0 right-0 h-10 bg-gray-900 flex items-center px-4 space-x-2 z-10">
              <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
              <div className="h-2.5 w-2.5 rounded-full bg-orange-400" />
              <div className="h-2.5 w-2.5 rounded-full bg-green-400" />
              <span className="text-[10px] text-gray-400 font-mono flex-1 text-center truncate pr-10">{report.title}</span>
            </div>
            {report.file_url ? (
              <iframe
                src={`${report.file_url}#toolbar=0&navpanes=0`}
                className="w-full h-full pt-10"
                title="Report Preview"
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full bg-gray-50 text-gray-400 italic">
                <FileText className="h-12 w-12 mb-2 opacity-20" />
                No preview available
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function cn(...classes: any[]) {
  return classes.filter(Boolean).join(" ");
}
