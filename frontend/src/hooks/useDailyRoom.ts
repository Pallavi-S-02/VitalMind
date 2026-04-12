/**
 * useDailyRoom.ts — React hook for Daily.co video call management.
 *
 * Manages:
 *   - Fetching/creating the room and meeting token from the backend
 *   - Initializing the @daily-co/daily-js iframe factory
 *   - Tracking participant state, connection status, microphone/camera toggles
 *   - Exposing leave() and endForAll() (doctor only)
 *
 * Architecture:
 *   We use Daily's "pre-built UI" via DailyIframe.createFrame() mounted into
 *   a provided container ref. This gives full video call UI with no additional
 *   WebRTC code needed. The hook wires the backend API and exposes minimal
 *   state needed to build the surrounding wrapper UI.
 */

"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export type CallStatus =
  | "idle"
  | "loading"
  | "joining"
  | "joined"
  | "leaving"
  | "ended"
  | "error";

export interface Participant {
  session_id: string;
  user_name: string;
  video: boolean;
  audio: boolean;
  local: boolean;
}

export interface DailyRoomInfo {
  room_name: string;
  room_url: string;
  token: string;
  is_owner: boolean;
}

export interface UseDailyRoomOptions {
  appointmentId: string;
  token: string;   // JWT auth token
  role: "doctor" | "patient";
  containerRef: React.RefObject<HTMLDivElement>;
  userName?: string;
}

export function useDailyRoom({
  appointmentId,
  token,
  role,
  containerRef,
  userName,
}: UseDailyRoomOptions) {
  const [callStatus, setCallStatus] = useState<CallStatus>("idle");
  const [roomInfo, setRoomInfo] = useState<DailyRoomInfo | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [isMicOn, setIsMicOn] = useState(true);
  const [isCamOn, setIsCamOn] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const callFrameRef = useRef<any>(null);

  // ── Step 1: Get / create the room, then get a join token ────────────────
  const initRoom = useCallback(async () => {
    setCallStatus("loading");
    setErrorMsg(null);

    try {
      const headers = {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      };

      // If doctor → create (idempotent) room first
      if (role === "doctor") {
        const createRes = await fetch(`${API_URL}/api/v1/telemedicine/rooms/create`, {
          method: "POST",
          headers,
          body: JSON.stringify({ appointment_id: appointmentId }),
        });
        if (!createRes.ok && createRes.status !== 200) {
          throw new Error("Failed to create room");
        }
      }

      // Get room info (both roles)
      const roomRes = await fetch(
        `${API_URL}/api/v1/telemedicine/appointments/${appointmentId}/room`,
        { headers }
      );
      if (!roomRes.ok) {
        const body = await roomRes.json().catch(() => ({}));
        throw new Error(body.error || "Room not yet available");
      }
      const roomData = await roomRes.json();
      const roomName: string = roomData.room_name;

      // Get meeting token
      const joinRes = await fetch(
        `${API_URL}/api/v1/telemedicine/rooms/${roomName}/join`,
        { method: "POST", headers }
      );
      if (!joinRes.ok) throw new Error("Failed to get meeting token");
      const joinData = await joinRes.json();

      setRoomInfo({
        room_name: roomName,
        room_url: joinData.room_url,
        token: joinData.token,
        is_owner: joinData.is_owner,
      });

      setCallStatus("joining");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to join call");
      setCallStatus("error");
    }
  }, [appointmentId, token, role]);

  // ── Step 2: Mount Daily iframe once we have room info ───────────────────
  useEffect(() => {
    if (callStatus !== "joining" || !roomInfo || !containerRef.current) return;

    let mounted = true;

    const mountFrame = async () => {
      try {
        // Dynamic import of @daily-co/daily-js to avoid SSR issues
        const DailyIframe = (await import("@daily-co/daily-js")).default;

        if (!mounted || !containerRef.current) return;

        const frame = DailyIframe.createFrame(containerRef.current, {
          iframeStyle: {
            width: "100%",
            height: "100%",
            border: "none",
            borderRadius: "16px",
          },
          showLeaveButton: false,   // We provide our own controls
          showFullscreenButton: true,
        });

        callFrameRef.current = frame;

        // Wire events
        frame
          .on("joined-meeting", () => {
            if (mounted) setCallStatus("joined");
          })
          .on("participant-updated", (event: any) => {
            if (!mounted) return;
            const p = event.participant;
            setParticipants((prev) => {
              const others = prev.filter((x) => x.session_id !== p.session_id);
              return [
                ...others,
                {
                  session_id: p.session_id,
                  user_name: p.user_name || "Unknown",
                  video: p.video,
                  audio: p.audio,
                  local: p.local,
                },
              ];
            });
            // Sync local mic/cam state
            if (p.local) {
              setIsMicOn(p.audio);
              setIsCamOn(p.video);
            }
          })
          .on("participant-left", (event: any) => {
            if (!mounted) return;
            setParticipants((prev) =>
              prev.filter((x) => x.session_id !== event.participant.session_id)
            );
          })
          .on("left-meeting", () => {
            if (mounted) setCallStatus("ended");
          })
          .on("error", (event: any) => {
            if (mounted) {
              setErrorMsg(event.errorMsg || "Call error");
              setCallStatus("error");
            }
          });

        // Join the call
        await frame.join({
          url: roomInfo.room_url,
          token: roomInfo.token,
          userName: userName,
          startVideoOff: false,
          startAudioOff: false,
        });
      } catch (err: any) {
        if (mounted) {
          setErrorMsg(err.message || "Failed to start call");
          setCallStatus("error");
        }
      }
    };

    mountFrame();

    return () => {
      mounted = false;
    };
  }, [callStatus, roomInfo, containerRef, userName]);

  // ── Controls ─────────────────────────────────────────────────────────────

  const toggleMic = useCallback(async () => {
    const frame = callFrameRef.current;
    if (!frame) return;
    if (isMicOn) {
      await frame.setLocalAudio(false);
    } else {
      await frame.setLocalAudio(true);
    }
    setIsMicOn((v) => !v);
  }, [isMicOn]);

  const toggleCam = useCallback(async () => {
    const frame = callFrameRef.current;
    if (!frame) return;
    if (isCamOn) {
      await frame.setLocalVideo(false);
    } else {
      await frame.setLocalVideo(true);
    }
    setIsCamOn((v) => !v);
  }, [isCamOn]);

  const leave = useCallback(async () => {
    setCallStatus("leaving");
    const frame = callFrameRef.current;
    if (frame) {
      await frame.leave();
      frame.destroy();
      callFrameRef.current = null;
    }
    setCallStatus("ended");
  }, []);

  const endForAll = useCallback(async () => {
    // Doctors only — end room for all participants
    if (!roomInfo) return;
    try {
      await fetch(`${API_URL}/api/v1/telemedicine/rooms/${roomInfo.room_name}/end`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ appointment_id: appointmentId }),
      });
    } catch (err) {
      console.error("End for all failed", err);
    }
    await leave();
  }, [roomInfo, token, appointmentId, leave]);

  return {
    callStatus,
    roomInfo,
    participants,
    isMicOn,
    isCamOn,
    errorMsg,
    initRoom,
    toggleMic,
    toggleCam,
    leave,
    endForAll,
  };
}
