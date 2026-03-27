from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    CORS(app)
    
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

    # Setup DB
    db.init_app(app)

    # Register blueprints (routes)
    from app.routes.email_routes import email_bp
    from app.routes.campaign_routes import campaign_bp
    app.register_blueprint(email_bp)
    app.register_blueprint(campaign_bp)

    return app
