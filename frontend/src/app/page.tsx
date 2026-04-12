import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Activity,
  HeartPulse,
  ShieldCheck,
  Microscope,
  ChevronRight,
  ArrowRight,
  Mic,
  Brain,
  Stethoscope,
  Zap,
  Lock,
  Network,
  FlaskConical,
  AlertTriangle,
  BookOpen,
  Star,
  Quote,
  CheckCircle2,
  Pill,
} from "lucide-react";

const ParticleCanvas = dynamic(
  () => import("@/components/landing/ParticleCanvas"),
  { ssr: false }
);

const HEARTBEAT_PATH = "M0,50 L60,50 L75,10 L90,90 L105,20 L120,80 L135,50 L300,50";

const AGENTS = [
  {
    number: "01",
    name: "Agent Orchestrator",
    tagline: "The Command Center",
    desc: "Coordinates all 7 specialist agents intelligently, routing every patient request to the right expert pipeline with sub-100ms latency.",
    icon: <Network className="w-6 h-6" />,
    color: "cyan",
    glow: "rgba(6,182,212,0.15)",
    border: "border-cyan-500/20",
    badge: "Core Infrastructure",
  },
  {
    number: "02",
    name: "Symptom Analyst",
    tagline: "Differential Diagnosis Engine",
    desc: "Processes natural language symptom descriptions to generate ranked differential diagnoses with ICD-10 codes and probability scores.",
    icon: <Brain className="w-6 h-6" />,
    color: "indigo",
    glow: "rgba(99,102,241,0.15)",
    border: "border-indigo-500/20",
    badge: "AI Powered",
  },
  {
    number: "03",
    name: "Triage Agent",
    tagline: "Emergency Prioritization",
    desc: "Real-time clinical severity assessment using ESI and NEWS2 frameworks. Instantly flags critical cases for immediate escalation.",
    icon: <AlertTriangle className="w-6 h-6" />,
    color: "rose",
    glow: "rgba(244,63,94,0.15)",
    border: "border-rose-500/20",
    badge: "Life Critical",
  },
  {
    number: "04",
    name: "Monitoring Agent",
    tagline: "24/7 Vitals Surveillance",
    desc: "Continuously ingests IoT wearable data (BPM, SpO₂, temperature, glucose) and fires anomaly alerts when thresholds are breached.",
    icon: <Activity className="w-6 h-6" />,
    color: "emerald",
    glow: "rgba(52,211,153,0.15)",
    border: "border-emerald-500/20",
    badge: "Always On",
  },
  {
    number: "05",
    name: "Drug Interaction Agent",
    tagline: "Prescription Safety Guard",
    desc: "Cross-validates new prescriptions against 80,000+ known drug interaction pathways before any medication is dispensed to the patient.",
    icon: <Pill className="w-6 h-6" />,
    color: "yellow",
    glow: "rgba(234,179,8,0.15)",
    border: "border-yellow-500/20",
    badge: "Zero Harm",
  },
  {
    number: "06",
    name: "Report Reader Agent",
    tagline: "Vision-Based Lab Analysis",
    desc: "Ingests raw PDF blood panels, MRI notes, and pathology reports using vision AI to extract, structure, and annotate clinical findings automatically.",
    icon: <Microscope className="w-6 h-6" />,
    color: "purple",
    glow: "rgba(168,85,247,0.15)",
    border: "border-purple-500/20",
    badge: "Vision AI",
  },
  {
    number: "07",
    name: "Voice AI Agent",
    tagline: "Real-Time Consultation",
    desc: "Powers Dr. Janvi AI via WebRTC. Multilingual STT → LLM reasoning → TTS in under 800ms. The closest thing to a real doctor on call.",
    icon: <Mic className="w-6 h-6" />,
    color: "blue",
    glow: "rgba(59,130,246,0.15)",
    border: "border-blue-500/20",
    badge: "WebRTC Live",
  },
];

const TESTIMONIALS = [
  {
    role: "patient",
    name: "Aarav Mehta",
    title: "Patient, Mumbai",
    avatar: "AM",
    avatarColor: "from-cyan-600 to-blue-700",
    stars: 5,
    quote: "At 2 AM I felt chest tightness. The Triage Agent assessed my symptoms in seconds and told me to call emergency services immediately. VitalMind may have saved my life.",
    highlight: "Emergency triage at 2 AM",
  },
  {
    role: "doctor",
    name: "Dr. Priya Sharma",
    title: "Cardiologist, Apollo Hospitals",
    avatar: "PS",
    avatarColor: "from-indigo-600 to-purple-700",
    stars: 5,
    quote: "The Report Reader Agent saves me 45 minutes per patient. Lab reports are pre-structured and annotated before I even open the file. The drug interaction checks are flawless.",
    highlight: "45 min saved per patient",
  },
  {
    role: "patient",
    name: "Sneha Iyer",
    title: "Patient, Bangalore",
    avatar: "SI",
    avatarColor: "from-emerald-600 to-teal-700",
    stars: 5,
    quote: "The monitoring agent caught that my SpO₂ was dropping during sleep. My doctor was alerted automatically. Turns out I had sleep apnea — I had no idea.",
    highlight: "Caught sleep apnea silently",
  },
  {
    role: "doctor",
    name: "Dr. Rahul Verma",
    title: "General Physician, Max Healthcare",
    avatar: "RV",
    avatarColor: "from-rose-600 to-red-700",
    stars: 5,
    quote: "The voice consultation agent handles my after-hours patients with remarkable clinical accuracy. The SOAP notes it generates are indistinguishable from ones I'd write myself.",
    highlight: "Human-quality SOAP notes",
  },
  {
    role: "patient",
    name: "Tanvi Kulkarni",
    title: "Patient, Pune",
    avatar: "TK",
    avatarColor: "from-yellow-600 to-orange-700",
    stars: 5,
    quote: "I uploaded my blood test PDF and within 30 seconds I had a plain-English explanation of every value, flagged abnormalities, and suggested follow-up questions for my doctor.",
    highlight: "Instant lab report clarity",
  },
  {
    role: "doctor",
    name: "Dr. Anjali Patel",
    title: "Oncologist, Tata Memorial",
    avatar: "AP",
    avatarColor: "from-blue-600 to-cyan-700",
    stars: 5,
    quote: "Drug interaction checking across complex chemo regimens used to take my team 20+ minutes manually. VitalMind's agent does it in under 3 seconds with zero misses.",
    highlight: "Zero drug interaction misses",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-[#03060f] text-slate-50 overflow-x-hidden selection:bg-cyan-500/20">

      <ParticleCanvas />

      {/* ─── Deep Background Glows ─── */}
      <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="glow-orb absolute w-[900px] h-[900px] rounded-full top-[-200px] left-[-300px]"
          style={{ background: "radial-gradient(circle, rgba(56,189,248,0.06) 0%, transparent 70%)" }} />
        <div className="glow-orb absolute w-[700px] h-[700px] rounded-full bottom-[-100px] right-[-200px]"
          style={{ background: "radial-gradient(circle, rgba(52,211,153,0.05) 0%, transparent 70%)", animationDelay: "2s" }} />
        <div className="absolute inset-0"
          style={{
            backgroundImage: "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.04) 1px, transparent 0)",
            backgroundSize: "40px 40px",
          }} />
      </div>

      {/* ─── EKG Banner ─── */}
      <div className="relative z-10 w-full h-12 overflow-hidden border-b border-white/[0.03]">
        <svg viewBox="0 0 300 100" className="absolute top-0 left-0 w-full h-full" preserveAspectRatio="none">
          <path d={HEARTBEAT_PATH} fill="none" stroke="rgba(52,211,153,0.5)" strokeWidth="1.5" className="ekg-path" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[10px] font-bold tracking-[0.4em] uppercase text-emerald-500/60 z-10">
            Live Patient Monitoring Active
          </span>
        </div>
      </div>

      {/* ─── Navbar ─── */}
      <header className="sticky top-0 z-50 w-full border-b border-white/[0.05]"
        style={{ background: "rgba(3,6,15,0.85)", backdropFilter: "blur(24px)" }}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative w-8 h-8">
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_20px_rgba(6,182,212,0.4)]" />
              <HeartPulse className="heartbeat absolute inset-0 m-auto w-4 h-4 text-white" />
            </div>
            <span className="text-xl font-black tracking-tight text-white">VitalMind</span>
          </div>
          <nav className="hidden md:flex items-center gap-8">
            {["Platform", "For Doctors", "Security", "Pricing"].map((item) => (
              <a key={item} href="#" className="text-sm font-medium text-slate-400 hover:text-white transition-colors">{item}</a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm font-medium text-slate-400 hover:text-white transition-colors">Sign In</Link>
            <Link href="/register"
              className="group relative overflow-hidden px-5 py-2 rounded-full text-sm font-bold text-white"
              style={{ background: "linear-gradient(135deg, #0ea5e9, #6366f1)" }}>
              <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-colors duration-300" />
              <span className="relative flex items-center gap-1.5">
                Get Started <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
              </span>
            </Link>
          </div>
        </div>
      </header>

      {/* ─── Hero Section ─── */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pt-20 pb-10">
        <div className="grid lg:grid-cols-2 gap-16 items-center min-h-[80vh]">
          <div>
            <div className="slide-up-1 inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/5 mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
              </span>
              <span className="text-xs font-semibold text-cyan-300 tracking-widest uppercase">7 Specialist AI Agents</span>
            </div>
            <h1 className="slide-up-2 text-5xl md:text-6xl xl:text-7xl font-black tracking-tighter leading-[1.0] mb-6">
              <span className="text-white">Your AI Doctor,</span>
              <br />
              <span className="relative inline-block">
                <span className="shimmer-text">Always Present.</span>
                <div className="absolute -bottom-2 left-0 right-0 h-px"
                  style={{ background: "linear-gradient(90deg, transparent, rgba(6,182,212,0.6), transparent)" }} />
              </span>
            </h1>
            <p className="slide-up-3 text-lg text-slate-400 leading-relaxed mb-10 max-w-lg">
              Meet Dr. Janvi — a generative AI physician backed by 7 specialist agents who listen, diagnose, monitor, and care for you 24/7. Real-time vitals, intelligent triage, and instant prescription safety.
            </p>
            <div className="slide-up-4 flex flex-col sm:flex-row gap-4">
              <Link href="/register"
                className="group relative overflow-hidden px-8 py-4 rounded-2xl font-bold text-white text-base shadow-[0_0_40px_rgba(6,182,212,0.25)] hover:shadow-[0_0_60px_rgba(6,182,212,0.4)] transition-all hover:scale-[1.02]"
                style={{ background: "linear-gradient(135deg, #0891b2, #4f46e5)" }}>
                <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-all duration-300" />
                <span className="relative flex items-center gap-2">
                  Start Your Free Consultation
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </span>
              </Link>
              <Link href="#agents"
                className="px-8 py-4 rounded-2xl font-semibold text-slate-300 hover:text-white border border-white/10 hover:border-white/20 hover:bg-white/5 transition-all text-base backdrop-blur-md">
                Meet the 7 Agents
              </Link>
            </div>
            <div className="mt-10 inline-flex items-center gap-3 px-4 py-2.5 rounded-2xl border border-emerald-500/20 bg-emerald-500/5">
              <div className="heartbeat"><HeartPulse className="w-5 h-5 text-emerald-400" /></div>
              <span className="text-sm font-bold text-emerald-400">72 BPM</span>
              <span className="text-xs text-slate-500">AI monitoring your vitals now</span>
              <div className="flex items-end gap-[2px] h-5">
                {[3, 5, 8, 12, 6, 9, 4, 7, 11, 5, 3].map((h, i) => (
                  <div key={i} className="wave-bar w-[3px] rounded-full bg-emerald-500/60"
                    style={{ height: `${h}px`, animationDelay: `${i * 0.08}s` }} />
                ))}
              </div>
            </div>
          </div>

          {/* Avatar Preview */}
          <div id="preview" className="relative flex items-center justify-center h-[520px]">
            <div className="absolute inset-0 rounded-full"
              style={{ background: "radial-gradient(ellipse at center, rgba(6,182,212,0.12) 0%, transparent 70%)" }} />
            <div className="absolute w-[420px] h-[420px] rounded-full border border-cyan-500/10" />
            <div className="absolute w-[340px] h-[340px] rounded-full border border-indigo-500/10" />
            <div className="absolute w-[420px] h-[420px] flex items-center justify-center">
              <div className="orbit-dot w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            </div>
            <div className="absolute w-[340px] h-[340px] flex items-center justify-center">
              <div className="orbit-dot-2 w-1.5 h-1.5 rounded-full bg-indigo-400 shadow-[0_0_6px_rgba(99,102,241,0.8)]" />
            </div>
            <div className="relative w-56 h-56 z-10">
              <div className="avatar-ring absolute inset-0 rounded-full border border-cyan-400/30" />
              <div className="avatar-ring absolute inset-0 rounded-full border border-cyan-400/20" style={{ animationDelay: "0.8s" }} />
              <div className="relative w-56 h-56 rounded-full overflow-hidden border-2 border-cyan-500/30"
                style={{
                  background: "linear-gradient(135deg, #0c1a2e 0%, #0a1628 50%, #0d1f3c 100%)",
                  boxShadow: "0 0 60px rgba(6,182,212,0.2), inset 0 0 40px rgba(6,182,212,0.05)",
                }}>
                <div className="absolute left-0 right-0 h-[2px] z-20 pointer-events-none"
                  style={{ background: "linear-gradient(90deg, transparent, rgba(6,182,212,0.6), transparent)", animation: "scan-line 2.5s linear infinite" }} />
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <div className="w-20 h-20 rounded-full mb-3 flex items-center justify-center"
                    style={{ background: "linear-gradient(135deg, #164e63, #1e3a6e)" }}>
                    <Stethoscope className="w-10 h-10 text-cyan-300" />
                  </div>
                  <p className="text-sm font-bold text-white">Dr. Janvi AI</p>
                  <p className="text-[10px] text-cyan-400/70 uppercase tracking-widest">Attending Physician</p>
                </div>
                <div className="absolute bottom-0 left-0 right-0 px-4 py-3 flex items-center justify-between"
                  style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(8px)" }}>
                  <span className="text-[9px] font-bold text-emerald-400 uppercase tracking-wider">● Online</span>
                  <div className="flex gap-[2px] items-end h-4">
                    {[2, 4, 6, 8, 5, 7, 3].map((h, i) => (
                      <div key={i} className="wave-bar w-[2px] rounded-full bg-emerald-400"
                        style={{ height: `${h}px`, animationDelay: `${i * 0.1}s` }} />
                    ))}
                  </div>
                  <span className="text-[9px] text-slate-500 font-mono">WebRTC</span>
                </div>
              </div>
            </div>
            <div className="float-card absolute top-8 -right-4 md:right-4 z-20">
              <div className="px-4 py-3 rounded-2xl border border-white/10 text-left min-w-[150px]"
                style={{ background: "rgba(12,22,45,0.85)", backdropFilter: "blur(20px)", boxShadow: "0 8px 32px rgba(0,0,0,0.4)" }}>
                <div className="flex items-center gap-2 mb-1">
                  <Activity className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Heart Rate</span>
                </div>
                <div className="flex items-end gap-1">
                  <span className="text-2xl font-black text-white">72</span>
                  <span className="text-sm text-slate-400 mb-0.5">bpm</span>
                </div>
                <div className="mt-1.5 flex items-end gap-[2px] h-5">
                  {[4, 7, 3, 9, 5, 8, 4, 6, 10, 5, 7, 3, 8].map((h, i) => (
                    <div key={i} className="wave-bar w-[3px] rounded-full bg-cyan-500/70"
                      style={{ height: `${h}px`, animationDelay: `${i * 0.07}s` }} />
                  ))}
                </div>
              </div>
            </div>
            <div className="float-slow absolute bottom-16 -left-4 md:left-4 z-20">
              <div className="px-4 py-3 rounded-2xl border border-white/10 text-left min-w-[160px]"
                style={{ background: "rgba(12,22,45,0.85)", backdropFilter: "blur(20px)", boxShadow: "0 8px 32px rgba(0,0,0,0.4)" }}>
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">AI Analysis</span>
                </div>
                <div className="space-y-1.5">
                  {[["Symptom Match", "94%", "text-emerald-400"], ["Risk Score", "Low", "text-blue-400"], ["Confidence", "98.2%", "text-cyan-400"]].map(([label, val, color]) => (
                    <div key={label} className="flex justify-between items-center">
                      <span className="text-[10px] text-slate-500">{label}</span>
                      <span className={`text-[11px] font-bold ${color}`}>{val}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="float-card absolute -bottom-4 right-0 md:right-8 z-20" style={{ animationDelay: "2s" }}>
              <div className="px-3 py-2.5 rounded-xl border border-emerald-500/20 flex items-center gap-2"
                style={{ background: "rgba(4,20,15,0.9)", backdropFilter: "blur(20px)" }}>
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span className="text-[11px] font-semibold text-emerald-300">HIPAA Compliant</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Heartbeat Divider ─── */}
      <div className="relative z-10 w-full h-16 my-4 overflow-hidden">
        <svg viewBox="0 0 1200 60" className="w-full h-full" preserveAspectRatio="none">
          <path d="M0,30 L200,30 L240,5 L260,55 L280,10 L300,50 L320,30 L600,30 L640,5 L660,55 L680,10 L700,50 L720,30 L1200,30"
            fill="none" stroke="rgba(6,182,212,0.15)" strokeWidth="1" />
          <path d="M0,30 L200,30 L240,5 L260,55 L280,10 L300,50 L320,30 L600,30 L640,5 L660,55 L680,10 L700,50 L720,30 L1200,30"
            fill="none" stroke="rgba(6,182,212,0.6)" strokeWidth="1.5" strokeDasharray="100 1100" className="ekg-path" />
        </svg>
      </div>

      {/* ─── Trust Bar ─── */}
      <section className="relative z-10 py-10 border-y border-white/[0.04]" style={{ background: "rgba(255,255,255,0.01)" }}>
        <div className="max-w-7xl mx-auto px-6">
          <p className="text-center text-[10px] font-bold tracking-[0.3em] uppercase text-slate-600 mb-8">
            Trusted By Innovative Practices Globally
          </p>
          <div className="flex flex-wrap justify-center items-center gap-10 md:gap-20 opacity-30 hover:opacity-60 transition-opacity duration-700">
            {[["🏥", "MayoLink"], ["💊", "ZenithCare"], ["🔬", "TeleVanguard"], ["🔒", "SecureMed"], ["🧬", "BioSynth AI"]].map(([icon, name]) => (
              <div key={name} className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
                <span>{icon}</span>{name}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════
          ─── 7 AI AGENTS SECTION ───
      ════════════════════════════════════════════════ */}
      <section id="agents" className="relative z-10 py-32 max-w-7xl mx-auto px-6">
        <div className="text-center mb-20">
          <p className="text-xs font-bold tracking-[0.3em] uppercase text-cyan-500 mb-3">The Intelligence Stack</p>
          <h2 className="text-4xl md:text-6xl font-black tracking-tighter mb-4">
            7 Specialist AI Agents,{" "}
            <br className="hidden md:block" />
            <span className="shimmer-text">Working as One.</span>
          </h2>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto">
            Each agent is a world-class specialist. Together, they form the most comprehensive clinical AI platform ever built.
          </p>
        </div>

        {/* Agents Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {AGENTS.map((agent, idx) => (
            <div
              key={agent.name}
              className={`group relative overflow-hidden rounded-[2rem] p-7 border ${agent.border} border-opacity-30 
                hover:border-opacity-60 transition-all duration-500 cursor-default
                ${idx === 0 ? "md:col-span-2 lg:col-span-1" : ""}`}
              style={{ background: "rgba(10,18,38,0.7)", backdropFilter: "blur(20px)" }}
            >
              {/* Hover glow */}
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-[2rem]"
                style={{ background: `radial-gradient(circle at 30% 30%, ${agent.glow}, transparent 70%)` }} />

              <div className="relative z-10">
                {/* Header */}
                <div className="flex items-start justify-between mb-5">
                  <div className={`w-12 h-12 rounded-2xl flex items-center justify-center border ${agent.border}`}
                    style={{ background: agent.glow }}>
                    <span className={`text-${agent.color}-400`}>{agent.icon}</span>
                  </div>
                  <div className="flex flex-col items-end gap-1.5">
                    <span className={`text-xs font-bold text-${agent.color}-400 border ${agent.border} px-2.5 py-0.5 rounded-full`}
                      style={{ background: agent.glow }}>
                      {agent.badge}
                    </span>
                    <span className="text-[10px] font-black text-slate-700 font-mono">{agent.number}</span>
                  </div>
                </div>

                <h3 className="text-xl font-black mb-1 tracking-tight">{agent.name}</h3>
                <p className={`text-xs font-bold text-${agent.color}-400 mb-3 uppercase tracking-widest`}>{agent.tagline}</p>
                <p className="text-slate-400 text-sm leading-relaxed">{agent.desc}</p>

                {/* Bottom status indicator */}
                <div className="mt-5 pt-4 border-t border-white/[0.04] flex items-center gap-2">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className={`animate-ping absolute inline-flex h-full w-full rounded-full bg-${agent.color}-400 opacity-75`} />
                    <span className={`relative inline-flex rounded-full h-1.5 w-1.5 bg-${agent.color}-400`} />
                  </span>
                  <span className={`text-[10px] font-semibold text-${agent.color}-400 uppercase tracking-widest`}>Agent Active</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Architecture Note */}
        <div className="mt-10 p-6 rounded-[1.5rem] border border-white/[0.05] flex flex-col md:flex-row items-center gap-6"
          style={{ background: "rgba(6,182,212,0.03)", backdropFilter: "blur(12px)" }}>
          <div className="w-12 h-12 rounded-2xl flex-shrink-0 flex items-center justify-center border border-cyan-500/20"
            style={{ background: "rgba(6,182,212,0.08)" }}>
            <Network className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <p className="text-sm font-bold text-white mb-1">LangGraph Multi-Agent Architecture</p>
            <p className="text-sm text-slate-400">All 7 agents run on a LangGraph state-machine orchestrated pipeline with shared Redis memory, giving every agent instant access to full patient context — no information silos.</p>
          </div>
          <div className="flex-shrink-0 flex gap-4 text-center">
            <div>
              <p className="text-2xl font-black text-cyan-400">&lt;100ms</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest">Routing</p>
            </div>
            <div className="w-px bg-white/10" />
            <div>
              <p className="text-2xl font-black text-emerald-400">7</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest">Agents</p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Stats Row ─── */}
      <section className="relative z-10 border-y border-white/[0.04] py-16"
        style={{ background: "rgba(3,6,15,0.9)", backdropFilter: "blur(16px)" }}>
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8">
          {[
            ["99.9%", "Uptime SLA", "text-cyan-400"],
            ["<50ms", "Triage Latency", "text-emerald-400"],
            ["AES-256", "PHI Encryption", "text-indigo-400"],
            ["24 / 7", "Live AI Monitoring", "text-rose-400"],
          ].map(([val, label, color]) => (
            <div key={label} className="text-center group">
              <p className={`text-4xl md:text-5xl font-black mb-1 ${color} group-hover:scale-105 transition-transform duration-300`}>{val}</p>
              <p className="text-xs uppercase tracking-widest text-slate-500 font-bold">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ════════════════════════════════════════════════
          ─── TESTIMONIALS SECTION ───
      ════════════════════════════════════════════════ */}
      <section id="testimonials" className="relative z-10 py-32 max-w-7xl mx-auto px-6">
        <div className="text-center mb-20">
          <p className="text-xs font-bold tracking-[0.3em] uppercase text-indigo-400 mb-3">Real Experiences</p>
          <h2 className="text-4xl md:text-6xl font-black tracking-tighter mb-4">
            What doctors &amp; patients{" "}
            <span className="shimmer-text">actually say.</span>
          </h2>
          <p className="text-lg text-slate-400 max-w-xl mx-auto">
            Verified feedback from the medical community and real patients across India.
          </p>

          {/* Role tabs */}
          <div className="inline-flex items-center gap-2 mt-8 p-1 rounded-full border border-white/10 bg-white/[0.02]">
            <span className="px-5 py-2 rounded-full text-sm font-bold bg-indigo-600 text-white">All Reviews</span>
            <span className="px-5 py-2 rounded-full text-sm font-medium text-slate-400 flex items-center gap-1.5">
              <Stethoscope className="w-3.5 h-3.5" /> Doctors
            </span>
            <span className="px-5 py-2 rounded-full text-sm font-medium text-slate-400 flex items-center gap-1.5">
              <HeartPulse className="w-3.5 h-3.5" /> Patients
            </span>
          </div>
        </div>

        {/* Testimonial Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {TESTIMONIALS.map((t) => (
            <div key={t.name}
              className="group relative overflow-hidden rounded-[2rem] p-7 border border-white/[0.05] hover:border-white/10 transition-all duration-500"
              style={{ background: "rgba(10,18,38,0.7)", backdropFilter: "blur(20px)" }}>
              <div className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 w-48 h-48 rounded-full blur-[60px]"
                style={{ background: t.role === "doctor" ? "rgba(99,102,241,0.08)" : "rgba(6,182,212,0.08)" }} />

              <div className="relative z-10">
                {/* Role badge */}
                <div className="flex items-center justify-between mb-5">
                  <span className={`text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full border ${t.role === "doctor"
                    ? "border-indigo-500/30 text-indigo-400 bg-indigo-500/5"
                    : "border-cyan-500/30 text-cyan-400 bg-cyan-500/5"}`}>
                    {t.role === "doctor" ? "🩺 Doctor" : "🏥 Patient"}
                  </span>
                  <div className="flex gap-0.5">
                    {Array.from({ length: t.stars }).map((_, i) => (
                      <Star key={i} className="w-3.5 h-3.5 fill-yellow-400 text-yellow-400" />
                    ))}
                  </div>
                </div>

                {/* Quote icon */}
                <Quote className="w-8 h-8 text-slate-700 mb-3" />

                {/* Highlighted snippet */}
                <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full mb-4 text-xs font-bold ${t.role === "doctor"
                  ? "bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                  : "bg-cyan-500/10 text-cyan-300 border border-cyan-500/20"}`}>
                  <CheckCircle2 className="w-3 h-3" />
                  {t.highlight}
                </div>

                <p className="text-slate-300 text-sm leading-relaxed mb-6 italic">
                  &ldquo;{t.quote}&rdquo;
                </p>

                {/* Author */}
                <div className="flex items-center gap-3 pt-4 border-t border-white/[0.04]">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-black text-white bg-gradient-to-br ${t.avatarColor} flex-shrink-0`}>
                    {t.avatar}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-white">{t.name}</p>
                    <p className="text-xs text-slate-500">{t.title}</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Aggregate rating */}
        <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-8 p-6 rounded-[1.5rem] border border-white/[0.05]"
          style={{ background: "rgba(255,255,255,0.01)" }}>
          <div className="text-center">
            <p className="text-5xl font-black text-white">4.9</p>
            <div className="flex gap-1 justify-center my-1">
              {Array.from({ length: 5 }).map((_, i) => (
                <Star key={i} className="w-4 h-4 fill-yellow-400 text-yellow-400" />
              ))}
            </div>
            <p className="text-xs text-slate-500 uppercase tracking-widest">Average Rating</p>
          </div>
          <div className="w-px h-16 bg-white/5 hidden sm:block" />
          <div className="text-center">
            <p className="text-5xl font-black text-emerald-400">10,000+</p>
            <p className="text-xs text-slate-500 uppercase tracking-widest mt-1">Verified Reviews</p>
          </div>
          <div className="w-px h-16 bg-white/5 hidden sm:block" />
          <div className="text-center">
            <p className="text-5xl font-black text-indigo-400">500+</p>
            <p className="text-xs text-slate-500 uppercase tracking-widest mt-1">Doctors Onboarded</p>
          </div>
          <div className="w-px h-16 bg-white/5 hidden sm:block" />
          <div className="text-center">
            <p className="text-5xl font-black text-cyan-400">50k+</p>
            <p className="text-xs text-slate-500 uppercase tracking-widest mt-1">Active Patients</p>
          </div>
        </div>
      </section>

      {/* ─── Bottom CTA ─── */}
      <section className="relative z-10 py-32 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <div className="heartbeat w-20 h-20 rounded-full flex items-center justify-center mx-auto border border-rose-500/30 mb-8"
            style={{ background: "rgba(244,63,94,0.1)", boxShadow: "0 0 40px rgba(244,63,94,0.2)" }}>
            <HeartPulse className="w-10 h-10 text-rose-400" />
          </div>
          <h2 className="text-4xl md:text-6xl font-black tracking-tighter mb-6">
            Your health deserves{" "}
            <span className="shimmer-text">intelligence.</span>
          </h2>
          <p className="text-xl text-slate-400 mb-10 max-w-lg mx-auto leading-relaxed">
            Join 50,000+ patients and 500+ physicians already using VitalMind&apos;s 7 AI agents to deliver smarter, faster, safer care.
          </p>
          <Link href="/register"
            className="group inline-flex items-center gap-3 px-10 py-5 rounded-2xl font-black text-lg text-white shadow-[0_0_60px_rgba(6,182,212,0.3)] hover:shadow-[0_0_80px_rgba(6,182,212,0.4)] transition-all hover:scale-[1.02]"
            style={{ background: "linear-gradient(135deg, #0891b2, #4f46e5, #7c3aed)" }}>
            Begin Your Journey
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </Link>
          <p className="mt-4 text-xs text-slate-600">No credit card required · HIPAA compliant · Free forever plan</p>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="relative z-10 border-t border-white/[0.04] py-10" style={{ background: "rgba(3,6,15,0.95)" }}>
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6 mb-8">
            <div className="flex items-center gap-2.5">
              <HeartPulse className="w-5 h-5 text-cyan-500" />
              <span className="text-lg font-black text-white">VitalMind</span>
            </div>
            <div className="flex flex-wrap justify-center gap-6 text-sm text-slate-500">
              {["Platform", "For Doctors", "For Patients", "Pricing", "Blog", "Privacy", "Terms", "HIPAA", "Security"].map((link) => (
                <a key={link} href="#" className="hover:text-white transition-colors">{link}</a>
              ))}
            </div>
          </div>
          <div className="pt-6 border-t border-white/[0.04] flex flex-col md:flex-row justify-between items-center gap-3">
            <p className="text-sm text-slate-600">
              © {new Date().getFullYear()} VitalMind Healthcare AI — All rights reserved.
            </p>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5 text-xs text-emerald-600">
                <ShieldCheck className="w-3.5 h-3.5" /> HIPAA Compliant
              </span>
              <span className="flex items-center gap-1.5 text-xs text-blue-600">
                <Lock className="w-3.5 h-3.5" /> AES-256 Encrypted
              </span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
