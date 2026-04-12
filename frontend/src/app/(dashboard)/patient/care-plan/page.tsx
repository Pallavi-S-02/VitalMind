"use client";

import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  Target, CheckCircle2, Clock, AlertCircle, BookOpen,
  Loader2, Sparkles, ChevronRight, Activity, Calendar,
  TrendingUp, TrendingDown, Minus, RefreshCw
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Goal {
  id: string;
  title: string;
  description: string;
  target_metric: string;
  timeframe_weeks: number;
  priority: "high" | "medium" | "low";
}

interface Milestone {
  week: number;
  description: string;
  success_criteria: string;
}

interface Task {
  id: string;
  title: string;
  description: string;
  type: string;
  frequency: string;
  time_of_day: string;
  status: string;
}

interface CarePlan {
  id: string;
  title: string;
  description: string;
  status: string;
  start_date: string;
  end_date: string | null;
  goals: {
    goals?: Goal[];
    milestones?: Milestone[];
    success_metrics?: string[];
    education_topics?: string[];
    follow_up_weeks?: number;
  };
  tasks?: Task[];
}

const TASK_TYPE_COLORS: Record<string, string> = {
  exercise: "bg-emerald-50 text-emerald-700 border-emerald-100",
  diet: "bg-orange-50 text-orange-700 border-orange-100",
  medication_reminder: "bg-blue-50 text-blue-700 border-blue-100",
  reading: "bg-purple-50 text-purple-700 border-purple-100",
  vitals_check: "bg-rose-50 text-rose-700 border-rose-100",
};

const PRIORITY_COLORS: Record<string, string> = {
  high: "text-red-600 bg-red-50 border-red-100",
  medium: "text-amber-600 bg-amber-50 border-amber-100",
  low: "text-gray-500 bg-gray-50 border-gray-100",
};

export default function PatientCarePlanPage() {
  const { data: session } = useSession();
  const router = useRouter();

  const [plan, setPlan] = useState<CarePlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [completingId, setCompletingId] = useState<string | null>(null);

  const fetchPlan = async () => {
    if (!session?.accessToken || !session?.user?.id) return;
    try {
      const res = await fetch(`${API}/api/v1/care-plans/${session.user.id}`, {
        headers: { Authorization: `Bearer ${session.accessToken}` },
      });
      if (res.ok) {
        const plans: CarePlan[] = await res.json();
        const active = plans.find((p) => p.status === "active") || plans[0] || null;
        if (active) {
          // Load tasks too
          const planRes = await fetch(`${API}/api/v1/care-plans/plan/${active.id}`, {
            headers: { Authorization: `Bearer ${session.accessToken}` },
          });
          if (planRes.ok) {
            setPlan(await planRes.json());
          } else {
            setPlan(active);
          }
        }
      }
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchPlan(); }, [session]);

  const handleGenerate = async () => {
    if (!session?.accessToken || !session?.user?.id) return;
    setGenerating(true);
    try {
      const res = await fetch(`${API}/api/v1/care-plans/generate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ patient_id: session.user.id }),
      });
      if (res.ok) await fetchPlan();
    } catch (err) { console.error(err); }
    finally { setGenerating(false); }
  };

  const handleCompleteTask = async (taskId: string) => {
    if (!plan || !session?.accessToken) return;
    setCompletingId(taskId);
    try {
      const res = await fetch(`${API}/api/v1/care-plans/${plan.id}/tasks/${taskId}/complete`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.accessToken}` },
      });
      if (res.ok) await fetchPlan();
    } catch (err) { console.error(err); }
    finally { setCompletingId(null); }
  };

  const tasks = plan?.tasks || [];
  const completedTasks = tasks.filter((t) => t.status === "completed");
  const pendingTasks = tasks.filter((t) => t.status !== "completed");
  const adherencePct = tasks.length > 0 ? Math.round((completedTasks.length / tasks.length) * 100) : 0;
  const goals = plan?.goals?.goals || [];
  const milestones = plan?.goals?.milestones || [];

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-16 text-center">
        <div className="h-20 w-20 bg-indigo-50 rounded-full flex items-center justify-center mx-auto mb-6">
          <Target className="w-10 h-10 text-indigo-400" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">No Active Care Plan</h1>
        <p className="text-gray-500 mb-8">
          Generate a personalized AI care plan based on your health profile and medical history.
        </p>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white font-semibold rounded-full hover:bg-indigo-700 transition-colors shadow-md disabled:opacity-60"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {generating ? "Generating your plan…" : "Generate My Care Plan"}
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{plan.title}</h1>
          {plan.description && <p className="text-gray-500 mt-1 max-w-xl">{plan.description}</p>}
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-1.5 text-sm text-indigo-600 font-medium hover:underline disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${generating ? "animate-spin" : ""}`} />
          Regenerate
        </button>
      </div>

      {/* Adherence ring + quick stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-1 bg-white border border-gray-100 rounded-2xl p-5 flex flex-col items-center justify-center gap-2">
          <div className="relative h-24 w-24">
            <svg className="h-24 w-24 -rotate-90" viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15.9" fill="none" stroke="#f3f4f6" strokeWidth="3" />
              <circle
                cx="18" cy="18" r="15.9" fill="none"
                stroke={adherencePct >= 70 ? "#22c55e" : adherencePct >= 40 ? "#f59e0b" : "#ef4444"}
                strokeWidth="3"
                strokeDasharray={`${adherencePct} ${100 - adherencePct}`}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xl font-bold text-gray-900">{adherencePct}%</span>
            </div>
          </div>
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Adherence</span>
        </div>

        <div className="bg-white border border-gray-100 rounded-2xl p-5 flex flex-col justify-between">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">Tasks Completed</div>
          <div className="text-3xl font-bold text-gray-900 mt-2">{completedTasks.length}<span className="text-base font-normal text-gray-400">/{tasks.length}</span></div>
          <div className="text-xs text-gray-400 mt-1">{pendingTasks.length} remaining today</div>
        </div>

        <div className="bg-white border border-gray-100 rounded-2xl p-5 flex flex-col justify-between">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">Goals Set</div>
          <div className="text-3xl font-bold text-gray-900 mt-2">{goals.length}</div>
          <button
            onClick={() => router.push("/patient/education")}
            className="text-xs text-indigo-600 font-medium hover:underline mt-1 flex items-center gap-1"
          >
            <BookOpen className="w-3 h-3" /> Read education content
          </button>
        </div>
      </div>

      {/* Goals */}
      {goals.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-2">
            <Target className="w-4 h-4" /> Goals
          </h2>
          <div className="space-y-3">
            {goals.map((goal) => (
              <div key={goal.id} className="bg-white border border-gray-100 rounded-2xl p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold text-gray-900">{goal.title}</div>
                    <p className="text-sm text-gray-500 mt-1">{goal.description}</p>
                    {goal.target_metric && (
                      <div className="text-xs text-indigo-600 font-medium mt-2 flex items-center gap-1">
                        <Activity className="w-3 h-3" /> Target: {goal.target_metric}
                      </div>
                    )}
                  </div>
                  <span className={`flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full border ${PRIORITY_COLORS[goal.priority] || PRIORITY_COLORS.low}`}>
                    {goal.priority}
                  </span>
                </div>
                {goal.timeframe_weeks && (
                  <div className="text-xs text-gray-400 mt-3 flex items-center gap-1">
                    <Calendar className="w-3 h-3" /> {goal.timeframe_weeks}-week target
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Milestones timeline */}
      {milestones.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" /> Milestones
          </h2>
          <div className="relative pl-6 space-y-4">
            {/* Vertical line */}
            <div className="absolute left-2 top-2 bottom-2 w-px bg-gray-200" />
            {milestones.map((m, i) => (
              <div key={i} className="relative">
                <div className="absolute -left-4 top-1 h-5 w-5 rounded-full bg-indigo-100 border-2 border-indigo-300 flex items-center justify-center text-[10px] font-bold text-indigo-600">
                  {m.week}
                </div>
                <div className="bg-white border border-gray-100 rounded-xl p-4 ml-2">
                  <div className="text-xs font-semibold text-indigo-600 mb-1">Week {m.week}</div>
                  <p className="text-sm text-gray-700">{m.description}</p>
                  {m.success_criteria && (
                    <p className="text-xs text-gray-400 mt-1.5">✓ {m.success_criteria}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Today's Tasks */}
      {tasks.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" /> Tasks
          </h2>
          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                className={`bg-white border rounded-xl p-4 flex items-center gap-4 transition-all ${
                  task.status === "completed" ? "opacity-50 border-gray-100" : "border-gray-200 hover:border-indigo-200"
                }`}
              >
                <button
                  onClick={() => task.status !== "completed" && handleCompleteTask(task.id)}
                  disabled={task.status === "completed" || completingId === task.id}
                  className={`h-6 w-6 rounded-full flex-shrink-0 border-2 flex items-center justify-center transition-all ${
                    task.status === "completed"
                      ? "bg-emerald-500 border-emerald-500"
                      : "border-gray-300 hover:border-indigo-500"
                  }`}
                >
                  {completingId === task.id ? (
                    <Loader2 className="w-3 h-3 animate-spin text-gray-400" />
                  ) : task.status === "completed" ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                  ) : null}
                </button>

                <div className="flex-1 min-w-0">
                  <div className={`font-medium text-sm ${task.status === "completed" ? "line-through text-gray-400" : "text-gray-900"}`}>
                    {task.title}
                  </div>
                  {task.description && (
                    <p className="text-xs text-gray-400 truncate">{task.description}</p>
                  )}
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${TASK_TYPE_COLORS[task.type] || "bg-gray-50 text-gray-600 border-gray-100"}`}>
                    {task.type.replace("_", " ")}
                  </span>
                  <span className="text-[11px] text-gray-400">{task.frequency}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
