"""
notifications.py — VitalMind Notifications API Blueprint (Step 17)

Endpoints
---------
POST /api/v1/notifications/subscribe
    Register a Web Push subscription for the authenticated user.

DELETE /api/v1/notifications/subscribe
    Unsubscribe (deactivate) a push subscription by endpoint.

GET  /api/v1/notifications
    List notifications for the authenticated user (paginated, filterable).

GET  /api/v1/notifications/unread-count
    Fast unread count.

POST /api/v1/notifications/<id>/read
    Mark a single notification as read.

POST /api/v1/notifications/read-all
    Mark all notifications as read.

DELETE /api/v1/notifications/<id>
    Soft-delete a notification.

GET  /api/v1/notifications/preferences
    Get current notification preferences.

PUT  /api/v1/notifications/preferences
    Update notification preferences.
"""

import logging
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from app.middleware.auth_middleware import require_auth

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")


# ─────────────────────────────────────────────────────────────────────────────
# Web Push subscription management
# ─────────────────────────────────────────────────────────────────────────────

@notifications_bp.route("/subscribe", methods=["POST"])
@require_auth
def subscribe_push():
    """
    Register a Web Push subscription for the authenticated user.

    Request JSON
    ------------
    {
        "endpoint":   "https://fcm.googleapis.com/fcm/send/...",
        "expirationTime": null,
        "keys": {
            "p256dh": "<base64url>",
            "auth":   "<base64url>"
        }
    }

    Response JSON: { "subscribed": true, "subscription_id": "uuid" }
    """
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint", "").strip()
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh", "").strip()
    auth = keys.get("auth", "").strip()

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "endpoint, keys.p256dh, and keys.auth are required"}), 400

    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from app.models.db import db
        from sqlalchemy import text

        # Upsert — re-activate if subscription already exists
        existing = db.session.execute(
            text("SELECT id FROM push_subscriptions WHERE endpoint = :ep AND user_id = :uid"),
            {"ep": endpoint, "uid": user_id},
        ).fetchone()

        if existing:
            db.session.execute(
                text("""
                    UPDATE push_subscriptions
                    SET is_active = true, updated_at = :now
                    WHERE id = :id
                """),
                {"id": str(existing.id), "now": datetime.now(timezone.utc).isoformat()},
            )
            db.session.commit()
            sub_id = str(existing.id)
        else:
            sub_id = str(uuid.uuid4())
            db.session.execute(
                text("""
                    INSERT INTO push_subscriptions (id, user_id, endpoint, p256dh, auth, is_active, created_at)
                    VALUES (:id, :uid, :ep, :p256dh, :auth, true, :now)
                """),
                {
                    "id": sub_id, "uid": user_id, "ep": endpoint,
                    "p256dh": p256dh, "auth": auth,
                    "now": datetime.now(timezone.utc).isoformat(),
                },
            )
            db.session.commit()

        logger.info("Notifications: push subscription registered for user %s (id=%s)", user_id, sub_id)
        return jsonify({"subscribed": True, "subscription_id": sub_id}), 201

    except Exception as exc:
        logger.exception("Notifications: push subscribe failed: %s", exc)
        return jsonify({"error": "Failed to register push subscription"}), 500


@notifications_bp.route("/subscribe", methods=["DELETE"])
@require_auth
def unsubscribe_push():
    """Deactivate a push subscription by endpoint URL."""
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint", "").strip()
    if not endpoint:
        return jsonify({"error": "endpoint is required"}), 400

    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None

    try:
        from app.models.db import db
        from sqlalchemy import text
        db.session.execute(
            text("""
                UPDATE push_subscriptions SET is_active = false
                WHERE endpoint = :ep AND user_id = :uid
            """),
            {"ep": endpoint, "uid": user_id},
        )
        db.session.commit()
        return jsonify({"unsubscribed": True}), 200
    except Exception as exc:
        logger.error("Notifications: unsubscribe failed: %s", exc)
        return jsonify({"error": "Failed to unsubscribe"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Notification listing & management
# ─────────────────────────────────────────────────────────────────────────────

@notifications_bp.route("", methods=["GET"])
@require_auth
def list_notifications():
    """
    List notifications for the authenticated user.

    Query params:
        page       (int, default=1)
        per_page   (int, default=20, max=50)
        unread     (bool, default=false) — only show unread
        type       (str) — filter by notification type

    Response JSON
    -------------
    {
        "notifications": [
            {
                "id": "uuid",
                "title": "Upcoming Appointment",
                "body": "You have an appointment with Dr. Smith...",
                "type": "appointment_reminder",
                "is_read": false,
                "action_data": { "action_url": "/patient/appointments" },
                "created_at": "2026-01-15T09:00:00Z"
            }
        ],
        "total": 42,
        "page": 1,
        "per_page": 20,
        "unread_count": 7
    }
    """
    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(1, int(request.args.get("per_page", 20))))
    unread_only = request.args.get("unread", "false").lower() == "true"
    type_filter = request.args.get("type", "").strip()
    offset = (page - 1) * per_page

    try:
        from app.models.db import db
        from sqlalchemy import text

        where_clauses = ["user_id = :uid", "deleted_at IS NULL"]
        params: dict = {"uid": user_id, "limit": per_page, "offset": offset}

        if unread_only:
            where_clauses.append("is_read = false")
        if type_filter:
            where_clauses.append("type = :type")
            params["type"] = type_filter

        where_sql = " AND ".join(where_clauses)

        rows = db.session.execute(
            text(f"""
                SELECT id, title, body, type, is_read, action_data, created_at
                FROM notifications
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).fetchall()

        total_row = db.session.execute(
            text(f"SELECT COUNT(*) FROM notifications WHERE {where_sql}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        ).fetchone()

        unread_row = db.session.execute(
            text("SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false AND deleted_at IS NULL"),
            {"uid": user_id},
        ).fetchone()

        notifs = []
        for r in rows:
            notifs.append({
                "id": str(r.id),
                "title": r.title,
                "body": r.body,
                "type": r.type,
                "is_read": r.is_read,
                "action_data": r.action_data or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return jsonify({
            "notifications": notifs,
            "total": int(total_row[0]) if total_row else 0,
            "page": page,
            "per_page": per_page,
            "unread_count": int(unread_row[0]) if unread_row else 0,
        }), 200

    except Exception as exc:
        logger.exception("Notifications: list failed: %s", exc)
        return jsonify({"error": "Failed to retrieve notifications"}), 500


@notifications_bp.route("/unread-count", methods=["GET"])
@require_auth
def get_unread_count():
    """Fast endpoint for unread notification count (used by header bell)."""
    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None
    if not user_id:
        return jsonify({"count": 0}), 200

    try:
        from app.services.notification_service import NotificationService
        count = NotificationService.get_unread_count(user_id)
        return jsonify({"count": count}), 200
    except Exception as exc:
        logger.error("Notifications: unread-count failed: %s", exc)
        return jsonify({"count": 0}), 200


@notifications_bp.route("/<notification_id>/read", methods=["POST"])
@require_auth
def mark_read(notification_id: str):
    """Mark a single notification as read."""
    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None

    try:
        from app.services.notification_service import NotificationService
        updated = NotificationService.mark_read(notification_id, user_id)
        count = NotificationService.get_unread_count(user_id)
        return jsonify({"updated": updated, "unread_count": count}), 200
    except Exception as exc:
        logger.error("Notifications: mark_read failed: %s", exc)
        return jsonify({"error": "Failed to mark notification as read"}), 500


@notifications_bp.route("/read-all", methods=["POST"])
@require_auth
def mark_all_read():
    """Mark all unread notifications as read for the authenticated user."""
    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None

    try:
        from app.services.notification_service import NotificationService
        updated = NotificationService.mark_all_read(user_id)
        return jsonify({"updated": updated, "unread_count": 0}), 200
    except Exception as exc:
        logger.error("Notifications: mark_all_read failed: %s", exc)
        return jsonify({"error": "Failed to mark all as read"}), 500


@notifications_bp.route("/<notification_id>", methods=["DELETE"])
@require_auth
def delete_notification(notification_id: str):
    """Soft-delete a notification (sets deleted_at timestamp)."""
    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None

    try:
        from app.models.db import db
        from sqlalchemy import text
        db.session.execute(
            text("""
                UPDATE notifications
                SET deleted_at = :now
                WHERE id = :id AND user_id = :uid
            """),
            {
                "now": datetime.now(timezone.utc).isoformat(),
                "id": notification_id,
                "uid": user_id,
            },
        )
        db.session.commit()
        return jsonify({"deleted": True}), 200
    except Exception as exc:
        logger.error("Notifications: delete failed: %s", exc)
        return jsonify({"error": "Failed to delete notification"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Notification preferences
# ─────────────────────────────────────────────────────────────────────────────

@notifications_bp.route("/preferences", methods=["GET"])
@require_auth
def get_preferences():
    """
    Get notification preferences for the authenticated user.

    Response JSON
    -------------
    {
        "preferences": {
            "appointment_reminder":  { "in_app": true, "email": true, "sms": false, "push": true },
            "medication_reminder":   { "in_app": true, "email": false, "sms": false, "push": true },
            "vitals_alert":          { "in_app": true, "email": false, "sms": true,  "push": true },
            "lab_result_ready":      { "in_app": true, "email": true,  "sms": false, "push": false },
            "doctor_message":        { "in_app": true, "email": false, "sms": false, "push": true }
        }
    }
    """
    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None

    default_prefs = {
        "appointment_reminder": {"in_app": True, "email": True, "sms": False, "push": True},
        "medication_reminder":  {"in_app": True, "email": False, "sms": False, "push": True},
        "vitals_alert":         {"in_app": True, "email": False, "sms": True,  "push": True},
        "triage_alert":         {"in_app": True, "email": False, "sms": True,  "push": True},
        "lab_result_ready":     {"in_app": True, "email": True,  "sms": False, "push": False},
        "system_alert":         {"in_app": True, "email": False, "sms": False, "push": False},
        "doctor_message":       {"in_app": True, "email": False, "sms": False, "push": True},
        "shift_summary":        {"in_app": True, "email": True,  "sms": False, "push": False},
    }

    try:
        from app.models.db import db
        from sqlalchemy import text
        import json as json_lib

        row = db.session.execute(
            text("SELECT preferences FROM notification_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchone()

        if row and row.preferences:
            saved = row.preferences if isinstance(row.preferences, dict) else json_lib.loads(row.preferences)
            # Merge saved with defaults (new types get defaults)
            merged = {**default_prefs, **saved}
            return jsonify({"preferences": merged}), 200

        return jsonify({"preferences": default_prefs}), 200

    except Exception as exc:
        logger.error("Notifications: get_preferences failed: %s", exc)
        return jsonify({"preferences": default_prefs}), 200


@notifications_bp.route("/preferences", methods=["PUT"])
@require_auth
def update_preferences():
    """
    Update notification preferences.

    Request JSON: Same structure as GET response preferences object.
    Only provided keys are updated — missing keys retain existing values.
    """
    data = request.get_json(silent=True) or {}
    preferences = data.get("preferences", {})

    if not preferences:
        return jsonify({"error": "preferences object is required"}), 400

    user = getattr(request, "current_user", None)
    user_id = str(user.id) if user else None
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        from app.models.db import db
        from sqlalchemy import text
        import json as json_lib

        # Load existing and merge
        row = db.session.execute(
            text("SELECT preferences FROM notification_preferences WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchone()

        existing = {}
        if row and row.preferences:
            existing = row.preferences if isinstance(row.preferences, dict) else json_lib.loads(row.preferences)

        merged = {**existing, **preferences}
        merged_json = json_lib.dumps(merged)

        if row:
            db.session.execute(
                text("""
                    UPDATE notification_preferences
                    SET preferences = :prefs, updated_at = :now
                    WHERE user_id = :uid
                """),
                {
                    "prefs": merged_json,
                    "now": datetime.now(timezone.utc).isoformat(),
                    "uid": user_id,
                },
            )
        else:
            db.session.execute(
                text("""
                    INSERT INTO notification_preferences (id, user_id, preferences, created_at, updated_at)
                    VALUES (:id, :uid, :prefs, :now, :now)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "uid": user_id,
                    "prefs": merged_json,
                    "now": datetime.now(timezone.utc).isoformat(),
                },
            )

        db.session.commit()
        return jsonify({"updated": True, "preferences": merged}), 200

    except Exception as exc:
        logger.exception("Notifications: update_preferences failed: %s", exc)
        return jsonify({"error": "Failed to update preferences"}), 500
