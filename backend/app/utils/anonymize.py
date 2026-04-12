import hashlib
from typing import Dict, Any

def anonymize_patient_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove direct identifiers from a dictionary containing patient profile data
    following HIPAA Safe Harbor guidelines.
    """
    identifying_keys = [
        'name', 'first_name', 'last_name', 'full_name',
        'address', 'street', 'city', 'zip', 'zip_code', 'postal_code',
        'phone', 'phone_number', 'mobile',
        'email', 'ssn', 'ssn_encrypted', 'address_encrypted',
        'emergency_contact_name', 'emergency_contact_phone'
    ]
    
    anonymized = data.copy()
    
    # 1. Remove direct identifiers
    for key in identifying_keys:
        if key in anonymized:
            del anonymized[key]
            
    # 2. Mask date of birth to just the year
    if 'date_of_birth' in anonymized and anonymized['date_of_birth']:
        dob = str(anonymized['date_of_birth'])
        if len(dob) >= 4:
            anonymized['birth_year'] = dob[:4]
        del anonymized['date_of_birth']
        
    return anonymized

def pseudonoymize_id(original_id: str, salt: str = "medassist-analytics-salt") -> str:
    """
    Creates a deterministic hash of an ID for analytics, 
    breaking direct linkage while maintaining relationships within datasets.
    """
    if not original_id:
        return ""
    hasher = hashlib.sha256()
    hasher.update(f"{original_id}{salt}".encode('utf-8'))
    return hasher.hexdigest()[:16]
