"use client";

import { useState, useEffect, useRef } from "react";
import { Search, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

export function GlobalSearchBar({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { data: session } = useSession();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
      setResults([]);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const token = (session as any)?.accessToken;
        // Construct standard fetch using the common env var pattern
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";
        const res = await fetch(`${apiUrl}/api/v1/search/?q=${encodeURIComponent(query)}&limit=10`, {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        
        if (res.ok) {
          const data = await res.json();
          setResults(Array.isArray(data) ? data : []);
        } else {
          setResults([]);
        }
      } catch (err) {
        console.error("Search failed:", err);
      } finally {
        setLoading(false);
      }
    }, 350); // debounce

    return () => clearTimeout(timer);
  }, [query, session]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-black/40 flex items-start justify-center pt-24 backdrop-blur-sm shadow-2xl" onClick={onClose}>
      <div 
        className="bg-white border border-gray-200 shadow-2xl rounded-xl w-full max-w-2xl overflow-hidden flex flex-col mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center px-4 py-3 border-b border-gray-200">
          <Search className="w-5 h-5 text-blue-500 mr-3" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Cmd+K or Search patients, reports, care plans..."
            className="flex-1 bg-transparent border-0 outline-none text-gray-800 placeholder:text-gray-400 text-lg focus:ring-0"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {loading && <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />}
          <div className="text-xs bg-gray-100 text-gray-500 px-2 py-1 rounded ml-3 cursor-pointer" onClick={onClose}>ESC</div>
        </div>
        
        {results.length > 0 && (
          <div className="max-h-96 overflow-y-auto py-2 bg-gray-50">
            {results.map((hit: any) => (
              <div 
                key={hit.id || hit._id || Math.random()}
                className="px-4 py-3 hover:bg-blue-50 cursor-pointer flex flex-col transition-colors border-l-2 border-transparent hover:border-blue-500"
                onClick={() => {
                  onClose();
                  // Routing based on type
                  if (hit.document_type === "patient") {
                    router.push(`/doctor/patient/${hit.id}`);
                  } else if (hit.document_type === "report") {
                    router.push(`/doctor/patient/${hit.patient_id || hit.id}?tab=reports`);
                  } else {
                    router.push(`/doctor/patient/${hit.patient_id || hit.id}`);
                  }
                }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-gray-800 capitalize truncate">
                    {hit.title || hit.filename || `Patient (${hit.birth_year || "Unknown DOB"})`}
                  </span>
                  <span className="text-[10px] bg-blue-100 text-blue-700 px-2 py-0.5 rounded uppercase tracking-wider font-semibold">
                    {hit.document_type || "document"}
                  </span>
                </div>
                <p className="text-sm text-gray-500 line-clamp-1">
                  {hit.summary || hit.description || "View clinical details for more information."}
                </p>
              </div>
            ))}
          </div>
        )}
        
        {query && !loading && results.length === 0 && (
          <div className="px-4 py-8 text-center text-gray-500 bg-gray-50">
            No clinical records found for "{query}".
          </div>
        )}
      </div>
    </div>
  );
}
