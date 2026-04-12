import logging
from datetime import datetime
from app.models.db import db
from app.models.message import DirectConversation, DirectMessage
from app.models.doctor import DoctorProfile
from app.models.patient import PatientProfile

logger = logging.getLogger(__name__)

class MessagingService:
    @staticmethod
    def get_or_create_conversation(patient_id, doctor_id):
        """Find or create a direct conversation between a patient and a doctor."""
        conv = DirectConversation.query.filter_by(
            patient_id=patient_id, 
            doctor_id=doctor_id
        ).first()
        
        if not conv:
            conv = DirectConversation(
                patient_id=patient_id,
                doctor_id=doctor_id
            )
            db.session.add(conv)
            db.session.commit()
            logger.info(f"Created new conversation between patient {patient_id} and doctor {doctor_id}")
            
        return conv

    @staticmethod
    def get_conversations_for_user(user_id, role):
        """Retrieve all conversations for a given user (patient or doctor)."""
        if role == 'patient':
            # Get the patient profile first
            patient = PatientProfile.query.filter_by(user_id=user_id).first()
            if not patient:
                return []
            return DirectConversation.query.filter_by(patient_id=patient.id).all()
        elif role == 'doctor':
             # Get the doctor profile first
            doctor = DoctorProfile.query.filter_by(user_id=user_id).first()
            if not doctor:
                return []
            return DirectConversation.query.filter_by(doctor_id=doctor.id).all()
        return []

    @staticmethod
    def send_message(conversation_id, sender_id, content):
        """Send a new message to a conversation."""
        msg = DirectMessage(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content
        )
        
        # Update conversation timestamp
        conv = DirectConversation.query.get(conversation_id)
        if conv:
            conv.updated_at = datetime.utcnow()
            
        db.session.add(msg)
        db.session.commit()
        return msg

    @staticmethod
    def get_messages(conversation_id, limit=50):
        """Get history for a conversation."""
        return DirectMessage.query.filter_by(conversation_id=conversation_id)\
            .order_by(DirectMessage.created_at.asc())\
            .limit(limit).all()

    @staticmethod
    def mark_as_read(conversation_id, user_id):
        """Mark all messages in a conversation not sent by current user as read."""
        unread = DirectMessage.query.filter_by(
            conversation_id=conversation_id, 
            is_read=False
        ).filter(DirectMessage.sender_id != user_id).all()
        
        for msg in unread:
            msg.is_read = True
            
        db.session.commit()
        return len(unread)
