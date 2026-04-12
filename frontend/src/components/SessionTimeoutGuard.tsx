"use client";

import { useEffect, useRef, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { usePathname } from "next/navigation";

// 15 minutes in milliseconds
const TIMEOUT_MS = 15 * 60 * 1000;

export function SessionTimeoutGuard({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const pathname = usePathname();
  const [isWarningActive, setIsWarningActive] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const resetTimer = () => {
    if (status !== "authenticated") return;
    
    // Clear existing timer
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Set new timer
    timeoutRef.current = setTimeout(() => {
      // In a real high-security app, we might want to ping the server to kill the session instantly
      // Here we invoke NextAuth signOut to clear local state and unauth the cookie
      signOut({ callbackUrl: "/login?reason=timeout" });
    }, TIMEOUT_MS);
  };

  useEffect(() => {
    // Only track if authenticated and not on login pages
    if (status !== "authenticated" || pathname.startsWith("/login") || pathname.startsWith("/register")) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      return;
    }

    // Set initial timer
    resetTimer();

    // Events that constitute user activity
    const activityEvents = [
      "mousedown",
      "mousemove",
      "keydown",
      "scroll",
      "touchstart",
      "wheel"
    ];

    // Create a throttled event listener to avoid thrashing
    let throttleTimer = false;
    const handleActivity = () => {
      if (throttleTimer) return;
      
      throttleTimer = true;
      setTimeout(() => {
        resetTimer();
        throttleTimer = false;
      }, 1000); // Only reset timer max once per second
    };

    // Attach listeners
    activityEvents.forEach((eventName) => {
      window.addEventListener(eventName, handleActivity, { passive: true });
    });

    // Cleanup
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      activityEvents.forEach((eventName) => {
        window.removeEventListener(eventName, handleActivity);
      });
    };
  }, [status, pathname]); // Re-run if auth status or route changes

  return <>{children}</>;
}
