"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, FileText, Search, Filter, AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { format } from "date-fns";
import { useSession } from "next-auth/react";

interface Report {
  id: string;
  title: string;
  type: string;
  date: string;
  status: "processing" | "completed" | "failed";
}

export default function ReportsPage() {
  const { data: session } = useSession();
  const [reports, setReports] = useState<Report[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session?.user?.id) {
      fetchReports();
    }
  }, [session]);

  const fetchReports = async () => {
    try {
      setIsLoading(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
      const response = await fetch(`${apiUrl}/api/v1/reports/patient/${session?.user?.id}`, {
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch reports");
      }

      const data = await response.json();
      setReports(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case "processing":
        return <Clock className="h-5 w-5 text-blue-500 animate-pulse" />;
      case "failed":
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Medical Reports</h1>
          <p className="text-muted-foreground mt-1 text-gray-500">
            View and manage your medical laboratory results and diagnostic reports.
          </p>
        </div>
        <Link
          href="/patient/reports/upload"
          className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow transition-colors hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
        >
          <Plus className="mr-2 h-4 w-4" />
          Upload Report
        </Link>
      </div>

      <div className="flex items-center space-x-4 bg-white p-4 rounded-xl shadow-sm border border-gray-100">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search reports by title or type..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
        </div>
        <button className="flex items-center px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium text-gray-600">
          <Filter className="mr-2 h-4 w-4" />
          Filter
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 bg-gray-100 animate-pulse rounded-2xl border border-gray-100" />
          ))}
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-dashed border-gray-200">
          <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900">Error Loading Reports</h3>
          <p className="text-gray-500 mt-1">{error}</p>
          <button
            onClick={fetchReports}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            Try Again
          </button>
        </div>
      ) : reports.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-dashed border-gray-200">
          <div className="bg-blue-50 p-4 rounded-full mb-4">
            <FileText className="h-10 w-10 text-blue-500" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900">No reports found</h3>
          <p className="text-gray-500 mt-1 max-w-xs text-center">
            You haven't uploaded any medical reports yet. Start by clicking the upload button.
          </p>
          <Link
            href="/patient/reports/upload"
            className="mt-6 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-lg shadow-blue-200 font-medium"
          >
            Upload your first report
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {reports.map((report) => (
            <Link
              key={report.id}
              href={`/patient/reports/${report.id}`}
              className="group relative flex flex-col p-6 bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-xl hover:scale-[1.02] transition-all duration-300"
            >
              <div className="flex justify-between items-start mb-4">
                <div className={`p-3 rounded-xl group-hover:text-white transition-colors duration-300 ${
                  report.type === "clinical_note" 
                    ? "bg-violet-50 text-violet-600 group-hover:bg-violet-600" 
                    : "bg-blue-50 text-blue-600 group-hover:bg-blue-600"
                }`}>
                  <FileText className={`h-6 w-6 group-hover:text-white ${
                    report.type === "clinical_note" ? "text-violet-600" : "text-blue-600"
                  }`} />
                </div>
                <div className="flex items-center space-x-1">
                  {getStatusIcon(report.status)}
                  <span className={cn(
                    "text-xs font-semibold px-2 py-1 rounded-full",
                    report.status === "completed" ? "bg-green-50 text-green-700" :
                    report.status === "processing" ? "bg-blue-50 text-blue-700" :
                    "bg-red-50 text-red-700"
                  )}>
                    {report.status.charAt(0).toUpperCase() + report.status.slice(1)}
                  </span>
                </div>
              </div>
              
              <div className="flex items-center gap-2 mb-1">
                {report.type === "clinical_note" && (
                  <span className="text-[10px] font-bold uppercase tracking-wider bg-violet-100 text-violet-700 px-2 py-0.5 rounded-md">
                    Doctor's Note
                  </span>
                )}
                {report.type !== "clinical_note" && (
                  <span className="text-[10px] font-bold uppercase tracking-wider bg-gray-100 text-gray-600 px-2 py-0.5 rounded-md">
                    Lab Report
                  </span>
                )}
              </div>
              
              <h3 className={`text-lg font-bold text-gray-900 line-clamp-1 transition-colors ${
                report.type === "clinical_note" ? "group-hover:text-violet-600" : "group-hover:text-blue-600"
              }`}>
                {report.title}
              </h3>
              <p className="text-sm text-gray-500 mt-1 font-medium italic">
                {report.type.replace('_', ' ').toUpperCase()}
              </p>
              
              <div className="mt-auto pt-6 flex items-center text-sm text-gray-400">
                <Clock className="h-4 w-4 mr-1.5" />
                {format(new Date(report.date), "PPP")}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function cn(...classes: any[]) {
  return classes.filter(Boolean).join(" ");
}
