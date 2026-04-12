"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { Mic, Square, ShieldCheck, FileText, AlertCircle, Loader2 } from "lucide-react";
import { useVoiceStore } from "@/store/voiceStore";

export default function AmbientNotesPage() {
  const { data: session } = useSession();
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const sessionId = params.sessionId as string;
  const patientId = searchParams.get("patientId"); // Passed typically in URL or we look it up. Using URL param for simplicity.

  const [hasConsent, setHasConsent] = useState(false);
  const [showConsentModal, setShowConsentModal] = useState(true);

  const {
    connect,
    disconnect,
    isConnected,
    isRecording,
    ambientSoap,
    error,
    startRecording,
    stopRecording,
    endSession,
    sendAmbientConsent,
    clearError
  } = useVoiceStore();

  useEffect(() => {
    if (session?.accessToken && patientId) {
      // Connect in ambient mode
      connect(session.accessToken, "ambient", patientId, "en");
    }
    return () => {
      disconnect();
    };
  }, [session, patientId]);

  const handleConsent = (given: boolean) => {
    if (given && patientId) {
      sendAmbientConsent(patientId, true);
      setHasConsent(true);
      setShowConsentModal(false);
    } else {
      router.back();
    }
  };

  const handleEndSession = async () => {
    if (session?.accessToken) {
       const reportId = await endSession(session.accessToken);
       // Route to the new editing view
       if (reportId) {
          router.push(`/doctor/patients/${patientId}/notes/${reportId}`);
       } else {
          router.push(`/doctor/dashboard`);
       }
    } else {
      endSession();
      router.push(`/doctor/dashboard`);
    }
  };

  if (!patientId) {
    return <div className="p-8 text-red-500">Error: patientId query parameter is required.</div>;
  }

  return (
    <div className="h-full flex flex-col relative bg-slate-50">
      
      {/* Consent Modal Overlay */}
      {showConsentModal && (
        <div className="absolute inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-8 text-center space-y-6">
            <div className="mx-auto w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900 mb-2">Patient Consent Required</h2>
              <p className="text-sm text-gray-500 leading-relaxed">
                Ambient listening mode records real-time audio to construct clinical notes. 
                You must obtain verbal consent from the patient before proceeding.
              </p>
            </div>
            <div className="flex gap-4 pt-4">
              <button 
                onClick={() => handleConsent(false)}
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-gray-600 font-medium hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={() => handleConsent(true)}
                disabled={!isConnected}
                className="flex-1 px-4 py-2.5 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {isConnected ? "Consent Given" : "Connecting..."}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main UI */}
      <div className="flex-1 flex flex-col p-8 max-w-5xl mx-auto w-full gap-6">
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <FileText className="w-6 h-6 text-blue-600" />
              Live Ambient Scribe
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              {isConnected ? "Connected to secure stream" : "Connecting..."}
            </p>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={isRecording ? stopRecording : startRecording}
              disabled={!hasConsent || !isConnected}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full font-medium transition-all ${
                isRecording 
                  ? "bg-red-100 text-red-600 border border-red-200 hover:bg-red-200" 
                  : "bg-blue-600 text-white shadow-md shadow-blue-200 hover:bg-blue-700 disabled:opacity-50"
              }`}
            >
              {isRecording ? (
                <><span className="relative flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span></span> Recording...</>
              ) : (
                 <><Mic className="w-4 h-4" /> Start Auto-Notes</>
              )}
            </button>

            <button
              onClick={handleEndSession}
              className="px-5 py-2.5 rounded-full border border-gray-300 text-gray-700 bg-white font-medium hover:bg-gray-50 transition-all"
            >
              Finish Consultation
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-xl flex items-start gap-3 border border-red-100">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="flex-1 text-sm font-medium">{error}</div>
            <button onClick={clearError}>✕</button>
          </div>
        )}

        {/* SOAP Live View */}
        <div className="flex-1 bg-white rounded-3xl shadow-sm border border-gray-100 p-8 overflow-y-auto">
          {ambientSoap ? (
             <div className="space-y-8 animate-in fade-in">
               <SoapSection 
                  title="Subjective" 
                  data={ambientSoap.subjective} 
               />
               <SoapSection 
                  title="Objective" 
                  data={ambientSoap.objective} 
               />
               <SoapSection 
                  title="Assessment" 
                  data={ambientSoap.assessment} 
               />
               <SoapSection 
                  title="Plan" 
                  data={ambientSoap.plan} 
               />
             </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center opacity-40">
              {isRecording ? (
                <>
                  <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
                  <h3 className="text-lg font-medium text-gray-900">Listening to consultation...</h3>
                  <p className="text-gray-500 text-sm mt-2 max-w-sm">Clinical notes will begin actively forming here automatically as you converse with the patient.</p>
                </>
              ) : (
                <>
                   <FileText className="w-12 h-12 text-gray-400 mb-4" />
                   <h3 className="text-lg font-medium text-gray-900">Waiting to start</h3>
                   <p className="text-gray-500 text-sm mt-2">Start recording to enable real-time structured notes extraction.</p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Minimal recursive JSON renderer for SOAP sections
function SoapSection({ title, data }: { title: string, data: any }) {
  if (!data || (typeof data === 'object' && Object.keys(data).length === 0)) return null;

  const renderData = (val: any): React.ReactNode => {
    if (typeof val === 'string' || typeof val === 'number') return <span>{val}</span>;
    if (Array.isArray(val)) {
       if (val.length === 0) return <span className="text-gray-400 italic">None noted</span>;
       return <ul className="list-disc pl-4 space-y-1">{val.map((item, i) => <li key={i}>{renderData(item)}</li>)}</ul>;
    }
    if (typeof val === 'object' && val !== null) {
       const entries = Object.entries(val).filter(([_, v]) => v !== null && v !== "" && !(Array.isArray(v) && v.length === 0));
       if (entries.length === 0) return <span className="text-gray-400 italic">No details</span>;
       return (
         <div className="space-y-2 mt-2">
           {entries.map(([k, v]) => (
             <div key={k} className="pl-3 border-l-2 border-gray-100">
               <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-0.5">{k.replace(/_/g, ' ')}</span>
               <div className="text-sm text-gray-800">{renderData(v)}</div>
             </div>
           ))}
         </div>
       );
    }
    return null;
  };

  const isEmpty = 
    !data || 
    (typeof data === "object" && Object.values(data).every(v => v === null || v === "" || (Array.isArray(v) && v.length === 0)));

  return (
    <div className="border-b border-gray-100 pb-6 last:border-0 last:pb-0">
      <h3 className="text-xl font-semibold text-gray-900 mb-4">{title}</h3>
      {isEmpty ? (
         <p className="text-sm text-gray-400 italic leading-relaxed">No elements captured yet.</p>
      ) : (
         <div className="text-sm text-gray-700 leading-relaxed">
           {renderData(data)}
         </div>
      )}
    </div>
  );
}
