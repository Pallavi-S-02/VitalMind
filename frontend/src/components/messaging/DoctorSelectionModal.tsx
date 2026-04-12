"use client";

import React, { useEffect, useState } from "react";
import { 
  X, 
  Search, 
  User, 
  Loader2, 
  ChevronRight,
  MessageCircle,
  AlertCircle
} from "lucide-react";
import { useSession, signOut } from "next-auth/react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Doctor {
  id: string;
  first_name: string;
  last_name: string;
  specialization?: string;
  avatar_url?: string;
}

interface DoctorSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (doctorId: string) => void;
}

export default function DoctorSelectionModal({ isOpen, onClose, onSelect }: DoctorSelectionModalProps) {
  const { data: session } = useSession();
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const [loadingId, setLoadingId] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && session?.accessToken) {
      setLoading(true);
      setError(null);
      setLoadingId(null); // Reset when reopening
      fetch(`${API}/api/v1/doctors/`, {
        headers: { Authorization: `Bearer ${session.accessToken}` },
      })
        .then(async (r) => {
          if (!r.ok) {
            if (r.status === 401) {
              throw new Error("Session expired. Please log out and log in again.");
            }
            throw new Error("Failed to load specialists");
          }
          return r.json();
        })
        .then((data) => {
          setDoctors(Array.isArray(data) ? data : data.doctors || []);
        })
        .catch((err) => {
          console.error(err);
          setError(err.message);
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, session]);

  if (!isOpen) return null;

  const filteredDoctors = doctors.filter(doc => 
    `${doc.first_name} ${doc.last_name}`.toLowerCase().includes(searchQuery.toLowerCase()) ||
    doc.specialization?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelect = (doctorId: string) => {
    setLoadingId(doctorId);
    onSelect(doctorId);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
      <div className="bg-gray-900 border border-white/10 w-full max-w-lg rounded-3xl overflow-hidden shadow-2xl animate-in zoom-in-95 duration-300">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between bg-white/5">
          <div>
            <h3 className="text-xl font-bold text-white">Start New Conversation</h3>
            <p className="text-sm text-gray-400">Select a specialist to chat with</p>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-white/5 rounded-xl text-gray-400 hover:text-white transition-all"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-white/5">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
            <input 
              type="text"
              placeholder="Search by name or specialty..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-950/50 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 transition-all"
            />
          </div>
        </div>

        {/* List */}
        <div className="max-h-[400px] overflow-y-auto p-2">
          {error ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-center px-4">
              <AlertCircle className="h-8 w-8 text-red-500" />
              <p className="text-sm font-semibold text-white">{error}</p>
              {error.includes("Session expired") && (
                <button 
                  onClick={() => signOut({ callbackUrl: '/login' })}
                  className="mt-2 text-xs bg-red-500/20 text-red-400 px-4 py-2 rounded-xl border border-red-500/30 hover:bg-red-500/30 transition-all font-bold uppercase tracking-widest"
                >
                  Log Out
                </button>
              )}
            </div>
          ) : loading ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
              <p className="text-sm text-gray-500">Loading specialists...</p>
            </div>
          ) : filteredDoctors.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-gray-500">No specialists found matching your search</p>
            </div>
          ) : (
            <div className="space-y-1">
              {filteredDoctors.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => handleSelect(doc.id)}
                  disabled={!!loadingId}
                  className={`w-full flex items-center gap-4 p-3 rounded-2xl transition-all text-left group ${
                    loadingId === doc.id 
                      ? "bg-blue-600/20 border-blue-500/50 cursor-wait" 
                      : "hover:bg-white/5 border border-transparent hover:border-white/5"
                  }`}
                >
                  <div className={`h-12 w-12 rounded-full flex items-center justify-center flex-shrink-0 transition-transform ${
                    loadingId === doc.id ? "bg-blue-600/20" : "bg-blue-600/10 border border-blue-500/20 group-hover:scale-105"
                  }`}>
                    {loadingId === doc.id ? (
                      <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
                    ) : (
                      <User className="h-6 w-6 text-blue-400" />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="font-bold text-white group-hover:text-blue-400 transition-colors">
                      Dr. {doc.first_name} {doc.last_name}
                    </div>
                    {doc.specialization && (
                      <div className="text-xs text-gray-400 mt-0.5">{doc.specialization}</div>
                    )}
                  </div>
                  {!loadingId && (
                    <div className="p-2 bg-white/5 rounded-lg opacity-0 group-hover:opacity-100 transition-all">
                      <MessageCircle className="h-4 w-4 text-blue-400" />
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-white/5 border-t border-white/5 text-center">
          <p className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold">
            Secure & HIPAA Compliant Messaging
          </p>
        </div>
      </div>
    </div>
  );
}
