import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

class EncryptionUtil:
    """
    Utility for encrypting and decrypting PHI (Protected Health Information)
    using AES-256 (via Fernet).
    """
    def __init__(self, secret_key: str = None):
        if not secret_key:
            secret_key = os.environ.get("ENCRYPTION_KEY")
            
        if not secret_key:
            logger.warning("No ENCRYPTION_KEY found. Using a temporary key for development.")
            # DO NOT DO THIS IN PRODUCTION. This is just to allow the app to run locally without crashing.
            secret_key = "development-only-temporary-encryption-key-do-not-use-in-prod"

        # Fernet requires a 32-url-safe-base64-encoded byte string.
        # We use PBKDF2 to derive a safe key from whatever string is provided in env.
        salt = b'medassist-salt-static' # In a real app, you might want a unique salt or store it securely
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        self.fernet = Fernet(key)

    def encrypt(self, data: str) -> str:
        """Encrypts a string and returns the base64 encoded encrypted string."""
        if not data:
            return data
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypts a base64 encoded encrypted string."""
        if not encrypted_data:
            return encrypted_data
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            # In some cases, we might want to return the raw string if it wasn't encrypted
            # but for strict security, we should raise or return None.
            # For this MVP, we'll return a placeholder to avoid crashing if data was entered unencrypted.
            return "[DECRYPTION_ERROR]"

# Singleton instance
encryption_util = EncryptionUtil()

def encrypt_phi(text):
    return encryption_util.encrypt(text)

def decrypt_phi(text):
    return encryption_util.decrypt(text)
