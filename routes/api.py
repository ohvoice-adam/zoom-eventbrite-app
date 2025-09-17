# routes/api.py - API routes
from flask import Blueprint, request, jsonify, session, current_app
from functools import wraps
from dateutil.parser import parse
import uuid
import threading
import logging
import os

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

def api_login_required(f):
    """Decorator to require authentication for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/organizations')
@api_login_required
def get_organizations():
    """Get Eventbrite organizations"""
    try:
        eventbrite_service = current_app.eventbrite_service
        organizations = eventbrite_service.get_organizations()
        return jsonify({'organizations': organizations})
        
    except Exception as e:
        logger.error(f"Error getting organizations: {str(e)}")
        return jsonify({'error': 'Failed to get organizations'}), 500

@api_bp.route('/users')
@api_login_required  
def get_users():
    """Get Zoom users"""
    try:
        zoom_service = current_app.zoom_service
        
        # Get access token
        access_token = zoom_service.get_access_token()
        if not access_token:
            return jsonify({'error': 'Failed to get Zoom access token'}), 500
        
        users = zoom_service.get_users(access_token)
        return jsonify({'users': users})
        
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        return jsonify({'error': 'Failed to get users'}), 500

@api_bp.route('/meetings', methods=['POST'])
@api_login_required
def get_meetings():
    """Get Zoom meetings with recordings"""
    try:
        data = request.json
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        user_id = data.get('user_id', 'me')
        
        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400
        
        zoom_service = current_app.zoom_service
        
        # Get access token
        access_token = zoom_service.get_access_token()
        if not access_token:
            return jsonify({'error': 'Failed to get Zoom access token'}), 500
        
        meetings = zoom_service.get_recordings(access_token, start_date, end_date, user_id)
        return jsonify({'meetings': meetings})
        
    except Exception as e:
        logger.error(f"Error getting meetings: {str(e)}")
        return jsonify({'error': 'Failed to get meetings'}), 500

@api_bp.route('/events', methods=['POST'])
@api_login_required
def get_events():
    """Get Eventbrite events with YouTube video checking"""
    try:
        data = request.json
        meeting_date = data.get('meeting_date')
        organization_id = data.get('organization_id')
        
        if not meeting_date or not organization_id:
            return jsonify({'error': 'Meeting date and organization ID are required'}), 400
        
        # Parse the date
        try:
            if meeting_date.endswith('Z'):
                event_date = parse(meeting_date.replace('Z', '+00:00'))
            else:
                event_date = parse(meeting_date)
        except Exception as e:
            return jsonify({'error': f'Invalid date format: {meeting_date}'}), 400
        
        eventbrite_service = current_app.eventbrite_service
        events = eventbrite_service.get_events_by_date(organization_id, event_date)
        
        # Check each event against existing YouTube videos
        youtube_service = current_app.youtube_service
        if youtube_service.is_authenticated():
            for event in events:
                event_title = event.get('name', {}).get('text', '')
                existing_video = youtube_service.check_existing_video(event_title)
                
                event['youtube_exists'] = existing_video is not None
                if existing_video:
                    event['youtube_video'] = existing_video
        else:
            # Add default values if YouTube checking is disabled
            for event in events:
                event['youtube_exists'] = False
                event['youtube_video'] = None
        
        return jsonify({'events': events})
        
    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
        return jsonify({'error': 'Failed to get events'}), 500

@api_bp.route('/process_matches', methods=['POST'])
@api_login_required
def process_matches():
    """Start background processing of confirmed matches"""
    try:
        data = request.json
        matches = data.get('matches', [])
        
        if not matches:
            return jsonify({'error': 'No matches provided'}), 400
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        user_id = session['user']['id']
        
        # Import the background processing function
        from app_prod import process_matches_background
        
        # Start background thread
        thread = threading.Thread(
            target=process_matches_background,
            args=(matches, session_id, current_app._get_current_object())
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started processing job {session_id} for user {user_id}")
        return jsonify({'session_id': session_id})
        
    except Exception as e:
        logger.error(f"Error starting processing: {str(e)}")
        return jsonify({'error': 'Failed to start processing'}), 500

@api_bp.route('/processing_status/<session_id>')
@api_login_required
def get_processing_status(session_id):
    """Get status of background processing job"""
    try:
        # Import the global processing status
        from app_prod import processing_status
        
        status = processing_status.get(session_id, {'status': 'not_found'})
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}")
        return jsonify({'error': 'Failed to get status'}), 500

@api_bp.route('/youtube/status')
@api_login_required
def youtube_status():
    """Get YouTube authentication status"""
    try:
        youtube_service = current_app.youtube_service
        status = youtube_service.get_auth_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting YouTube status: {str(e)}")
        return jsonify({'error': 'Failed to get YouTube status'}), 500

@api_bp.route('/youtube/refresh_cache', methods=['POST'])
@api_login_required
def refresh_youtube_cache():
    """Refresh YouTube video cache"""
    try:
        youtube_service = current_app.youtube_service
        
        if not youtube_service.is_authenticated():
            return jsonify({'error': 'YouTube not authenticated'}), 401
        
        count = youtube_service.refresh_video_cache()
        logger.info(f"Refreshed YouTube cache with {count} videos")
        return jsonify({'cached_videos': count})
        
    except Exception as e:
        logger.error(f"Error refreshing YouTube cache: {str(e)}")
        return jsonify({'error': 'Failed to refresh cache'}), 500
