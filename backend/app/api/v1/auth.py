from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.db import db
from app.models.user import User, Role
from app.models.patient import PatientProfile
from app.models.doctor import DoctorProfile
from app.services.auth_service import AuthService
from app.middleware.auth_middleware import require_auth
from app.middleware.hipaa_audit import audit_log
from functools import wraps

def token_required(f):
    @require_auth
    @wraps(f)
    def decorated(*args, **kwargs):
        return f(request.current_user, *args, **kwargs)
    return decorated

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    try:
        # Basic validation
        required_fields = ['email', 'password', 'first_name', 'last_name', 'role']
        for field in required_fields:
            if field not in data:
                return jsonify({'message': f'Missing required field: {field}'}), 400
                
        if data['role'] not in ['patient', 'doctor']: # Only allow self-registration for these
            return jsonify({'message': 'Invalid role specified for registration'}), 400

        # Check if user already exists
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'message': 'Email already registered'}), 409

        # Get the role
        role_name = data['role']
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return jsonify({'message': f'Role {role_name} not found'}), 400

        # Create new user
        new_user = User(
            email=data['email'],
            password_hash=generate_password_hash(data['password']),
            first_name=data['first_name'],
            last_name=data['last_name'],
            role_id=role.id,
            phone_number=data.get('phone_number')
        )
        
        db.session.add(new_user)
        db.session.flush() # Get the new_user.id
        
        # Create associated profile
        if data['role'] == 'patient':
            profile = PatientProfile(
                user_id=new_user.id,
                date_of_birth=data.get('date_of_birth'),
                gender=data.get('gender')
            )
            db.session.add(profile)
        elif data['role'] == 'doctor':
            # Check for required doctor fields
            if 'license_number' not in data:
                db.session.rollback()
                return jsonify({'message': 'Missing required field for doctor: license_number'}), 400
            
            profile = DoctorProfile(
                user_id=new_user.id,
                specialization=data.get('specialty', 'General Practice'),
                license_number=data['license_number']
            )
            db.session.add(profile)

        db.session.commit()

        # Generate token
        token = AuthService.generate_token(new_user.id, role.name)
        
        return jsonify({
            'message': 'User registered successfully',
            'token': token,
            'user': {
                'id': new_user.id,
                'email': new_user.email,
                'role': role.name,
                'first_name': new_user.first_name,
                'last_name': new_user.last_name
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'message': 'Internal Server Error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing email or password'}), 400
        
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
        
    if not user.is_active:
        return jsonify({'message': 'Account is inactive. Please contact support.'}), 403
        
    # Generate token
    token = AuthService.generate_token(user.id, user.role.name)
    
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'role': user.role.name,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    }), 200

@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get the profile of the currently logged-in user."""
    user = request.current_user
    return jsonify({
        'id': user.id,
        'email': user.email,
        'role': user.role.name,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone_number': user.phone_number,
        'is_active': user.is_active
    }), 200

@auth_bp.route('/me', methods=['PUT'])
@require_auth
@audit_log(action="update", resource_type="user")
def update_current_user():
    """Update the profile of the currently logged-in user."""
    user = request.current_user
    data = request.get_json()
    
    try:
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'phone_number' in data:
            user.phone_number = data['phone_number']
        if 'email' in data and data['email'] != user.email:
            # Check for email conflict
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'message': 'Email already in use'}), 409
            user.email = data['email']
            
        db.session.commit()
        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone_number': user.phone_number
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Failed to update profile', 'error': str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
@require_auth
def refresh_token():
    """Refresh the JWT token."""
    # Since require_auth already validates the token, we can just issue a new one
    token = AuthService.generate_token(request.user_id, request.user_role)
    return jsonify({'token': token}), 200

@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """
    Client-side logout: The client simply deletes the token.
    For server-side invalidation, we would need a token blacklist (e.g., in Redis).
    For now, this is a placeholder that just returns success.
    """
    return jsonify({'message': 'Successfully logged out'}), 200
