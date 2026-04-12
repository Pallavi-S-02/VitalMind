from flask import Blueprint, request, jsonify
from app.api.v1.auth import token_required
from app.services.messaging_service import MessagingService
from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService

bp = Blueprint('messages', __name__, url_prefix='/api/v1/messages')

@bp.route('/conversations', methods=['GET'])
@token_required
def get_conversations(current_user):
    """Get all conversations for the current user."""
    role_name = current_user.role.name.lower()
    conversations = MessagingService.get_conversations_for_user(current_user.id, role_name)
    return jsonify([c.to_dict() for c in conversations]), 200

@bp.route('/conversations/new', methods=['POST'])
@token_required
def start_conversation(current_user):
    """Start a new message thread with a doctor."""
    if current_user.role.name.lower() != 'patient':
        return jsonify({"message": "Only patients can start a new message thread with a doctor"}), 403
        
    data = request.get_json()
    doctor_id = data.get('doctor_id')
    
    if not doctor_id:
        return jsonify({"message": "doctor_id is required"}), 400
        
    patient_profile = PatientService.get_patient_by_user_id(current_user.id)
    if not patient_profile:
        return jsonify({"message": "Patient profile not found"}), 404
        
    conv = MessagingService.get_or_create_conversation(patient_profile.id, doctor_id)
    return jsonify(conv.to_dict()), 201

@bp.route('/conversations/<string:conversation_id>/history', methods=['GET'])
@token_required
def get_conversation_history(current_user, conversation_id):
    """Get message history for a conversation."""
    # TODO: Verify user is part of this conversation
    messages = MessagingService.get_messages(conversation_id)
    return jsonify([m.to_dict() for m in messages]), 200

@bp.route('/send', methods=['POST'])
@token_required
def send_message(current_user):
    """Send a message in a conversation."""
    data = request.get_json()
    conversation_id = data.get('conversation_id')
    content = data.get('content')
    
    if not conversation_id or not content:
        return jsonify({"message": "conversation_id and content are required"}), 400
        
    # TODO: Verify user is part of this conversation
    msg = MessagingService.send_message(conversation_id, current_user.id, content)
    return jsonify(msg.to_dict()), 201

@bp.route('/conversations/<string:conversation_id>/read', methods=['POST'])
@token_required
def mark_read(current_user, conversation_id):
    """Mark all messages in a conversation as read."""
    count = MessagingService.mark_as_read(conversation_id, current_user.id)
    return jsonify({"message": f"{count} messages marked as read"}), 200
