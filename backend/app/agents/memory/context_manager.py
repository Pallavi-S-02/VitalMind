"""
context_manager.py — Short-term conversation memory backed by Redis.

Stores the rolling conversation state for each session_id so that
agent nodes can maintain multi-turn awareness without holding state
in memory (horizontally scalable).

Key prefix: vitalmind:session:{session_id}
TTL:        Configurable via REDIS_SESSION_TTL (default 2 hours)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

_SESSION_PREFIX = "vitalmind:session:"
_DEFAULT_TTL_SECONDS = int(os.getenv("REDIS_SESSION_TTL", 7200))  # 2 hours


def _get_client() -> redis.Redis:
    """Return a Redis client from environment config."""
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )


class ContextManager:
    """
    Manages short-term agent state in Redis.

    Each session stores a JSON blob containing:
      - messages   : list of {role, content} dicts
      - context    : arbitrary enriched context dict
      - intent     : last classified intent
      - tool_outputs : accumulated tool results
    """

    def __init__(self, session_id: str, ttl: int = _DEFAULT_TTL_SECONDS) -> None:
        self.session_id = session_id
        self.ttl = ttl
        self._client = _get_client()
        self._key = f"{_SESSION_PREFIX}{session_id}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Load the full session state from Redis. Returns empty dict if missing."""
        try:
            raw = self._client.get(self._key)
            if raw:
                state = json.loads(raw)
                logger.debug("Loaded session %s (%d messages)", self.session_id, len(state.get("messages", [])))
                return state
        except Exception as exc:
            logger.warning("ContextManager.load failed for %s: %s", self.session_id, exc)
        return {
            "messages": [],
            "context": {},
            "intent": None,
            "tool_outputs": [],
        }

    def save(self, state: dict[str, Any]) -> None:
        """Persist the session state back to Redis, resetting TTL."""
        try:
            payload = {
                "messages": state.get("messages", []),
                "context": state.get("context", {}),
                "intent": state.get("intent"),
                "tool_outputs": state.get("tool_outputs", []),
            }
            self._client.setex(self._key, self.ttl, json.dumps(payload, default=str))
            logger.debug("Saved session %s to Redis.", self.session_id)
        except Exception as exc:
            logger.warning("ContextManager.save failed for %s: %s", self.session_id, exc)

    def append_message(self, role: str, content: str) -> None:
        """Convenience: add a single message to the session without loading everything."""
        state = self.load()
        state.setdefault("messages", []).append({"role": role, "content": content})
        self.save(state)

    def update_context(self, updates: dict[str, Any]) -> None:
        """Merge new key-value pairs into the session context dict."""
        state = self.load()
        state.setdefault("context", {}).update(updates)
        self.save(state)

    def clear(self) -> None:
        """Delete the session from Redis (e.g. on logout or explicit reset)."""
        try:
            self._client.delete(self._key)
            logger.info("Session %s cleared from Redis.", self.session_id)
        except Exception as exc:
            logger.warning("ContextManager.clear failed: %s", exc)

    def extend_ttl(self) -> None:
        """Reset the expiry timer without changing content."""
        try:
            self._client.expire(self._key, self.ttl)
        except Exception as exc:
            logger.warning("ContextManager.extend_ttl failed: %s", exc)

    def get_messages(self) -> list[dict[str, str]]:
        """Return just the message history list."""
        return self.load().get("messages", [])

    def get_context(self) -> dict[str, Any]:
        """Return the context dict."""
        return self.load().get("context", {})
