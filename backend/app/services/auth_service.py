import jwt
from datetime import datetime, timedelta
import os
from flask import current_app

class AuthService:
    @staticmethod
    def generate_token(user_id, role, expiration_minutes=60):
        """Generates a JWT token for a user."""
        try:
            payload = {
                'exp': datetime.utcnow() + timedelta(minutes=expiration_minutes),
                'iat': datetime.utcnow(),
                'sub': str(user_id),
                'role': role
            }
            return jwt.encode(
                payload,
                current_app.config.get('SECRET_KEY'),
                algorithm='HS256'
            )
        except Exception as e:
            return str(e)

    @staticmethod
    def decode_token(auth_token):
        """Decodes a JWT token."""
        try:
            payload = jwt.decode(
                auth_token,
                current_app.config.get('SECRET_KEY'),
                algorithms=['HS256']
            )
            return payload
        except jwt.ExpiredSignatureError:
            return 'Signature expired. Please log in again.'
        except jwt.InvalidTokenError:
            return 'Invalid token. Please log in again.'
