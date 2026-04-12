"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  Calendar,
  MessageSquare,
  Settings,
  Stethoscope,
  FileText,
  Pill,
  Sparkles,
  Activity,
  HeartPulse,
  Bot,
  ChevronRight,
} from "lucide-react";

interface SidebarProps {
  role: string;
}

export function Sidebar({ role }: SidebarProps) {
  const pathname = usePathname();

  const getLinks = () => {
    if (role === "doctor") {
      return [
        { href: "/doctor/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { href: "/doctor/schedule", label: "Schedule", icon: Calendar },
        { href: "/doctor/patients", label: "Patients", icon: Users },
        { href: "/doctor/monitoring", label: "Monitoring", icon: HeartPulse },
        { href: "/doctor/messages", label: "Messages", icon: MessageSquare },
        { href: "/doctor/telemedicine", label: "Telemedicine", icon: Activity },
        { href: "/doctor/ai-assistant", label: "AI Assistant", icon: Sparkles },
        { href: "/doctor/settings", label: "Settings", icon: Settings },
      ];
    }

    if (role === "patient") {
      return [
        { href: "/patient/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { href: "/patient/appointments", label: "Appointments", icon: Calendar },
        { href: "/patient/ai-doctor", label: "AI Doctor", icon: Bot },
        { href: "/patient/messages", label: "Messages", icon: MessageSquare },
        { href: "/patient/reports", label: "Reports", icon: FileText },
        { href: "/patient/medications", label: "Medications", icon: Pill },
        { href: "/patient/vitals", label: "Vitals", icon: Activity },
        { href: "/patient/chat", label: "AI Assistant", icon: Sparkles },
        { href: "/patient/settings", label: "Settings", icon: Settings },
      ];
    }

    const baseLinks = [
      { href: `/${role}/dashboard`, label: "Dashboard", icon: LayoutDashboard },
      { href: `/${role}/appointments`, label: "Appointments", icon: Calendar },
    ];
    if (role === "admin") {
      baseLinks.push(
        { href: "/admin/doctors", label: "Doctors", icon: Stethoscope },
        { href: "/admin/patients", label: "Patients", icon: Users }
      );
    }
    baseLinks.push({ href: `/${role}/settings`, label: "Settings", icon: Settings });
    return baseLinks;
  };

  const links = getLinks();
  const mainLinks = links.slice(0, -1);
  const settingsLink = links[links.length - 1];

  return (
    <div
      className="w-64 flex-shrink-0 h-screen flex flex-col sticky top-0 border-r border-white/[0.05]"
      style={{
        background: "rgba(6,13,31,0.97)",
        backdropFilter: "blur(20px)",
      }}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-white/[0.05]">
        <div className="relative w-7 h-7 mr-2.5">
          <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_15px_rgba(6,182,212,0.4)]" />
          <HeartPulse className="absolute inset-0 m-auto w-3.5 h-3.5 text-white" style={{ animation: "heartbeat-icon 1.5s ease-in-out infinite" }} />
        </div>
        <span className="text-lg font-black tracking-tight text-white">VitalMind</span>
        <span className="ml-2 text-[9px] font-bold text-cyan-500 border border-cyan-500/30 px-1.5 py-0.5 rounded-full uppercase tracking-widest">
          {role}
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-slate-600 px-3 py-2 mt-1">
          Navigation
        </p>
        {mainLinks.map((link) => {
          const Icon = link.icon;
          const isActive = pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "group flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                isActive
                  ? "text-cyan-300"
                  : "text-slate-400 hover:text-slate-200"
              )}
              style={
                isActive
                  ? {
                      background: "linear-gradient(135deg, rgba(6,182,212,0.12), rgba(99,102,241,0.08))",
                      border: "1px solid rgba(6,182,212,0.2)",
                      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
                    }
                  : { border: "1px solid transparent" }
              }
            >
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    "w-7 h-7 rounded-lg flex items-center justify-center transition-all duration-200",
                    isActive
                      ? "shadow-[0_0_12px_rgba(6,182,212,0.3)]"
                      : "group-hover:bg-white/5"
                  )}
                  style={
                    isActive
                      ? { background: "linear-gradient(135deg, rgba(6,182,212,0.25), rgba(99,102,241,0.2))" }
                      : {}
                  }
                >
                  <Icon
                    className={cn(
                      "w-4 h-4 transition-colors",
                      isActive ? "text-cyan-400" : "text-slate-500 group-hover:text-slate-300"
                    )}
                  />
                </div>
                {link.label}
              </div>
              {isActive && (
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_rgba(6,182,212,0.8)]" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="px-3 pb-3">
        <div className="h-px bg-white/[0.04] mb-3" />
        <Link
          href={settingsLink.href}
          className={cn(
            "group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
            pathname.startsWith(settingsLink.href)
              ? "text-cyan-300"
              : "text-slate-400 hover:text-slate-200"
          )}
          style={
            pathname.startsWith(settingsLink.href)
              ? {
                  background: "linear-gradient(135deg, rgba(6,182,212,0.12), rgba(99,102,241,0.08))",
                  border: "1px solid rgba(6,182,212,0.2)",
                }
              : { border: "1px solid transparent" }
          }
        >
          <div className="w-7 h-7 rounded-lg flex items-center justify-center group-hover:bg-white/5 transition-all">
            <Settings className="w-4 h-4 text-slate-500 group-hover:text-slate-300" />
          </div>
          Settings
        </Link>
      </div>
    </div>
  );
}
