from functools import wraps
from flask import request, jsonify
from app.services.auth_service import AuthService
from app.models.user import User

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'message': 'Authorization header is missing'}), 401

        try:
            # Format: 'Bearer <token>'
            token = auth_header.split(" ")[1]
        except IndexError:
            return jsonify({'message': 'Invalid token format. Use Bearer <token>'}), 401

        resp = AuthService.decode_token(token)
        if isinstance(resp, str):
            # If decode_token returns a string, it means an error occurred
            return jsonify({'message': resp}), 401

        # Check if user exists
        user = User.query.get(resp['sub'])
        if not user:
            return jsonify({'message': 'User not found'}), 401
            
        if not user.is_active:
            return jsonify({'message': 'Account is inactive'}), 403

        # Add user and role info to the request context
        request.user_id = resp['sub']
        request.user_role = resp['role']
        request.current_user = user

        return f(*args, **kwargs)

    return decorated

def require_role(roles):
    """
    roles: list of allowed roles. e.g., ['admin', 'doctor']
    """
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated_function(*args, **kwargs):
            if request.user_role not in roles:
                return jsonify({'message': 'Access denied: insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
