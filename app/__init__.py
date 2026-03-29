from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
import logging
import firebase_admin
from firebase_admin import credentials

db = SQLAlchemy()
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        if request.method == 'OPTIONS':
            response.status_code = 200
        return response
    
    # Configure Database
    database_url = os.getenv('DATABASE_URL')
    
    # SQLAlchemy requires 'postgresql://' instead of 'postgres://' (common in Heroku/Vercel/Neon)
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    if database_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        # Fallback to SQLite for local development
        basedir = os.path.abspath(os.path.dirname(__file__))
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '..', 'app.db')
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,  # Recycle connections every 5 minutes
    }

    # Initialize Firebase Admin SDK
    if not firebase_admin._apps:
        # Option 1: Explicit env vars (for Vercel production)
        project_id = os.getenv('FIREBASE_PROJECT_ID')
        client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
        private_key = os.getenv('FIREBASE_PRIVATE_KEY')

        if project_id and client_email and private_key:
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": project_id,
                "client_email": client_email,
                # Vercel sometimes escapes newlines in private keys, we need to unescape them
                "private_key": private_key.replace("\\n", "\n"),
            })
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized with env var credentials.")
        else:
            # Option 2: JSON file (for local development)
            cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if not cred_path:
                basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                local_key = os.path.join(basedir, 'firebase-service-account.json')
                if os.path.exists(local_key):
                    cred_path = local_key

            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info(f"Firebase Admin SDK initialized with credentials from: {cred_path}")
            else:
                try:
                    firebase_admin.initialize_app()
                    logger.info("Firebase Admin SDK initialized with default credentials.")
                except Exception as e:
                    logger.warning(
                        f"Firebase Admin SDK could not be initialized: {e}. "
                        f"Set FIREBASE_PROJECT_ID/CLIENT_EMAIL/PRIVATE_KEY env vars "
                        f"or place firebase-service-account.json in the backend/ directory."
                    )

    # Setup DB
    db.init_app(app)

    # Register blueprints (routes)
    from app.routes.email_routes import email_bp
    from app.routes.campaign_routes import campaign_bp
    from app.routes.ai_routes import ai_bp
    from app.routes.user_routes import user_bp
    
    app.register_blueprint(email_bp)
    app.register_blueprint(campaign_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(user_bp)

    return app
