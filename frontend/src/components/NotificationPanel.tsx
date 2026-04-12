"use client";

/**
 * NotificationPanel.tsx  — Real-time notification bell + dropdown panel.
 *
 * Features:
 *  - Animated bell icon with unread badge count
 *  - Click-outside-to-close dropdown
 *  - Live notification feed (paginated, load more)
 *  - Per-notification mark-read, delete actions
 *  - "Mark all read" button
 *  - Type-based icon and colour coding
 *  - Relative time-ago display
 *  - Connects to /notifications Socket.IO namespace on mount
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  Bell,
  BellRing,
  X,
  CheckCheck,
  Trash2,
  Calendar,
  Pill,
  Activity,
  AlertTriangle,
  FlaskConical,
  MessageSquare,
  Info,
  Loader2,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useNotificationStore, AppNotification } from "@/store/notificationStore";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function NotifIcon({ type }: { type: string }) {
  const cls = "h-4 w-4 flex-shrink-0";
  if (type === "appointment_reminder") return <Calendar className={cn(cls, "text-blue-400")} />;
  if (type === "medication_reminder")  return <Pill className={cn(cls, "text-violet-400")} />;
  if (type === "vitals_alert")         return <Activity className={cn(cls, "text-orange-400")} />;
  if (type === "triage_alert")         return <AlertTriangle className={cn(cls, "text-red-400")} />;
  if (type === "lab_result_ready")     return <FlaskConical className={cn(cls, "text-emerald-400")} />;
  if (type === "doctor_message")       return <MessageSquare className={cn(cls, "text-cyan-400")} />;
  return <Info className={cn(cls, "text-gray-400")} />;
}

function priorityBorder(type: string): string {
  if (type === "triage_alert")         return "border-l-red-500";
  if (type === "vitals_alert")         return "border-l-orange-500";
  if (type === "appointment_reminder") return "border-l-blue-500";
  if (type === "medication_reminder")  return "border-l-violet-500";
  if (type === "lab_result_ready")     return "border-l-emerald-500";
  if (type === "doctor_message")       return "border-l-cyan-500";
  return "border-l-gray-600";
}

// ─────────────────────────────────────────────────────────────────────────────
// Notification item
// ─────────────────────────────────────────────────────────────────────────────

function NotificationItem({
  notif,
  onRead,
  onDelete,
  onNavigate,
}: {
  notif: AppNotification;
  onRead: (id: string) => void;
  onDelete: (id: string) => void;
  onNavigate: (url?: string) => void;
}) {
  const actionUrl = notif.action_data?.action_url as string | undefined;

  return (
    <div
      className={cn(
        "group relative flex gap-3 px-4 py-3 border-b border-white/5 border-l-2 transition-all cursor-pointer",
        priorityBorder(notif.type),
        notif.is_read
          ? "bg-transparent hover:bg-white/3"
          : "bg-white/5 hover:bg-white/8"
      )}
      onClick={() => {
        if (!notif.is_read) onRead(notif.id);
        if (actionUrl) onNavigate(actionUrl);
      }}
    >
      {/* Unread dot */}
      {!notif.is_read && (
        <span className="absolute top-3.5 right-3 h-1.5 w-1.5 rounded-full bg-cyan-400 flex-shrink-0" />
      )}

      {/* Icon */}
      <div className="mt-0.5 p-1.5 rounded-lg bg-white/8 flex-shrink-0 h-fit">
        <NotifIcon type={notif.type} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className={cn("text-sm leading-snug", notif.is_read ? "text-gray-300" : "text-white font-medium")}>
          {notif.title}
        </p>
        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2 leading-relaxed">
          {notif.body}
        </p>
        <p className="text-[10px] text-gray-600 mt-1">{timeAgo(notif.created_at)}</p>
      </div>

      {/* Actions (visible on hover) */}
      <div className="absolute right-3 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-1">
        {!notif.is_read && (
          <button
            onClick={(e) => { e.stopPropagation(); onRead(notif.id); }}
            title="Mark as read"
            className="p-1 rounded-lg hover:bg-white/15 text-gray-400 hover:text-white transition-colors"
          >
            <CheckCheck className="h-3.5 w-3.5" />
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(notif.id); }}
          title="Delete"
          className="p-1 rounded-lg hover:bg-red-900/30 text-gray-500 hover:text-red-400 transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export function NotificationPanel() {
  const { data: session } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const panelRef = useRef<HTMLDivElement>(null);

  const {
    connect,
    disconnect,
    isConnected,
    notifications,
    unreadCount,
    isLoading,
    hasMore,
    currentPage,
    loadNotifications,
    markRead,
    markAllRead,
    deleteNotification,
    refreshUnreadCount,
  } = useNotificationStore();

  // Connect WS + initial data
  useEffect(() => {
    if (!session?.accessToken) return;
    connect(session.accessToken);
    refreshUnreadCount(session.accessToken);
    return () => disconnect();
  }, [session?.accessToken]);

  // Load notifications when panel opens
  useEffect(() => {
    if (open && session?.accessToken) {
      loadNotifications(session.accessToken, 1, filter === "unread");
    }
  }, [open, filter, session?.accessToken]);

  // Close on outside click
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const handleMarkRead = useCallback(
    (id: string) => session?.accessToken && markRead(id, session.accessToken),
    [session?.accessToken]
  );

  const handleDelete = useCallback(
    (id: string) => session?.accessToken && deleteNotification(id, session.accessToken),
    [session?.accessToken]
  );

  const handleMarkAllRead = useCallback(() => {
    if (session?.accessToken) markAllRead(session.accessToken);
  }, [session?.accessToken]);

  const handleNavigate = useCallback((url?: string) => {
    if (url) { router.push(url); setOpen(false); }
  }, [router]);

  const handleLoadMore = useCallback(() => {
    if (session?.accessToken && hasMore && !isLoading) {
      loadNotifications(session.accessToken, currentPage + 1, filter === "unread");
    }
  }, [session?.accessToken, hasMore, isLoading, currentPage, filter]);

  const hasUnread = unreadCount > 0;

  return (
    <div ref={panelRef} className="relative">
      {/* ── Bell button ───────────────────────────────────────────── */}
      <button
        id="notification-bell"
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition-all"
        aria-label="Notifications"
      >
        {hasUnread ? (
          <BellRing className="h-5 w-5 text-cyan-400 animate-[wiggle_1s_ease-in-out_infinite]" />
        ) : (
          <Bell className="h-5 w-5" />
        )}

        {/* Badge */}
        {hasUnread && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center px-1 rounded-full bg-red-500 text-white text-[10px] font-bold border-2 border-gray-950 tabular-nums leading-none">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {/* ── Panel ─────────────────────────────────────────────────── */}
      {open && (
        <div
          className="absolute right-0 top-12 w-96 max-h-[600px] flex flex-col bg-gray-900 border border-white/10 rounded-2xl shadow-2xl shadow-black/50 overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 flex-shrink-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-white">Notifications</h3>
              {hasUnread && (
                <span className="px-1.5 py-0.5 rounded-full bg-cyan-600/30 text-cyan-400 text-[10px] font-bold">
                  {unreadCount} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {hasUnread && (
                <button
                  onClick={handleMarkAllRead}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <CheckCheck className="h-3.5 w-3.5" />
                  All read
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/10 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Filter tabs */}
          <div className="flex gap-1 px-4 py-2 flex-shrink-0 border-b border-white/5">
            {(["all", "unread"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all",
                  filter === f
                    ? "bg-cyan-600/20 text-cyan-400 border border-cyan-600/30"
                    : "text-gray-500 hover:text-gray-300"
                )}
              >
                {f}
              </button>
            ))}
          </div>

          {/* List */}
          <div className="overflow-y-auto flex-1">
            {isLoading && notifications.length === 0 ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="h-6 w-6 text-cyan-400 animate-spin" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16">
                <Bell className="h-8 w-8 text-gray-700 mb-2" />
                <p className="text-sm text-gray-500">
                  {filter === "unread" ? "No unread notifications" : "You're all caught up!"}
                </p>
              </div>
            ) : (
              <>
                {notifications.map((n) => (
                  <NotificationItem
                    key={n.id}
                    notif={n}
                    onRead={handleMarkRead}
                    onDelete={handleDelete}
                    onNavigate={handleNavigate}
                  />
                ))}

                {hasMore && (
                  <div className="flex justify-center py-3">
                    <button
                      onClick={handleLoadMore}
                      disabled={isLoading}
                      className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-cyan-400 transition-colors"
                    >
                      {isLoading
                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        : <ChevronDown className="h-3.5 w-3.5" />}
                      Load more
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-white/5 flex-shrink-0">
            <div className={cn(
              "flex items-center gap-1.5 text-[10px] font-medium",
              isConnected ? "text-emerald-400" : "text-gray-600"
            )}>
              <span className={cn(
                "w-1.5 h-1.5 rounded-full",
                isConnected ? "bg-emerald-400" : "bg-gray-600"
              )} />
              {isConnected ? "Live" : "Offline"}
            </div>
            <button
              onClick={() => handleNavigate("/settings/notifications")}
              className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
            >
              Preferences →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
