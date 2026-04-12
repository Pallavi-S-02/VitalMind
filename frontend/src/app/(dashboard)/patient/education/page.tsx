"use client";

import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
  BookOpen, AlertTriangle, Heart, Utensils, Activity,
  Phone, Loader2, ChevronDown, ChevronUp, Search
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface EducationContent {
  condition: string;
  overview: string;
  key_facts: string[];
  warning_signs: string[];
  lifestyle_tips: string[];
  medication_notes: string[];
  when_to_call_doctor: string[];
  resources: string[];
}

const SECTION_CONFIG = [
  { key: "key_facts", label: "Key Facts", icon: <BookOpen className="w-4 h-4" />, color: "text-indigo-600" },
  { key: "warning_signs", label: "Warning Signs", icon: <AlertTriangle className="w-4 h-4" />, color: "text-red-500" },
  { key: "lifestyle_tips", label: "Lifestyle Tips", icon: <Heart className="w-4 h-4" />, color: "text-emerald-500" },
  { key: "medication_notes", label: "Medication Notes", icon: <Activity className="w-4 h-4" />, color: "text-blue-500" },
  { key: "when_to_call_doctor", label: "When to Call Doctor", icon: <Phone className="w-4 h-4" />, color: "text-amber-500" },
];

function ConditionCard({ content }: { content: EducationContent }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-gray-100 rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-6 py-5 text-left"
      >
        <div>
          <h3 className="text-lg font-bold text-gray-900 capitalize">{content.condition}</h3>
          <p className="text-sm text-gray-500 mt-1 max-w-xl line-clamp-2">{content.overview}</p>
        </div>
        <div className="flex-shrink-0 ml-4">
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-gray-100 divide-y divide-gray-50">
          {SECTION_CONFIG.map(({ key, label, icon, color }) => {
            const items: string[] = content[key as keyof EducationContent] as string[] || [];
            if (!items.length) return null;
            return (
              <div key={key} className="px-6 py-4">
                <div className={`flex items-center gap-2 font-semibold text-sm mb-3 ${color}`}>
                  {icon} {label}
                </div>
                <ul className="space-y-1.5">
                  {items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-gray-300 flex-shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}

          {content.resources && content.resources.length > 0 && (
            <div className="px-6 py-4 bg-indigo-50/50">
              <div className="text-sm font-semibold text-indigo-700 mb-2">📚 Resources</div>
              <ul className="space-y-1">
                {content.resources.map((r, i) => (
                  <li key={i} className="text-sm text-indigo-600">{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function PatientEducationPage() {
  const { data: session } = useSession();
  const [educationContent, setEducationContent] = useState<EducationContent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const fetchEducation = async () => {
      if (!session?.accessToken || !session?.user?.id) return;
      try {
        // Get the active care plan, which contains education content
        const res = await fetch(`${API}/api/v1/care-plans/${session.user.id}`, {
          headers: { Authorization: `Bearer ${session.accessToken}` },
        });
        if (res.ok) {
          const plans = await res.json();
          const active = plans.find((p: any) => p.status === "active");

          // If care plan has education content embedded (from generation), extract it
          if (active?.goals?.education_content) {
            const content = active.goals.education_content;
            if (typeof content === "object") {
              setEducationContent(Object.values(content) as EducationContent[]);
            }
          } else if (active?.goals?.education_topics) {
            // Topics from plan, need to generate content dynamically
            // For now show placeholders. Full generation would call the agent
            setEducationContent([]);
          }
        }
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    };
    fetchEducation();
  }, [session]);

  const filtered = educationContent.filter((c) =>
    c.condition.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <BookOpen className="w-6 h-6 text-indigo-500" />
          Health Education
        </h1>
        <p className="text-gray-500 mt-1 text-sm">
          Personalized educational content generated for your conditions by our AI clinical team.
        </p>
      </div>

      {/* Search */}
      {educationContent.length > 1 && (
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conditions…"
            className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-50 transition-all bg-white"
          />
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-7 h-7 animate-spin text-indigo-400" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 bg-gray-50 rounded-2xl border border-gray-100">
          <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No education content available</p>
          <p className="text-gray-400 text-sm mt-1">
            Generate a care plan first to get personalized health education.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((content, i) => (
            <ConditionCard key={i} content={content} />
          ))}
        </div>
      )}
    </div>
  );
}
