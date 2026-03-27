from flask import Blueprint, request, jsonify, send_file
import re
import io
import logging
from app.services.email_service import EmailService
from app.repository.email_repository import EmailRepository

email_bp = Blueprint('email', __name__)
logger = logging.getLogger(__name__)

repository = EmailRepository()
service = EmailService(repository)

@email_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" # Simplified for now
    }), 200

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

@email_bp.route('/email/send-single', methods=['POST'])
def send_single_email():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    email = data.get('email')
    message = data.get('message')

    if not email or not is_valid_email(email):
        return jsonify({"error": "A valid 'email' is required"}), 400
    
    if not message or not str(message).strip():
        return jsonify({"error": "'message' cannot be empty"}), 400

    try:
        email_record = service.send_single_email(email, message)
        return jsonify({
            "email_id": email_record.id,
            "status": email_record.status
        }), 200
    except Exception as e:
        logger.error(f"Send single email completely failed: {e}")
        return jsonify({"error": "Internal server error"}), 500

@email_bp.route('/track/open/<string:email_id>', methods=['GET'])
def track_open(email_id):
    logger.info(f"Tracking endpoint hit for email_id: {email_id}")
    try:
        service.track_open(email_id)
    except Exception as e:
        logger.error(f"Error tracking {email_id}: {e}")
    
    # 1x1 transparent PNG pixel representation
    pixel_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff\xff\x7f\x06\x04\x00\x08\x99\x01\x18\x83\x11\n\x0e\x00\x00\x00\x00IEND\xaeB`\x82'
    
    return send_file(
        io.BytesIO(pixel_data),
        mimetype='image/png',
        as_attachment=False
    )

@email_bp.route('/email/stats', methods=['GET'])
def get_stats():
    try:
        stats = service.get_dashboard_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        return jsonify({"error": "Failed to fetch stats"}), 500
