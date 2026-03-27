from flask import Blueprint, request, jsonify
from app.services.ai_service import ai_service

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

@ai_bp.route('/research', methods=['POST'])
def research():
    data = request.json
    prompt = data.get('prompt')
    
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
        
    result = ai_service.research_email(prompt)
    
    if "error" in result:
        return jsonify(result), 500
        
    return jsonify(result)
