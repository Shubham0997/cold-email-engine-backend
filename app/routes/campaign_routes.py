import logging
from flask import Blueprint, request, jsonify
from app.services.email_service_campaign import CampaignService
from app.repository.campaign_repository import CampaignRepository
from app.services.email_service import EmailService
from app.repository.email_repository import EmailRepository

campaign_bp = Blueprint('campaign', __name__)
logger = logging.getLogger(__name__)

# Initialize dependencies
email_repo = EmailRepository()
email_service = EmailService(email_repo)
campaign_repo = CampaignRepository()
campaign_service = CampaignService(campaign_repo, email_service)

@campaign_bp.route('/campaigns', methods=['POST'])
def create_campaign():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    name = data.get('name')
    subject = data.get('subject')
    body = data.get('body')
    recipients = data.get('recipients', [])
    
    if not all([name, subject, body, recipients]):
        return jsonify({"error": "Missing required fields"}), 400
        
    try:
        campaign = campaign_service.create_campaign(name, subject, body, recipients)
        return jsonify(campaign.to_dict()), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create campaign: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500

@campaign_bp.route('/campaigns', methods=['GET'])
def get_campaigns():
    try:
        campaigns = campaign_service.get_all_campaigns()
        return jsonify([c.to_dict() for c in campaigns]), 200
    except Exception as e:
        logger.error(f"Failed to fetch campaigns: {e}")
        return jsonify({"error": str(e)}), 500

@campaign_bp.route('/campaigns/<campaign_id>', methods=['GET'])
def get_campaign_details(campaign_id):
    try:
        details = campaign_service.get_campaign_details(campaign_id)
        if not details:
            return jsonify({"error": "Campaign not found"}), 404
        return jsonify(details), 200
    except Exception as e:
        logger.error(f"Failed to fetch campaign details: {e}")
        return jsonify({"error": str(e)}), 500

@campaign_bp.route('/campaigns/<campaign_id>/start', methods=['POST'])
def start_campaign(campaign_id):
    try:
        # NOTE: This is a synchronous call for now. 
        # For large lists, this should be moved to a background task (e.g. Celery/Thread).
        campaign_service.start_campaign(campaign_id)
        return jsonify({"message": "Campaign started successfully"}), 200
    except Exception as e:
        logger.error(f"Failed to start campaign: {e}")
        return jsonify({"error": str(e)}), 500

@campaign_bp.route('/campaigns/<campaign_id>', methods=['PUT'])
def update_campaign(campaign_id):
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    name = data.get('name')
    subject = data.get('subject')
    body = data.get('body')
    recipients = data.get('recipients', [])
    
    if not all([name, subject, body, recipients]):
        return jsonify({"error": "Missing required fields"}), 400
        
    try:
        campaign = campaign_service.update_campaign(campaign_id, name, subject, body, recipients)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404
        return jsonify(campaign.to_dict()), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to update campaign: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500

@campaign_bp.route('/campaigns/<campaign_id>/reset', methods=['POST'])
def reset_campaign(campaign_id):
    try:
        campaign = campaign_service.reset_campaign(campaign_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404
        return jsonify(campaign.to_dict()), 200
    except Exception as e:
        logger.error(f"Failed to reset campaign: {e}")
        return jsonify({"error": str(e)}), 500
@campaign_bp.route('/campaigns/<campaign_id>', methods=['DELETE'])
def delete_campaign(campaign_id):
    try:
        success = campaign_service.delete_campaign(campaign_id)
        if not success:
            return jsonify({"error": "Campaign not found"}), 404
        return jsonify({"message": "Campaign deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Failed to delete campaign: {e}")
        return jsonify({"error": str(e)}), 500
