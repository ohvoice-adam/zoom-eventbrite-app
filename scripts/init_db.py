#!/usr/bin/env python3
"""Initialize the application database"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Initialize the database"""
    try:
        # Set development environment if not set
        if 'FLASK_ENV' not in os.environ:
            os.environ['FLASK_ENV'] = 'development'
            print("Setting FLASK_ENV=development")
        
        # Set database path if not set
        if 'DATABASE_PATH' not in os.environ:
            os.environ['DATABASE_PATH'] = './data/app.db'
            print("Setting DATABASE_PATH=./data/app.db")
        
        # Import after setting environment
        from models import db, init_db
        from config import get_config
        from flask import Flask
        from pathlib import Path
        
        # Create minimal Flask app for database initialization
        app = Flask(__name__)
        config = get_config()
        
        print(f"Using Flask environment: {os.environ.get('FLASK_ENV')}")
        print(f"Database path from config: {config.DATABASE_URL}")
        
        # Ensure the data directory exists
        db_url = config.DATABASE_URL
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            db_dir = os.path.dirname(db_path)
            if db_dir:
                Path(db_dir).mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {db_dir}")
        
        # Configure only what's needed for database
        app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URL
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database
        db.init_app(app)
        
        with app.app_context():
            print("Creating database tables...")
            db.create_all()
            print("Database initialization complete!")
            
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()