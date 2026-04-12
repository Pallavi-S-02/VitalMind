"use client";

import { useEffect, useState } from "react";
import { Search, User, Zap, LogOut, ChevronDown } from "lucide-react";
import { signOut } from "next-auth/react";
import { NotificationPanel } from "@/components/NotificationPanel";
import { GlobalSearchBar } from "@/components/GlobalSearchBar";

const ROLE_COLORS: Record<string, string> = {
  doctor: "from-indigo-500 to-purple-600",
  patient: "from-cyan-500 to-blue-600",
  nurse: "from-emerald-500 to-teal-600",
  admin: "from-rose-500 to-red-600",
};

interface HeaderProps {
  user: {
    name?: string | null;
    email?: string | null;
    role?: string;
  };
}

export function Header({ user }: HeaderProps) {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (isProfileOpen && !target.closest('.profile-dropdown-container')) {
        setIsProfileOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isProfileOpen]);

  const roleGradient = ROLE_COLORS[user.role || "patient"] || ROLE_COLORS.patient;
  const initials = user.name
    ? user.name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()
    : "?";

  return (
    <>
      <header
        className="h-16 flex items-center justify-between px-6 z-40 relative border-b border-white/[0.05] flex-shrink-0"
        style={{ background: "rgba(6,13,31,0.95)", backdropFilter: "blur(20px)" }}
      >
        {/* Search */}
        <div className="flex items-center flex-1 max-w-md">
          <button
            onClick={() => setIsSearchOpen(true)}
            className="group w-full flex items-center gap-3 px-4 py-2 rounded-xl text-sm text-slate-500 hover:text-slate-300 transition-all duration-200 border border-white/[0.06] hover:border-white/[0.1]"
            style={{ background: "rgba(255,255,255,0.03)" }}
          >
            <Search className="w-4 h-4 text-slate-600 group-hover:text-cyan-400 transition-colors" />
            <span>Search patients, reports...</span>
            <div className="ml-auto flex items-center gap-1">
              <kbd className="hidden sm:flex h-5 items-center gap-0.5 rounded border border-white/10 bg-white/5 px-1.5 font-mono text-[10px] text-slate-600">
                <span>⌘</span>K
              </kbd>
            </div>
          </button>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3 ml-4">
          {/* Live clock */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/[0.05]"
            style={{ background: "rgba(255,255,255,0.03)" }}>
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
            </span>
            <span className="text-xs font-mono text-slate-500">
              {time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>

          {/* AI badge */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-cyan-500/20"
            style={{ background: "rgba(6,182,212,0.06)" }}>
            <Zap className="w-3 h-3 text-cyan-400" />
            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest">AI Active</span>
          </div>

          {/* Notifications */}
          <NotificationPanel />

          {/* Profile Dropdown */}
          <div className="relative profile-dropdown-container">
            <button
              onClick={() => setIsProfileOpen(!isProfileOpen)}
              className="flex items-center gap-2 p-1 rounded-full hover:bg-white/5 transition-colors outline-none"
            >
              <div className={`flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br ${roleGradient} text-white text-xs font-black shadow-[0_0_12px_rgba(6,182,212,0.3)] hover:scale-105 transition-transform`}>
                {initials}
              </div>
              <ChevronDown className={`w-3.5 h-3.5 text-slate-500 transition-transform duration-200 ${isProfileOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {isProfileOpen && (
              <div 
                className="absolute top-full right-0 mt-2 w-64 rounded-2xl border border-white/[0.08] shadow-2xl overflow-hidden z-50 animate-in fade-in zoom-in duration-200"
                style={{ background: "rgba(10,18,40,0.98)", backdropFilter: "blur(20px)" }}
              >
                <div className="p-4 border-b border-white/[0.05]">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center bg-gradient-to-br ${roleGradient} text-white text-sm font-black`}>
                      {initials}
                    </div>
                    <div className="flex flex-col min-w-0">
                      <p className="text-sm font-semibold text-white truncate px-0">{user.name}</p>
                      <p className="text-xs text-slate-500 truncate mt-0.5">{user.email}</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest bg-gradient-to-r ${roleGradient} bg-clip-text text-transparent border border-white/10`}>
                      {user.role}
                    </span>
                  </div>
                </div>

                <div className="p-2">
                  <button
                    onClick={() => signOut({ callbackUrl: '/login' })}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-white/[0.05] transition-all group"
                  >
                    <div className="p-1.5 rounded-lg bg-white/5 group-hover:bg-rose-500/10 transition-colors">
                      <LogOut className="w-4 h-4 group-hover:text-rose-400" />
                    </div>
                    <span>Sign out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      <GlobalSearchBar
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
      />
    </>
  );
}
