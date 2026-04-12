"""
triage.py — VitalMind Triage API Blueprint (Step 16)

Endpoints
---------
POST /api/v1/triage/evaluate
    Submit a chief complaint (+ optional vitals) for immediate ESI triage.

GET  /api/v1/triage/<triage_id>
    Retrieve a previously computed triage record.

GET  /api/v1/triage/patient/<patient_id>/history
    List triage history for a patient (most recent first).

POST /api/v1/triage/<triage_id>/override
    Allow a clinician to override the AI-assigned ESI level with justification.
"""

import logging
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from app.middleware.auth_middleware import require_auth

logger = logging.getLogger(__name__)

triage_bp = Blueprint("triage", __name__, url_prefix="/api/v1/triage")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/triage/evaluate
# ─────────────────────────────────────────────────────────────────────────────

@triage_bp.route("/evaluate", methods=["POST"])
@require_auth
def evaluate_triage():
    """
    Perform an immediate triage evaluation.

    Request JSON
    ------------
    {
        "chief_complaint": "Sudden severe chest pain radiating to left arm, sweating",
        "patient_id": "<uuid>",           // optional — uses authenticated user if omitted
        "vital_signs": {                   // optional — loaded from Redis if omitted
            "heart_rate": 102,
            "spo2": 94.5,
            "systolic_bp": 85,
            "diastolic_bp": 55,
            "temperature_c": 36.8,
            "respiratory_rate": 22
        },
        "context": {                       // optional additional patient context
            "chronic_conditions": ["hypertension", "diabetes"],
            "medications": ["metformin", "lisinopril"],
            "allergies": ["penicillin"]
        }
    }

    Response JSON (ESI 1/2 example)
    --------------------------------
    {
        "triage_id": "uuid",
        "esi_level": 1,
        "esi_label": "IMMEDIATE",
        "max_wait_minutes": 0,
        "disposition": "ED resuscitation bay",
        "patient_instruction": "CALL 911 NOW. Do not drive yourself...",
        "urgency": "emergency",
        "content": "<empathetic patient-facing triage report>",
        "vital_threats": ["Hypotension: BP 85/55", "Tachycardia: HR 102"],
        "recommended_resources": ["12-lead ECG", "Troponin", "IV access", "..."],
        "immediate_actions": ["Aspirin 325mg chewable", "IV access", "..."],
        "red_flags": ["chest pain (+3)", "left arm pain (+3)", "..."],
        "preliminary_differentials": ["STEMI", "Pulmonary Embolism", "Aortic Dissection"],
        "alert_dispatched": true,
        "alert_id": "uuid",
        "notifications_sent": ["nurse_push", "physician_sms", "specialist_page"]
    }
    """
    data = request.get_json(silent=True) or {}
    chief_complaint = (data.get("chief_complaint") or "").strip()

    if not chief_complaint:
        return jsonify({"error": "chief_complaint is required for triage evaluation"}), 400

    # Patient identification — use provided ID or fall back to authenticated user
    current_user = getattr(request, "current_user", None)
    patient_id = (data.get("patient_id") or
                  (str(current_user.id) if current_user else None))

    vital_signs = data.get("vital_signs") or {}
    additional_context = data.get("context") or {}

    # Build patient context dict (merge from request + authenticated profile)
    patient_context: dict = {
        "name": getattr(current_user, "name", None) or additional_context.get("name", "Patient"),
        "age": getattr(current_user, "age", None) or additional_context.get("age"),
        "chronic_conditions": (
            getattr(current_user, "chronic_conditions", None) or
            additional_context.get("chronic_conditions", [])
        ),
        "current_medications": (
            getattr(current_user, "current_medications", None) or
            additional_context.get("medications", [])
        ),
        "allergies": (
            getattr(current_user, "allergies", None) or
            additional_context.get("allergies", [])
        ),
    }

    session_id = str(uuid.uuid4())

    logger.info(
        "Triage API: evaluating complaint for patient=%s complaint=%s",
        patient_id, chief_complaint[:80],
    )

    try:
        from app.agents.triage_agent import run_triage

        result = run_triage(
            chief_complaint=chief_complaint,
            patient_id=patient_id,
            vital_signs=vital_signs,
            patient_context=patient_context,
            session_id=session_id,
        )

        if not result:
            return jsonify({"error": "Triage evaluation returned no result"}), 500

        # Build clean API response
        response_payload = {
            "triage_id": result.get("triage_id"),
            "session_id": session_id,
            "esi_level": result.get("esi_level"),
            "esi_label": result.get("esi_label"),
            "urgency": result.get("urgency"),
            "max_wait_minutes": result.get("max_wait_minutes"),
            "disposition": result.get("disposition"),
            "patient_instruction": result.get("patient_instruction"),
            "content": result.get("content"),
            "vital_threats": result.get("vital_threats", []),
            "recommended_resources": result.get("recommended_resources", []),
            "immediate_actions": result.get("immediate_actions", []),
            "red_flags": result.get("red_flags", []),
            "preliminary_differentials": result.get("preliminary_differentials", []),
            "alert_dispatched": result.get("alert_dispatched", False),
            "alert_id": result.get("alert_id"),
            "notifications_sent": result.get("notifications_sent", []),
            "audit_note": result.get("audit_note"),
        }

        status_code = 200
        if result.get("esi_level", 3) <= 2:
            status_code = 201   # Created — an alert was generated

        return jsonify(response_payload), status_code

    except Exception as exc:
        logger.exception("Triage API: evaluation failed: %s", exc)
        return jsonify({
            "error": "Triage evaluation encountered an error",
            "detail": str(exc),
            # Safe fallback — always tell the patient to seek care
            "patient_instruction": (
                "Unable to complete automated triage. As a precaution, "
                "please call 911 or go to your nearest emergency room if you feel your life may be at risk."
            ),
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/triage/<triage_id>
# ─────────────────────────────────────────────────────────────────────────────

@triage_bp.route("/<triage_id>", methods=["GET"])
@require_auth
def get_triage_record(triage_id: str):
    """
    Retrieve a triage record by its ID.

    Response JSON
    -------------
    {
        "triage_id": "uuid",
        "patient_id": "uuid",
        "chief_complaint": "...",
        "esi_level": 2,
        "esi_label": "EMERGENT",
        "red_flags": [...],
        "vitals_snapshot": {...},
        "patient_report": "...",
        "audit_note": "...",
        "alert_dispatched": true,
        "created_at": "2026-01-15T14:22:00Z",
        "clinician_override": null
    }
    """
    try:
        from app.models.db import db
        from sqlalchemy import text

        row = db.session.execute(
            text("SELECT * FROM triage_records WHERE id = :id LIMIT 1"),
            {"id": triage_id},
        ).fetchone()

        if not row:
            return jsonify({"error": "Triage record not found"}), 404

        import json as json_lib
        record = dict(row._mapping)

        # Parse JSON fields
        for field in ("red_flags", "vitals_snapshot"):
            if isinstance(record.get(field), str):
                try:
                    record[field] = json_lib.loads(record[field])
                except Exception:
                    pass

        return jsonify(record), 200

    except Exception as exc:
        logger.error("Triage API: get record failed: %s", exc)
        return jsonify({"error": "Could not retrieve triage record", "detail": str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/triage/patient/<patient_id>/history
# ─────────────────────────────────────────────────────────────────────────────

@triage_bp.route("/patient/<patient_id>/history", methods=["GET"])
@require_auth
def get_patient_triage_history(patient_id: str):
    """
    List triage events for a specific patient (most recent first).

    Query params:
        limit (int, default=20): max number of records
        esi_max (int, default=5): only return records with ESI ≤ this level

    Response JSON
    -------------
    {
        "patient_id": "uuid",
        "count": 5,
        "triage_events": [
            {
                "triage_id": "uuid",
                "esi_level": 2,
                "esi_label": "EMERGENT",
                "chief_complaint": "Chest pain...",
                "alert_dispatched": true,
                "created_at": "2026-01-15T14:22:00Z"
            },
            ...
        ]
    }
    """
    limit = min(int(request.args.get("limit", 20)), 100)
    esi_max = min(int(request.args.get("esi_max", 5)), 5)

    try:
        from app.models.db import db
        from sqlalchemy import text

        rows = db.session.execute(
            text("""
                SELECT id AS triage_id, esi_level, esi_label, chief_complaint,
                       alert_dispatched, created_at
                FROM triage_records
                WHERE patient_id = :patient_id
                  AND esi_level <= :esi_max
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"patient_id": patient_id, "esi_max": esi_max, "limit": limit},
        ).fetchall()

        events = [dict(r._mapping) for r in rows]

        return jsonify({
            "patient_id": patient_id,
            "count": len(events),
            "triage_events": events,
        }), 200

    except Exception as exc:
        logger.error("Triage API: patient history failed: %s", exc)
        return jsonify({"error": "Could not retrieve triage history"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/triage/<triage_id>/override
# ─────────────────────────────────────────────────────────────────────────────

@triage_bp.route("/<triage_id>/override", methods=["POST"])
@require_auth
def override_triage(triage_id: str):
    """
    Allow a licensed clinician to override the AI ESI assignment.

    Request JSON
    ------------
    {
        "new_esi_level": 1,
        "clinical_justification": "Patient showing BP 70/40 on arrival, STEMI confirmed on ECG"
    }

    Response JSON
    -------------
    {
        "triage_id": "uuid",
        "original_esi": 2,
        "override_esi": 1,
        "overridden_by": "<user_id>",
        "clinical_justification": "...",
        "overridden_at": "2026-01-15T14:25:00Z"
    }
    """
    data = request.get_json(silent=True) or {}
    new_esi = data.get("new_esi_level")
    justification = (data.get("clinical_justification") or "").strip()

    if new_esi is None or int(new_esi) not in range(1, 6):
        return jsonify({"error": "new_esi_level must be an integer between 1 and 5"}), 400

    if not justification:
        return jsonify({"error": "clinical_justification is required for ESI override (audit trail)"}), 400

    current_user = getattr(request, "current_user", None)
    clinician_id = str(current_user.id) if current_user else "unknown"

    try:
        from app.models.db import db
        from sqlalchemy import text

        # Fetch original record
        row = db.session.execute(
            text("SELECT id, esi_level FROM triage_records WHERE id = :id"),
            {"id": triage_id},
        ).fetchone()

        if not row:
            return jsonify({"error": "Triage record not found"}), 404

        original_esi = row.esi_level
        from app.agents.prompts.triage_prompts import ESI_CONFIG
        new_esi_cfg = ESI_CONFIG.get(int(new_esi), {})
        overridden_at = datetime.now(timezone.utc).isoformat()

        db.session.execute(
            text("""
                UPDATE triage_records
                SET esi_level = :new_esi,
                    esi_label = :new_label,
                    clinician_override = :override_json
                WHERE id = :id
            """),
            {
                "new_esi": int(new_esi),
                "new_label": new_esi_cfg.get("label", str(new_esi)),
                "override_json": str({
                    "original_esi": original_esi,
                    "new_esi": int(new_esi),
                    "overridden_by": clinician_id,
                    "justification": justification,
                    "overridden_at": overridden_at,
                }),
                "id": triage_id,
            },
        )
        db.session.commit()

        logger.info(
            "Triage API: ESI override by clinician %s — triage %s: %d → %d",
            clinician_id, triage_id, original_esi, int(new_esi),
        )

        return jsonify({
            "triage_id": triage_id,
            "original_esi": original_esi,
            "override_esi": int(new_esi),
            "overridden_by": clinician_id,
            "clinical_justification": justification,
            "overridden_at": overridden_at,
        }), 200

    except Exception as exc:
        logger.exception("Triage API: override failed: %s", exc)
        return jsonify({"error": "Override failed", "detail": str(exc)}), 500
