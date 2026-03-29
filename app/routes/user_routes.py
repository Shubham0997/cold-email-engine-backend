from flask import Blueprint, request, jsonify, g
import logging
import smtplib
from app import db
from app.domain.models import SmtpConfig
from app.middleware.auth_middleware import require_auth
from app.utils.crypto import encrypt_value, decrypt_value
import socket

user_bp = Blueprint('user', __name__)
logger = logging.getLogger(__name__)

@user_bp.route('/settings/smtp', methods=['GET'])
@require_auth
def get_smtp_config():
    try:
        user_id = g.user['uid']
        config = db.session.query(SmtpConfig).filter_by(user_id=user_id).first()
        
        if not config:
            return jsonify({"has_config": False}), 200
            
        data = config.to_dict()
        data['has_config'] = True
        
        # Never send the password back to the client!
        data['smtp_pass'] = '********' 
        
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to fetch SMTP config: {e}")
        return jsonify({"error": "Failed to retrieve configuration"}), 500

@user_bp.route('/settings/smtp/verify', methods=['POST'])
@require_auth
def verify_and_save_smtp():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    user_id = g.user['uid']
    host = data.get('smtp_host', '').strip()
    port = data.get('smtp_port')
    user = data.get('smtp_user', '').strip()
    password = data.get('smtp_pass', '').strip()
    
    if not all([host, port, user]):
        return jsonify({"error": "Host, port, and username are required."}), 400
        
    try:
        port = int(port)
    except ValueError:
        return jsonify({"error": "Port must be a number."}), 400
        
    # If the client sends the masked placeholder, load the real password from DB to verify/save
    if password == '********':
        existing = db.session.query(SmtpConfig).filter_by(user_id=user_id).first()
        if not existing:
            return jsonify({"error": "Password required for new setup."}), 400
        try:
            password = decrypt_value(existing.smtp_pass)
        except Exception:
            return jsonify({"error": "Decryption error. Please re-enter your password."}), 400
            
    if not password:
        return jsonify({"error": "Password is required."}), 400

    # Test connection
    try:
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = "142.251.2.108" # Default to typical gmail fallback if DNS issues occur locally
            
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        
        if port == 465:
            import ssl
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=host)
            server = smtplib.SMTP_SSL()
        else:
            server = smtplib.SMTP()
            
        server._host = host # type: ignore
        server.sock = sock
        server.file = sock.makefile('rb')
        
        server.getreply()
        server.ehlo_or_helo_if_needed()
        
        if port != 465:
            server.starttls()
            server.ehlo_or_helo_if_needed()
            
        # Try login!
        server.login(user, password)
        server.quit()
        
        logger.info(f"Verified SMTP connection for user {user_id}")
        
    except smtplib.SMTPAuthenticationError:
        return jsonify({"error": "Authentication failed. Check your username and App Password."}), 401
    except Exception as e:
        logger.error(f"SMTP Verification error: {e}")
        return jsonify({"error": f"Connection failed: {str(e)}"}), 400
        
    # Save/Update config
    try:
        config = db.session.query(SmtpConfig).filter_by(user_id=user_id).first()
        encrypted_pass = encrypt_value(password)
        
        if config:
            config.smtp_host = host
            config.smtp_port = port
            config.smtp_user = user
            config.smtp_pass = encrypted_pass
        else:
            config = SmtpConfig(
                user_id=user_id,
                smtp_host=host,
                smtp_port=port,
                smtp_user=user,
                smtp_pass=encrypted_pass
            )
            db.session.add(config)
            
        db.session.commit()
        return jsonify({"message": "SMTP configuration saved successfully", "has_config": True}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to save SMTP config: {e}")
        return jsonify({"error": "Failed to save configuration."}), 500
