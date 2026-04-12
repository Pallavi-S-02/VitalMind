from flask import Blueprint, request, jsonify
from app.services.file_storage_service import FileStorageService
from app.api.v1.auth import token_required
from app.tasks.report_processing import trigger_report_processing
from app.middleware.hipaa_audit import audit_log
import logging
from app.models.doctor import DoctorProfile
from app.services.clinical_note_service import ClinicalNoteService

logger = logging.getLogger(__name__)

bp = Blueprint('reports', __name__, url_prefix='/api/v1/reports')

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

from app.models.db import db
from app.models.patient import PatientProfile

def resolve_patient_id(form_patient_id):
    if db.session.query(PatientProfile).filter_by(id=form_patient_id).first():
        return form_patient_id
    profile = db.session.query(PatientProfile).filter_by(user_id=form_patient_id).first()
    return str(profile.id) if profile else form_patient_id

@bp.route('/upload', methods=['POST'])
@token_required
@audit_log(action="upload", resource_type="medical_report")
def upload_report(current_user):
    """
    Upload a medical report.
    Accepts multipart/form-data.
    """
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
        
    patient_id = request.form.get('patient_id')
    
    if not patient_id:
        return jsonify({"message": "patient_id is required"}), 400
        
    if current_user.role == 'patient' and str(current_user.id) != patient_id:
        return jsonify({"message": "Unauthorized access"}), 403
        
    resolved_patient_id = resolve_patient_id(patient_id)
        
    if file and allowed_file(file.filename):
        try:
            file_bytes = file.read()
            # 1. Upload to S3 and save initial DB record
            report = FileStorageService.upload_new_report(
                patient_id=resolved_patient_id, 
                filename=file.filename,
                file_bytes=file_bytes,
                mime_type=file.mimetype
            )
            
            if not report:
                return jsonify({"message": "Failed to upload file to storage"}), 500
                
            # 2. Trigger asynchronous LangGraph ReportReader pipeline
            trigger_report_processing(str(report['id']), resolved_patient_id)
            
            return jsonify({
                "message": "Report uploaded and processing started", 
                "report": report
            }), 201
            
        except Exception as e:
            logger.error("Error during report upload: %s", e)
            return jsonify({"message": "Internal server error during upload"}), 500
            
    return jsonify({"message": "File type not allowed"}), 400

@bp.route('/patient/<string:patient_id>', methods=['GET'])
@token_required
@audit_log(action="read_all", resource_type="medical_report")
def get_patient_reports(current_user, patient_id):
    """List all reports for a patient"""
    if current_user.role == 'patient' and str(current_user.id) != patient_id:
        return jsonify({"message": "Unauthorized access"}), 403
        
    resolved_patient_id = resolve_patient_id(patient_id)
    reports = FileStorageService.get_patient_reports(resolved_patient_id)
    return jsonify(reports), 200

@bp.route('/<string:report_id>', methods=['GET'])
@token_required
@audit_log(action="read", resource_type="medical_report")
def get_report(current_user, report_id):
    """Get report details, including AI summary and MinIO presigned viewing URL"""
    # 1. Patients can only see their own reports
    # 2. Doctors/Admins can see any report by ID (permissions can be tightened later per-facility)
    
    patient_id_filter = None
    if current_user.role == 'patient':
        patient_id_filter = resolve_patient_id(str(current_user.id))
        
    report = FileStorageService.get_report_with_presigned_url(report_id, patient_id_filter)
    
    if not report:
        return jsonify({"message": "Report not found or unauthorized"}), 404
        
    return jsonify(report), 200

@bp.route('/<string:report_id>', methods=['PUT'])
@token_required
@audit_log(action="update", resource_type="medical_report")
def update_report(current_user, report_id):
    """
    Update a medical report, specifically to approve/edit structured clinical notes.
    """
    if current_user.role not in ('doctor', 'admin'):
        return jsonify({"message": "Forbidden. Only doctors can update clinical notes."}), 403

    from app.models.db import db
    from app.models.report import MedicalReport
    
    report = MedicalReport.query.filter_by(id=report_id).first()
    if not report:
        return jsonify({"message": "Report not found"}), 404
        
    data = request.get_json(silent=True) or {}
    
    if "summary" in data:
        report.summary = data["summary"]
        
    if "structured_data" in data:
        # Keep existing fields and merge
        report.structured_data = {**report.structured_data, **data["structured_data"]}
        
    try:
        db.session.commit()
        return jsonify({
            "message": "Report updated successfully",
            "id": report_id
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to update report %s: %s", report_id, e)
        return jsonify({"message": "Internal server error during update"}), 500


@bp.route('/notes', methods=['POST'])
@token_required
@audit_log(action="create", resource_type="clinical_note")
def create_clinical_note(current_user):
    """
    Create a manual clinical SOAP note.
    """
    if current_user.role.name not in ('doctor', 'admin'):
        return jsonify({"message": "Forbidden. Only doctors can create clinical notes."}), 403

    data = request.get_json()
    patient_id = data.get('patient_id')
    if not patient_id:
        return jsonify({"message": "patient_id is required"}), 400

    # Resolve doctor profile
    doctor_profile = DoctorProfile.query.filter_by(user_id=current_user.id).first()
    doctor_id = doctor_profile.id if doctor_profile else None

    # Resolve patient profile ID
    resolved_patient_id = resolve_patient_id(patient_id)

    soap_data = {
        "subjective": data.get("subjective", ""),
        "objective": data.get("objective", ""),
        "assessment": data.get("assessment", ""),
        "plan": data.get("plan", "")
    }

    report = ClinicalNoteService.create_manual_note(
        patient_id=resolved_patient_id,
        doctor_id=doctor_id,
        title=data.get("title"),
        soap_data=soap_data
    )

    if not report:
        return jsonify({"message": "Failed to create clinical note"}), 500

    return jsonify({
        "message": "Clinical note created successfully",
        "note": {
            "id": str(report.id),
            "title": report.title,
            "date": report.date.isoformat()
        }
    }), 201

