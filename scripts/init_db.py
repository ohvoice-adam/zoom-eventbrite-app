#!/usr/bin/env python3
"""Initialize the application database"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Initialize the database"""
    try:
        # Import after adding to path
        from models import db, init_db
        from config import get_config
        from flask import Flask
        
        # Create minimal Flask app for database initialization
        app = Flask(__name__)
        config = get_config()
        
        # Configure only what's needed for database
        app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URL
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database
        db.init_app(app)
        
        with app.app_context():
            print("Initializing database...")
            init_db(app)
            print("Database initialization complete!")
            
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
