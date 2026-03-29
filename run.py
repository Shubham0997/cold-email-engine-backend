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
    from sqlalchemy import inspect, text
    
    db.create_all()
    
    # --- Lightweight migration: add user_id columns if missing ---
    inspector = inspect(db.engine)
    
    for table_name in ['emails', 'campaigns', 'smtp_configs']:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        if 'user_id' not in columns:
            logging.info(f"Migrating: Adding 'user_id' column to '{table_name}' table...")
            with db.engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN user_id VARCHAR(128)"))
                conn.commit()
            logging.info(f"Migration complete for '{table_name}'.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
