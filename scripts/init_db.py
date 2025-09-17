#!/usr/bin/env python3
"""Initialize the application database"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_prod import create_app
from models import init_db

def main():
    """Initialize the database"""
    app = create_app()
    
    with app.app_context():
        print("Initializing database...")
        init_db(app)
        print("Database initialization complete!")

if __name__ == '__main__':
    main()
