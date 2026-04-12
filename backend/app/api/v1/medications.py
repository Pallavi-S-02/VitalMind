"""
medications.py — VitalMind Medication & Drug Interaction API
"""

import logging
import uuid

from flask import Blueprint, request, jsonify
from app.services.medication_service import MedicationService
from app.services.doctor_service import DoctorService
from app.api.v1.auth import token_required
from app.models.doctor import DoctorProfile

logger = logging.getLogger(__name__)

bp = Blueprint('medications', __name__, url_prefix='/api/v1/medications')

@bp.route('/catalog', methods=['GET'])
@token_required
def get_medication_catalog(current_user):
    """Get all available medications from the master catalog"""
    meds = MedicationService.get_medication_catalog()
    return jsonify([m.to_dict() for m in meds]), 200

@bp.route('/patient/<string:patient_id>', methods=['GET'])
@token_required
def get_patient_medications(current_user, patient_id):
    """Get medications for a patient"""
    # Authorization: user must be admin, doctor, or the patient themselves
    is_authorized = (current_user.role.name in ['admin', 'doctor']) or (str(current_user.id) == patient_id)
    if not is_authorized:
        return jsonify({"message": "Unauthorized access"}), 403

    from app.models.patient import PatientProfile
    actual_profile_id = patient_id
    if current_user.role.name == 'patient' and str(current_user.id) == patient_id:
        profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if profile: actual_profile_id = str(profile.id)

    medications = MedicationService.get_patient_medications(actual_profile_id)
    return jsonify([m.to_dict() for m in medications]), 200

@bp.route('/prescriptions', methods=['POST'])
@token_required
def create_prescription(current_user):
    """Create a new prescription (doctor only)"""
    if current_user.role.name != 'doctor':
        return jsonify({"message": "Only doctors can create prescriptions"}), 403

    data = request.get_json()
    
    # Map User ID to Doctor Profile ID (Mandatory for database health)
    doctor_profile = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    if not doctor_profile:
        return jsonify({"message": "Doctor profile not found for this user."}), 404

    # Ensure we use the profile ID for the foreign key, not the User ID
    data['doctor_id'] = str(doctor_profile.id)

    try:
        prescription = MedicationService.create_prescription(data)
        return jsonify({"message": "Prescription created", "prescription": prescription.to_dict()}), 201
    except Exception as e:
        logger.exception("Prescription creation failed: %s", e)
        return jsonify({"message": "Internal error creating prescription", "error": str(e)}), 500

@bp.route('/prescriptions/patient/<string:patient_id>', methods=['GET'])
@token_required
def get_patient_prescriptions(current_user, patient_id):
    from app.models.patient import PatientProfile
    actual_profile_id = patient_id
    if current_user.role.name == 'patient' and str(current_user.id) == patient_id:
        profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if profile: actual_profile_id = str(profile.id)

    prescriptions = MedicationService.get_patient_prescriptions(actual_profile_id)
    return jsonify([p.to_dict() for p in prescriptions]), 200

@bp.route('/check-interactions', methods=['POST'])
@token_required
def check_drug_interactions(current_user):
    """Run the Drug Interaction AI Agent for a patient's medication profile."""
    data = request.get_json() or {}

    patient_id = data.get("patient_id")
    if not patient_id:
        if current_user.role.name == "patient":
            patient_id = str(current_user.id)
        else:
            return jsonify({"message": "patient_id is required"}), 400

    user_message = data.get("message", "Review medications for safety.")
    session_id = data.get("session_id") or str(uuid.uuid4())

    try:
        from app.agents.drug_interaction_agent import DrugInteractionAgent
        from langchain_core.messages import HumanMessage

        agent = DrugInteractionAgent()
        initial_state = {
            "messages": [HumanMessage(content=user_message)],
            "patient_id": patient_id,
            "session_id": session_id,
            "intent": "drug_interaction",
            "context": {},
            "tool_outputs": [],
            "final_response": None,
            "error": None,
        }

        result = agent.invoke(initial_state)
        final = result.get("final_response") or {}

        return jsonify({
            "session_id": session_id,
            "patient_id": patient_id,
            "response": final.get("content", "Analysis complete."),
            "overall_safety_rating": final.get("overall_safety_rating", "CAUTION"),
            "total_interactions": final.get("total_interactions", 0),
            "critical_alerts": final.get("critical_alerts", []),
            "moderate_warnings": final.get("moderate_warnings", []),
            "minor_notes": final.get("minor_notes", []),
            "error": result.get("error"),
        }), 200

    except Exception as exc:
        logger.exception("DrugInteractionAgent error: %s", exc)
        return jsonify({"message": "Agent error", "error": str(exc)}), 500
@bp.route('/<string:patient_id>/schedule', methods=['GET'])
@token_required
def get_medication_schedule(current_user, patient_id):
    """
    Generate an AI-optimized medication schedule for a patient.
    """
    # Authorization logic (patient access only, or doctor/admin)
    is_authorized = (current_user.role.name in ['admin', 'doctor']) or (str(current_user.id) == patient_id)
    if not is_authorized:
        return jsonify({"message": "Unauthorized access"}), 403

    from app.models.patient import PatientProfile
    actual_profile_id = patient_id
    if current_user.role.name == 'patient' and str(current_user.id) == patient_id:
        profile = PatientProfile.query.filter_by(user_id=current_user.id).first()
        if profile: actual_profile_id = str(profile.id)

    try:
        schedule_data = MedicationService.generate_schedule(actual_profile_id)
        return jsonify(schedule_data), 200
    except Exception as e:
        logger.exception("Schedule generation failed for patient %s: %s", patient_id, e)
        return jsonify({"message": "Failed to generate schedule", "error": str(e)}), 500
