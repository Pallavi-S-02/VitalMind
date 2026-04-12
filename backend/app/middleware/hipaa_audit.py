import logging
from flask import request, current_app
from functools import wraps
from datetime import datetime
import json
import uuid

# Keep local file logger as fallback in case database goes down
audit_logger = logging.getLogger('hipaa_audit')
audit_logger.setLevel(logging.INFO)
handler = logging.FileHandler('hipaa_audit.log')
handler.setFormatter(logging.Formatter('%(message)s'))
audit_logger.addHandler(handler)

def log_phi_access(action, resource_type, resource_id=None, patient_id=None):
    """
    Log any access or modification to Protected Health Information (PHI)
    to the AuditLog database table.
    """
    try:
        from app.models.db import db
        from app.models.audit_log import AuditLog
        
        user_id = getattr(request, 'user_id', None)
        user_role = getattr(request, 'user_role', 'anonymous')
        
        details = {
            'actor_role': user_role,
            'patient_id': str(patient_id) if patient_id else None
        }
        
        # Verify user_id is a valid UUID, otherwise it shouldn't be mapped
        valid_user_id = None
        if user_id:
            try:
                valid_user_id = uuid.UUID(str(user_id))
            except ValueError:
                pass
                
        valid_resource_id = None
        if resource_id:
            try:
                valid_resource_id = uuid.UUID(str(resource_id))
            except ValueError:
                pass

        log_entry = AuditLog(
            user_id=valid_user_id,
            action=action,
            entity_type=resource_type,
            entity_id=valid_resource_id,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        audit_logger.error(f"Failed to write audit log to DB: {e}")
        # Fallback to local file
        audit_event = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'actor_id': str(getattr(request, 'user_id', 'anonymous')),
            'action': action,
            'resource_type': resource_type,
            'resource_id': str(resource_id) if resource_id else None,
        }
        audit_logger.info(json.dumps(audit_event))

def audit_log(action, resource_type):
    """
    Decorator to automatically log PHI access for specific routes
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract IDs from kwargs if present (URL parameters)
            resource_id = kwargs.get('id') or kwargs.get(f'{resource_type}_id')
            patient_id = kwargs.get('patient_id')
            
            # Log the attempt
            log_phi_access(
                action=f"{action}_attempt",
                resource_type=resource_type,
                resource_id=resource_id,
                patient_id=patient_id
            )
            
            # Execute the function
            try:
                result = f(*args, **kwargs)
                
                # Log successful completion
                log_phi_access(
                    action=f"{action}_success",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    patient_id=patient_id
                )
                return result
            except Exception as e:
                # Log failure
                log_phi_access(
                    action=f"{action}_failed",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    patient_id=patient_id
                )
                raise e
        return decorated_function
    return decorator
