import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_fernet_instance = None

def _get_fernet():
    global _fernet_instance
    if _fernet_instance is None:
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            # Fallback to a temporary key if not provided (not secure for prod, but prevents crash)
            # A real prod environment must provide ENCRYPTION_KEY
            logger.warning("ENCRYPTION_KEY not found in environment. Using a temporary key. Passwords will be lost on restart!")
            key = Fernet.generate_key().decode()
            os.environ['ENCRYPTION_KEY'] = key
        
        try:
            _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise ValueError("Invalid ENCRYPTION_KEY provided")
            
    return _fernet_instance

def encrypt_value(value: str) -> str:
    """Encrypts a string value and returns the encrypted base64 string."""
    if not value:
        return value
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    """Decrypts a base64 encrypted string back to plaintext."""
    if not encrypted_value:
        return encrypted_value
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_value.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt value: {e}")
        # Return empty or raise? Returning original could leak if not actually encrypted, 
        # but safely raising is better.
        raise ValueError("Decryption failed. The encryption key may have changed.")
