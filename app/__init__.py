from flask import Flask, jsonify
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
    CORS(app, supports_credentials=True)
    
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
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        # Auto-discover service account key in the backend directory
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
                    f"Place firebase-service-account.json in the backend/ directory."
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
