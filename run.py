import os
import logging
from dotenv import load_dotenv
from app import create_app

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

load_dotenv()

app = create_app()

# Ensure database tables are created on startup (useful for serverless environments)
with app.app_context():
    from app.domain.models import db
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
