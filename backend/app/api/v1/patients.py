from flask import Blueprint, request, jsonify
from app.services.patient_service import PatientService
from app.api.v1.auth import token_required
from app.middleware.hipaa_audit import audit_log

bp = Blueprint('patients', __name__, url_prefix='/api/v1/patients')

@bp.route('/', methods=['GET'])
@token_required
@audit_log(action="read_all", resource_type="patient")
def get_patients(current_user):
    """
    Get all patients
    ---
    tags:
      - Patients
    security:
      - Bearer: []
    responses:
      200:
        description: List of patients
    """
    # Only admins or doctors should see all patients
    if current_user.role.name not in ['admin', 'doctor']:
        return jsonify({"message": "Unauthorized access"}), 403
        
    patients = PatientService.get_all_patients()
    return jsonify([p.to_dict() for p in patients]), 200

@bp.route('/<string:patient_id>', methods=['GET'])
@token_required
def get_patient(current_user, patient_id):
    """Get patient by ID"""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        return jsonify({"message": "Patient not found"}), 404
        
    # Check authorization: user must be admin, doctor, or the patient themselves
    if current_user.role.name == 'patient' and str(current_user.id) != str(patient.user_id):
        return jsonify({"message": "Unauthorized access"}), 403
        
    return jsonify(patient.to_dict()), 200

@bp.route('/profile', methods=['GET'])
@token_required
def get_my_profile(current_user):
    """Get the patient profile of the currently logged-in user."""
    if current_user.role.name != 'patient':
        return jsonify({"message": "This endpoint is for patients only"}), 403
        
    patient = PatientService.get_patient_by_user_id(current_user.id)
    if not patient:
        return jsonify({"message": "Patient profile not found"}), 404
        
    return jsonify(patient.to_dict()), 200

@bp.route('/<string:patient_id>', methods=['PUT'])
@token_required
@audit_log(action="update", resource_type="patient")
def update_patient(current_user, patient_id):
    """Update patient profile"""
    patient = PatientService.get_patient_by_id(patient_id)
    if not patient:
        return jsonify({"message": "Patient not found"}), 404
        
    # Check authorization: user must be admin, doctor, or the patient themselves
    if current_user.role.name == 'patient' and str(current_user.id) != str(patient.user_id):
        return jsonify({"message": "Unauthorized access"}), 403
        
    data = request.get_json()
    updated_patient = PatientService.update_patient_profile(patient_id, data)
    
    return jsonify({"message": "Profile updated successfully", "patient": updated_patient.to_dict()}), 200
