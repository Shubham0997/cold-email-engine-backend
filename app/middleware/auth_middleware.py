import functools
import logging
from flask import request, jsonify, g
import firebase_admin
import firebase_admin.auth as firebase_auth

logger = logging.getLogger(__name__)

def require_auth(f):
    """
    Decorator that protects a Flask route with Firebase Authentication.
    
    Validates the Firebase ID token from the Authorization header.
    On success, sets g.user with uid and email for downstream use.
    On failure, returns a 401 Unauthorized response.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # If Firebase Admin is not initialized, reject with a clear message
        if not firebase_admin._apps:
            logger.error("Firebase Admin SDK is not initialized. Cannot verify tokens.")
            return jsonify({"error": "Authentication service is not configured on the server."}), 503
        
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization header missing or malformed"}), 401
        
        token = auth_header.split('Bearer ')[1]
        
        try:
            decoded_token = firebase_auth.verify_id_token(token)
            g.user = {
                'uid': decoded_token['uid'],
                'email': decoded_token.get('email', ''),
            }
        except firebase_auth.ExpiredIdTokenError:
            return jsonify({"error": "Token has expired. Please sign in again."}), 401
        except firebase_auth.RevokedIdTokenError:
            return jsonify({"error": "Token has been revoked. Please sign in again."}), 401
        except firebase_auth.InvalidIdTokenError:
            return jsonify({"error": "Invalid authentication token."}), 401
        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            return jsonify({"error": "Authentication failed."}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function
