"use client";

/**
 * notificationStore.ts — Zustand store for real-time notifications.
 *
 * Manages:
 *   - Socket.IO connection to /notifications namespace
 *   - Notification list (paginated from REST API)
 *   - Unread badge count (from WS + REST)
 *   - Mark read / mark all read
 *   - Push subscription registration
 */

import { create } from "zustand";
import { io, Socket } from "socket.io-client";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface AppNotification {
  id: string;
  title: string;
  body: string;
  type: string;
  is_read: boolean;
  action_data?: {
    action_url?: string;
    priority?: string;
    metadata?: Record<string, unknown>;
    [key: string]: unknown;
  };
  created_at: string;
}

interface NotificationState {
  // Connection
  socket: Socket | null;
  isConnected: boolean;

  // Data
  notifications: AppNotification[];
  unreadCount: number;
  totalCount: number;

  // UI
  isLoading: boolean;
  hasMore: boolean;
  currentPage: number;

  // Actions
  connect: (token: string) => void;
  disconnect: () => void;
  loadNotifications: (token: string, page?: number, unreadOnly?: boolean) => Promise<void>;
  markRead: (id: string, token: string) => Promise<void>;
  markAllRead: (token: string) => Promise<void>;
  deleteNotification: (id: string, token: string) => Promise<void>;
  setPushSubscription: (subscription: PushSubscription, token: string) => Promise<void>;
  refreshUnreadCount: (token: string) => Promise<void>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export const useNotificationStore = create<NotificationState>((set, get) => ({
  socket: null,
  isConnected: false,
  notifications: [],
  unreadCount: 0,
  totalCount: 0,
  isLoading: false,
  hasMore: false,
  currentPage: 1,

  // ── WebSocket connection ───────────────────────────────────────────────────

  connect: (token: string) => {
    const existing = get().socket;
    if (existing?.connected) return;

    const socket = io(`${API_URL}/notifications`, {
      path: "/socket.io",
      auth: { token },
      transports: ["websocket", "polling"],
    });

    socket.on("connect", () => {
      set({ isConnected: true });
    });

    socket.on("disconnect", () => {
      set({ isConnected: false });
    });

    socket.on("unread_count", (data: { count: number }) => {
      set({ unreadCount: data.count });
    });

    socket.on("new_notification", (notif: AppNotification) => {
      set((s) => ({
        notifications: [notif, ...s.notifications],
        unreadCount: s.unreadCount + 1,
        totalCount: s.totalCount + 1,
      }));
    });

    socket.on("notification_read", (data: { notification_id: string }) => {
      set((s) => ({
        notifications: s.notifications.map((n) =>
          n.id === data.notification_id ? { ...n, is_read: true } : n
        ),
      }));
    });

    socket.on("all_notifications_read", () => {
      set((s) => ({
        notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
        unreadCount: 0,
      }));
    });

    set({ socket });
  },

  disconnect: () => {
    get().socket?.disconnect();
    set({ socket: null, isConnected: false });
  },

  // ── REST operations ────────────────────────────────────────────────────────

  loadNotifications: async (token, page = 1, unreadOnly = false) => {
    set({ isLoading: true });
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: "20",
        ...(unreadOnly ? { unread: "true" } : {}),
      });
      const res = await fetch(`${API_URL}/api/v1/notifications?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;

      const data = await res.json();
      const newNotifs: AppNotification[] = data.notifications || [];

      set((s) => ({
        notifications: page === 1 ? newNotifs : [...s.notifications, ...newNotifs],
        totalCount: data.total || 0,
        unreadCount: data.unread_count ?? s.unreadCount,
        currentPage: page,
        hasMore: newNotifs.length === 20,
        isLoading: false,
      }));
    } catch {
      set({ isLoading: false });
    }
  },

  markRead: async (id, token) => {
    // Optimistic update
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, is_read: true } : n
      ),
      unreadCount: Math.max(0, s.unreadCount - 1),
    }));

    try {
      await fetch(`${API_URL}/api/v1/notifications/${id}/read`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      // Also emit via WebSocket for cross-tab sync
      get().socket?.emit("mark_read", { notification_id: id, token });
    } catch {
      /* silently revert would be complex — acceptable to leave optimistic update */
    }
  },

  markAllRead: async (token) => {
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
      unreadCount: 0,
    }));

    try {
      await fetch(`${API_URL}/api/v1/notifications/read-all`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      get().socket?.emit("mark_all_read", { token });
    } catch {
      /* noop */
    }
  },

  deleteNotification: async (id, token) => {
    set((s) => ({
      notifications: s.notifications.filter((n) => n.id !== id),
      totalCount: Math.max(0, s.totalCount - 1),
    }));

    try {
      await fetch(`${API_URL}/api/v1/notifications/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      /* noop */
    }
  },

  setPushSubscription: async (subscription, token) => {
    try {
      const sub = subscription.toJSON();
      await fetch(`${API_URL}/api/v1/notifications/subscribe`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          endpoint: sub.endpoint,
          expirationTime: sub.expirationTime ?? null,
          keys: { p256dh: sub.keys?.p256dh, auth: sub.keys?.auth },
        }),
      });
    } catch {
      /* push subscription is best-effort */
    }
  },

  refreshUnreadCount: async (token) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/notifications/unread-count`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ unreadCount: data.count ?? 0 });
      }
    } catch {
      /* noop */
    }
  },
}));
