"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, X, FileText, AlertCircle, CheckCircle2, Loader2, ArrowLeft } from "lucide-react";
import { useSession } from "next-auth/react";
import Link from "next/link";

export default function UploadReportPage() {
  const router = useRouter();
  const { data: session } = useSession();
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      const allowedTypes = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp"];
      
      if (!allowedTypes.includes(selectedFile.type)) {
        setError("Invalid file type. Please upload a PDF or an image (PNG, JPG, WebP).");
        return;
      }
      
      if (selectedFile.size > 10 * 1024 * 1024) {
        setError("File is too large. Max size is 10MB.");
        return;
      }
      
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file || !session?.user?.id) return;

    try {
      setIsUploading(true);
      setError(null);

      const formData = new FormData();
      formData.append("file", file);
      formData.append("patient_id", session.user.id);
      
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
      const response = await fetch(`${apiUrl}/api/v1/reports/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || "Upload failed");
      }

      setSuccess(true);
      setTimeout(() => {
        router.push("/patient/reports");
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong during upload");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="flex items-center space-x-4">
        <Link
          href="/patient/reports"
          className="p-2 hover:bg-gray-100 rounded-full transition-colors"
        >
          <ArrowLeft className="h-6 w-6 text-gray-500" />
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Upload Medical Report</h1>
          <p className="text-gray-500 mt-1">
            Our AI will automatically parse and summarize your report once uploaded.
          </p>
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-xl shadow-blue-100 overflow-hidden border border-gray-100">
        <div className="p-8 space-y-6">
          {!file ? (
            <div
              className="relative group border-2 border-dashed border-gray-200 rounded-2xl p-12 flex flex-col items-center justify-center space-y-4 hover:border-blue-400 hover:bg-blue-50 transition-all cursor-pointer"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files?.[0]) {
                  const dropFile = e.dataTransfer.files[0];
                  setFile(dropFile);
                }
              }}
            >
              <input
                type="file"
                className="absolute inset-0 opacity-0 cursor-pointer"
                onChange={handleFileChange}
                accept=".pdf,.png,.jpg,.jpeg,.webp"
              />
              <div className="p-4 bg-blue-50 rounded-full group-hover:bg-blue-100 transition-colors">
                <Upload className="h-10 w-10 text-blue-600" />
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-gray-900">
                  Click to upload or drag and drop
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  PDF, PNG, JPG or WebP (max. 10MB)
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between p-6 bg-blue-50 rounded-2xl border border-blue-100 animate-in fade-in zoom-in duration-300">
              <div className="flex items-center space-x-4">
                <div className="p-3 bg-white rounded-xl shadow-sm">
                  <FileText className="h-8 w-8 text-blue-600" />
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-900 truncate max-w-xs md:max-w-md">
                    {file.name}
                  </p>
                  <p className="text-sm text-blue-600/70 font-medium italic">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB • Ready to process
                  </p>
                </div>
              </div>
              {!isUploading && !success && (
                <button
                  onClick={() => setFile(null)}
                  className="p-2 hover:bg-white rounded-full transition-colors text-gray-400 hover:text-red-500"
                >
                  <X className="h-6 w-6" />
                </button>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-4 rounded-xl border border-red-100 animate-in slide-in-from-top-2">
              <AlertCircle className="h-5 w-5" />
              <p className="text-sm font-semibold">{error}</p>
            </div>
          )}

          {success && (
            <div className="flex items-center space-x-2 text-green-600 bg-green-50 p-4 rounded-xl border border-green-100 animate-in slide-in-from-top-2">
              <CheckCircle2 className="h-5 w-5" />
              <p className="text-sm font-semibold">Report uploaded successfully! Redirecting...</p>
            </div>
          )}

          <div className="pt-4">
            <button
              onClick={handleUpload}
              disabled={!file || isUploading || success}
              className="w-full flex items-center justify-center py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:text-gray-400 text-white rounded-2xl font-bold text-lg shadow-xl shadow-blue-200 hover:shadow-2xl hover:scale-[1.01] transition-all duration-300"
            >
              {isUploading ? (
                <>
                  <Loader2 className="mr-2 h-6 w-6 animate-spin" />
                  Uploading & Starting AI Analysis...
                </>
              ) : (
                "Continue to Analysis"
              )}
            </button>
          </div>
        </div>
        
        <div className="bg-gray-50 px-8 py-6 border-t border-gray-100">
          <div className="flex items-start space-x-3">
            <div className="p-1 bg-blue-100 rounded-full mt-0.5">
              <Loader2 className="h-3 w-3 text-blue-600" />
            </div>
            <p className="text-xs text-gray-500 leading-relaxed">
              By uploading, you agree that your medical data will be processed by our secure HIPAA-compliant AI to provide you with a summary and structured results. This is for informational purposes and does not replace professional medical advice.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
