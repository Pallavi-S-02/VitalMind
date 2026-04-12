from flask import Blueprint, request, jsonify
from app.services.doctor_service import DoctorService
from app.api.v1.auth import token_required

bp = Blueprint('doctors', __name__, url_prefix='/api/v1/doctors')

@bp.route('/', methods=['GET'])
@token_required
def get_doctors(current_user):
    """
    Get all doctors
    ---
    tags:
      - Doctors
    security:
      - Bearer: []
    responses:
      200:
        description: List of doctors
    """
    doctors = DoctorService.get_all_doctors()
    return jsonify([d.to_dict() for d in doctors]), 200

@bp.route('/<string:doctor_id>', methods=['GET'])
@token_required
def get_doctor(current_user, doctor_id):
    """
    Get doctor by ID
    ---
    tags:
      - Doctors
    security:
      - Bearer: []
    parameters:
      - in: path
        name: doctor_id
        required: true
        schema:
          type: string
    responses:
      200:
        description: Doctor details
      404:
        description: Doctor not found
    """
    doctor = DoctorService.get_doctor_by_id(doctor_id)
    if not doctor:
        return jsonify({"message": "Doctor not found"}), 404
        
    return jsonify(doctor.to_dict()), 200

@bp.route('/<string:doctor_id>', methods=['PUT'])
@token_required
def update_doctor(current_user, doctor_id):
    """
    Update doctor profile
    ---
    tags:
      - Doctors
    security:
      - Bearer: []
    parameters:
      - in: path
        name: doctor_id
        required: true
        schema:
          type: string
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
    responses:
      200:
        description: Profile updated
    """
    if current_user.role == 'doctor' and current_user.id != doctor_id:
        return jsonify({"message": "Unauthorized access"}), 403
        
    data = request.get_json()
    doctor = DoctorService.update_doctor_profile(doctor_id, data)
    
    if not doctor:
        return jsonify({"message": "Doctor not found"}), 404
        
    return jsonify({"message": "Profile updated successfully", "doctor": doctor.to_dict()}), 200

@bp.route('/me', methods=['PUT'])
@token_required
def update_current_doctor(current_user):
    """
    Update the currently logged-in doctor's profile
    """
    if current_user.role != 'doctor':
        return jsonify({"message": "Unauthorized. Only doctors can update their own clinical profile."}), 403
        
    if not current_user.doctor_profile:
        return jsonify({"message": "Doctor profile not found"}), 404
        
    data = request.get_json()
    doctor = DoctorService.update_doctor_profile(current_user.doctor_profile.id, data)
    
    return jsonify({
        "message": "Profile updated successfully", 
        "doctor": doctor.to_dict()
    }), 200
