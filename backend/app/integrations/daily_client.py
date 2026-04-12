"""
daily_client.py — Daily.co REST API integration client.

Docs: https://docs.daily.co/reference

Key operations:
  - Create rooms (video call rooms per appointment)
  - Generate meeting tokens (time-limited, role-specific)
  - Get room info / participant count
  - Delete / end rooms

All requests are authenticated with the `DAILY_API_KEY` env var.
Gracefully degrades when the key is absent (e.g. dev environments).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DAILY_API_BASE = "https://api.daily.co/v1"
_ROOM_EXPIRY_SECONDS = 3600    # Rooms auto-close after 1 hour of no activity
_TOKEN_EXPIRY_SECONDS = 7200   # Meeting tokens valid for 2 hours


class DailyClient:
    """Thin synchronous wrapper around the Daily.co REST API."""

    def __init__(self) -> None:
        self.api_key = os.getenv("DAILY_API_KEY", "")
        if not self.api_key:
            logger.warning(
                "DailyClient: DAILY_API_KEY not set — all calls will be no-ops. "
                "Set DAILY_API_KEY in .env to enable video calls."
            )
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, **kwargs) -> Optional[dict]:
        if not self._is_configured():
            return None
        try:
            resp = self._session.get(f"{DAILY_API_BASE}{path}", timeout=10, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("DailyClient GET %s failed: %s", path, exc)
            return None

    def _post(self, path: str, payload: dict, **kwargs) -> Optional[dict]:
        if not self._is_configured():
            return None
        try:
            resp = self._session.post(
                f"{DAILY_API_BASE}{path}", json=payload, timeout=10, **kwargs
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("DailyClient POST %s failed: %s", path, exc)
            return None

    def _delete(self, path: str) -> bool:
        if not self._is_configured():
            return False
        try:
            resp = self._session.delete(f"{DAILY_API_BASE}{path}", timeout=10)
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("DailyClient DELETE %s failed: %s", path, exc)
            return False

    # ─────────────────────────────────────────────────────────────
    # Room management
    # ─────────────────────────────────────────────────────────────

    def create_room(
        self,
        name: str,
        privacy: str = "private",
        max_participants: int = 10,
        exp_seconds: Optional[int] = None,
        enable_recording: bool = False,
    ) -> Optional[dict]:
        """
        Create a Daily room.

        Returns dict with: id, name, url, created_at, privacy, config
        """
        exp = int(time.time()) + (exp_seconds or _ROOM_EXPIRY_SECONDS)

        properties: dict = {
            "max_participants": max_participants,
            "exp": exp,
            "enable_chat": True,
            "enable_knocking": True,
            "start_video_off": False,
            "start_audio_off": False,
        }

        if enable_recording:
            properties["enable_recording"] = "cloud"

        payload = {
            "name": name,
            "privacy": privacy,
            "properties": properties,
        }

        result = self._post("/rooms", payload)
        if result:
            logger.info("DailyClient: created room '%s' url=%s", name, result.get("url"))
        return result

    def get_room(self, name: str) -> Optional[dict]:
        """Get info for an existing room."""
        return self._get(f"/rooms/{name}")

    def delete_room(self, name: str) -> bool:
        """Permanently delete a room."""
        ok = self._delete(f"/rooms/{name}")
        if ok:
            logger.info("DailyClient: deleted room '%s'", name)
        return ok

    def list_rooms(self) -> list[dict]:
        """List all rooms in the account."""
        result = self._get("/rooms")
        return result.get("data", []) if result else []

    # ─────────────────────────────────────────────────────────────
    # Meeting tokens
    # ─────────────────────────────────────────────────────────────

    def create_meeting_token(
        self,
        room_name: str,
        user_id: str,
        user_name: str,
        is_owner: bool = False,
        exp_seconds: Optional[int] = None,
    ) -> Optional[str]:
        """
        Generate a time-limited meeting token for a specific room.

        is_owner=True gives the participant moderator controls
        (mute others, end call for all, etc.).

        Returns token string, or None on failure.
        """
        exp = int(time.time()) + (exp_seconds or _TOKEN_EXPIRY_SECONDS)

        payload = {
            "properties": {
                "room_name": room_name,
                "user_id": user_id,
                "user_name": user_name,
                "is_owner": is_owner,
                "exp": exp,
                "enable_recording": False,
                # Keep participants from changing their own names
                "user_name_readonly": False,
            }
        }

        result = self._post("/meeting-tokens", payload)
        if result:
            token = result.get("token")
            logger.info(
                "DailyClient: token created for user %s in room %s (owner=%s)",
                user_id, room_name, is_owner,
            )
            return token
        return None

    # ─────────────────────────────────────────────────────────────
    # Presence / analytics
    # ─────────────────────────────────────────────────────────────

    def get_room_presence(self, room_name: str) -> Optional[dict]:
        """
        Get current participant count for a room.
        Returns: { total_count: int, data: [participant_info, ...] }
        """
        return self._get(f"/presence/{room_name}")


# Module-level singleton
_client: Optional[DailyClient] = None


def get_daily_client() -> DailyClient:
    global _client
    if _client is None:
        _client = DailyClient()
    return _client
