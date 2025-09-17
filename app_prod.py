# app_prod.py - Production app with YouTube checking and SQLite
import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import uuid
import threading
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import secrets

from config import get_config
from models import db, User, ProcessingJob, EventMatch, YouTubeVideo, SystemSettings, init_db

# Initialize configuration
config = get_config()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    
    # Trust proxy headers (for nginx)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Initialize extensions
    db.init_app(app)
    
    # Configure logging
    setup_logging(app)
    
    # Validate configuration
    config_errors = config.validate()
    if config_errors:
        app.logger.error("Configuration errors: %s", config_errors)
        if not config.DEBUG:
            flash("Configuration errors detected. Check logs.", "error")
    
    # Initialize services
    from services.youtube_service import YouTubeService
    from services.zoom_service import ZoomService
    from services.eventbrite_service import EventbriteService
    from services.auth_service import AuthService
    
    app.youtube_service = YouTubeService(config)
    app.zoom_service = ZoomService(config)
    app.eventbrite_service = EventbriteService(config)
    app.auth_service = AuthService(config)
    
    # Create database tables
    with app.app_context():
        init_db(app)
    
    # Register routes
    register_routes(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    return app

def setup_logging(app):
    """Configure application logging"""
    if not app.debug and not app.testing:
        # File handler with rotation
        file_handler = RotatingFileHandler(
            config.LOG_FILE, maxBytes=10240000, backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        app.logger.info('Application startup')

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.error("Unexpected error: %s\n%s", str(error), traceback.format_exc())
        if app.debug:
            raise error
        return jsonify({'error': 'Internal server error'}), 500

# Store processing status globally for simple implementation
processing_status = {}

def login_required(f):
    """Decorator to require Google SSO authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def process_matches_background(matches, session_id, app):
    """Process confirmed matches in the background with YouTube checking"""
    global processing_status
    
    with app.app_context():
        print(f"DEBUG: Background processing started for session {session_id}", flush=True)
        
        processing_status[session_id] = {
            'status': 'processing',
            'current': 0,
            'total': len(matches),
            'messages': []
        }
        
        try:
            # Get services
            zoom_service = app.zoom_service
            youtube_service = app.youtube_service
            
            # Get Zoom token
            zoom_token = zoom_service.get_access_token()
            if not zoom_token:
                processing_status[session_id]['status'] = 'error'
                processing_status[session_id]['messages'].append('Failed to get Zoom access token')
                return
            
            youtube_available = youtube_service.is_authenticated()
            
            if not youtube_available:
                processing_status[session_id]['messages'].append('YouTube not authenticated - videos will be downloaded only')
            
            for i, match in enumerate(matches):
                processing_status[session_id]['current'] = i + 1
                
                meeting = match['zoom_meeting']
                eventbrite_event = match['eventbrite_event']
                event_title = eventbrite_event.get('name', {}).get('text', 'Untitled')
                
                processing_status[session_id]['messages'].append(f"Processing: {event_title}")
                
                # Check if video already exists on YouTube
                if youtube_available:
                    existing_video = youtube_service.check_existing_video(event_title)
                    if existing_video:
                        processing_status[session_id]['messages'].append(
                            f"Video already exists on YouTube: {event_title} ({existing_video['video_id']})"
                        )
                        continue
                
                # Get recording files
                recording_files = zoom_service.get_recording_files(zoom_token, meeting['id'])
                if not recording_files:
                    processing_status[session_id]['messages'].append(f"No recording files found for: {event_title}")
                    continue
                
                # Find video file
                video_file = None
                for rec_file in recording_files:
                    if rec_file.get('file_type', '').upper() == 'MP4':
                        video_file = rec_file
                        break
                
                if not video_file:
                    processing_status[session_id]['messages'].append(f"No MP4 video found for: {event_title}")
                    continue
                
                # Download video
                video_path = zoom_service.download_video(zoom_token, video_file)
                if not video_path:
                    processing_status[session_id]['messages'].append(f"Failed to download video for: {event_title}")
                    continue
                
                processing_status[session_id]['messages'].append(f"Downloaded: {event_title}")
                
                # Upload to YouTube if authenticated
                if youtube_available:
                    upload_result = youtube_service.upload_video(
                        video_path, 
                        event_title,
                        f"Event recording from {meeting.get('start_time', '')}"
                    )
                    
                    if upload_result and upload_result.get('success'):
                        processing_status[session_id]['messages'].append(
                            f"Uploaded to YouTube: {event_title} ({upload_result['video_id']})"
                        )
                    else:
                        error_msg = upload_result.get('error', 'Unknown error') if upload_result else 'Upload failed'
                        processing_status[session_id]['messages'].append(
                            f"YouTube upload failed for {event_title}: {error_msg}"
                        )
            
            processing_status[session_id]['status'] = 'completed'
            
        except Exception as e:
            print(f"DEBUG: Exception in background processing: {str(e)}", flush=True)
            processing_status[session_id]['status'] = 'error'
            processing_status[session_id]['messages'].append(f"Error: {str(e)}")

def register_routes(app):
    """Register all application routes"""
    
    # Import route blueprints
    from routes.auth import auth_bp
    from routes.api import api_bp
    from routes.main import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(main_bp)

# Create the Flask app
app = create_app()

if __name__ == '__main__':
    if config.DEBUG:
        print(f"Starting development server on {config.HOST}:{config.PORT}")
        app.run(debug=True, host=config.HOST, port=config.PORT)
    else:
        print("Use gunicorn for production deployment")
        print(f"gunicorn --bind {config.HOST}:{config.PORT} --workers {config.WORKERS} --timeout {config.TIMEOUT} app_prod:app")
