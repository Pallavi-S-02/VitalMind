import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from app.services.auth_service import AuthService
import jwt
from datetime import datetime, timedelta

class TestAuthService(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test_secret_key'
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        self.user_id = 1
        self.role = 'patient'

    def tearDown(self):
        self.app_context.pop()

    def test_generate_token(self):
        token = AuthService.generate_token(self.user_id, self.role)
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)
        
        # Verify token contents
        decoded = jwt.decode(token, self.app.config['SECRET_KEY'], algorithms=['HS256'])
        self.assertEqual(decoded['sub'], str(self.user_id))
        self.assertEqual(decoded['role'], self.role)
        self.assertIn('exp', decoded)
        self.assertIn('iat', decoded)

    def test_decode_token_valid(self):
        token = AuthService.generate_token(self.user_id, self.role)
        decoded = AuthService.decode_token(token)
        
        self.assertIsInstance(decoded, dict)
        self.assertEqual(decoded['sub'], str(self.user_id))
        self.assertEqual(decoded['role'], self.role)

    def test_decode_token_expired(self):
        # Create an expired token
        payload = {
            'exp': datetime.utcnow() - timedelta(days=1),
            'iat': datetime.utcnow() - timedelta(days=2),
            'sub': str(self.user_id),
            'role': self.role
        }
        expired_token = jwt.encode(payload, self.app.config['SECRET_KEY'], algorithm='HS256')
        
        result = AuthService.decode_token(expired_token)
        self.assertEqual(result, 'Signature expired. Please log in again.')

    def test_decode_token_invalid(self):
        invalid_token = 'invalid.token.string'
        result = AuthService.decode_token(invalid_token)
        self.assertEqual(result, 'Invalid token. Please log in again.')

if __name__ == '__main__':
    unittest.main()
