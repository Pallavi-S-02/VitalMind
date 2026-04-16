"""
notification_stream.py — Socket.IO WebSocket handler for real-time notifications.

Namespace: /notifications

Rooms:
  user:<user_id>   — Personal notification room (one per authenticated user)

Events (server → client):
  new_notification      — A new notification has been dispatched
  unread_count          — Current unread count (sent on connect + on any read)

Events (client → server):
  mark_read             — Mark a specific notification as read
  mark_all_read         — Mark all notifications for the user as read
  get_unread_count      — Request current unread count
"""

from __future__ import annotations

import logging

from app.websocket import socketio

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Connection / disconnection
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on("connect", namespace="/notifications")
def handle_notification_connect(auth):
    """
    Authenticate and join the user's personal notification room.
    Sends current unread count immediately on connect.
    """
    from app.services.auth_service import AuthService
    from flask_socketio import join_room, emit

    from flask_socketio import ConnectionRefusedError
    if not auth or "token" not in auth:
        logger.warning("NotificationWS: connection refused — no token")
        raise ConnectionRefusedError("no token")

    try:
        token = auth["token"]
        if token.startswith("Bearer "):
            token = token[7:]

        decoded = AuthService.decode_token(token)
        if isinstance(decoded, str):
            raise ValueError(decoded)
        user_id = decoded.get("sub")
        if not user_id:
            raise ConnectionRefusedError("invalid user_id")

        # Join personal room
        join_room(f"user:{user_id}")
        logger.info("NotificationWS: user %s joined room user:%s", user_id, user_id)

        # Send unread count immediately
        try:
            from app.services.notification_service import NotificationService
            count = NotificationService.get_unread_count(user_id)
        except Exception:
            count = 0

        emit("unread_count", {"count": count, "user_id": user_id})
        emit("notification_connected", {"status": "connected", "user_id": user_id})
        return True

    except Exception as exc:
        logger.warning("NotificationWS: connection refused — invalid token: %s", exc)
        raise ConnectionRefusedError(str(exc))


@socketio.on("disconnect", namespace="/notifications")
def handle_notification_disconnect():
    from flask import request
    logger.info("NotificationWS: client SID %s disconnected", request.sid)


# ─────────────────────────────────────────────────────────────────────────────
# Client-initiated events
# ─────────────────────────────────────────────────────────────────────────────

@socketio.on("mark_read", namespace="/notifications")
def handle_mark_read(data):
    """Mark a single notification as read and broadcast updated unread count."""
    from flask_socketio import emit
    from app.services.auth_service import AuthService
    from flask import request

    notification_id = data.get("notification_id")
    token = data.get("token", "")
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        decoded = AuthService.decode_token(token)
        if isinstance(decoded, str):
            raise ValueError(decoded)
        user_id = decoded.get("sub")
        if not user_id or not notification_id:
            return

        from app.services.notification_service import NotificationService
        NotificationService.mark_read(notification_id, user_id)
        count = NotificationService.get_unread_count(user_id)

        emit("unread_count", {"count": count}, room=f"user:{user_id}", namespace="/notifications")
        emit("notification_read", {"notification_id": notification_id})
        logger.debug("NotificationWS: notification %s marked read by user %s", notification_id, user_id)

    except Exception as exc:
        logger.error("NotificationWS: mark_read failed: %s", exc)


@socketio.on("mark_all_read", namespace="/notifications")
def handle_mark_all_read(data):
    """Mark all notifications as read for the authenticated user."""
    from flask_socketio import emit
    from app.services.auth_service import AuthService

    token = data.get("token", "")
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        decoded = AuthService.decode_token(token)
        if isinstance(decoded, str):
            raise ValueError(decoded)
        user_id = decoded.get("sub")
        if not user_id:
            return

        from app.services.notification_service import NotificationService
        updated = NotificationService.mark_all_read(user_id)

        emit("unread_count", {"count": 0}, room=f"user:{user_id}", namespace="/notifications")
        emit("all_notifications_read", {"updated": updated})
        logger.info("NotificationWS: %d notifications marked read for user %s", updated, user_id)

    except Exception as exc:
        logger.error("NotificationWS: mark_all_read failed: %s", exc)


@socketio.on("get_unread_count", namespace="/notifications")
def handle_get_unread_count(data):
    """Return current unread notification count."""
    from flask_socketio import emit
    from app.services.auth_service import AuthService

    token = data.get("token", "")
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        decoded = AuthService.decode_token(token)
        if isinstance(decoded, str):
            raise ValueError(decoded)
        user_id = decoded.get("sub")
        if not user_id:
            return

        from app.services.notification_service import NotificationService
        count = NotificationService.get_unread_count(user_id)
        emit("unread_count", {"count": count})

    except Exception as exc:
        logger.error("NotificationWS: get_unread_count failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: push a notification to a user's room from server-side code
# ─────────────────────────────────────────────────────────────────────────────

def push_notification_to_user(user_id: str, notification: dict) -> None:
    """
    Utility: emit a notification event directly to a user's Socket.IO room.
    Called by NotificationService._deliver_in_app() and external triggers.
    """
    try:
        socketio.emit(
            "new_notification",
            notification,
            room=f"user:{user_id}",
            namespace="/notifications",
        )
    except Exception as exc:
        logger.error("NotificationStream: push to user %s failed: %s", user_id, exc)
