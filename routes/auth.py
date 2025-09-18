# routes/auth.py - Authentication routes
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
import googleapiclient.discovery
from google_auth_oauthlib.flow import Flow
import logging
import os

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

def create_google_oauth_flow():
    """Create Google OAuth flow for SSO"""
    # Get credentials from config
    client_id = current_app.config.get('GOOGLE_SSO_CLIENT_ID')
    client_secret = current_app.config.get('GOOGLE_SSO_CLIENT_SECRET')
    
    # Check if credentials are dummy/missing
    if not client_id or not client_secret or 'dummy' in client_id or 'your_' in client_id:
        logger.error("Google OAuth credentials not properly configured")
        logger.error(f"Client ID: {client_id[:20]}..." if client_id else "Not set")
        raise ValueError("Google OAuth not properly configured. Please add real credentials to .env file.")
    
    # Get the proper redirect URI based on the request
    redirect_uri = request.url_root.rstrip('/') + '/callback'
    
    # Handle localhost vs IP access
    if request.host.startswith('localhost'):
        redirect_uri = redirect_uri.replace('localhost', '127.0.0.1')
    
    logger.info(f"OAuth redirect URI: {redirect_uri}")
    
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
            "javascript_origins": [request.url_root.rstrip('/')]
        }
    }
    
    scopes = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ]
    
    # Disable HTTPS requirement for local development
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' if current_app.debug else '0'
    
    try:
        flow = Flow.from_client_config(client_config, scopes=scopes)
        flow.redirect_uri = redirect_uri
        return flow
    except Exception as e:
        logger.error(f"Error creating OAuth flow: {str(e)}")
        raise

@auth_bp.route('/login')
def login():
    """Initiate Google OAuth login"""
    if 'user' in session:
        return redirect(url_for('main.index'))
    
    try:
        flow = create_google_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='select_account'
        )
        session['oauth_state'] = state
        logger.info(f"Redirecting to Google OAuth: {authorization_url[:100]}...")
        return redirect(authorization_url)
        
    except ValueError as e:
        logger.error(f"OAuth configuration error: {str(e)}")
        flash(str(e), 'error')
        return render_template('login.html')
    except Exception as e:
        logger.error(f"Error initiating OAuth: {str(e)}")
        flash('Authentication error. Please check the configuration and try again.', 'error')
        return render_template('login.html')

@auth_bp.route('/callback')
def callback():
    """Handle Google OAuth callback"""
    if 'oauth_state' not in session:
        logger.warning("No OAuth state in session")
        flash('Authentication error. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        flow = create_google_oauth_flow()
        flow.fetch_token(authorization_response=request.url)
        
        # Get user info from Google
        credentials = flow.credentials
        user_info_service = googleapiclient.discovery.build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        
        # Use auth service to create/update user
        auth_service = current_app.auth_service
        user = auth_service.create_or_update_user(user_info)
        
        if not user:
            error_msg = f'Access denied. Only {auth_service.allowed_domain} users are allowed.'
            flash(error_msg, 'error')
            logger.warning(f"Access denied for {user_info.get('email', 'unknown')}")
            return render_template('login.html', error=error_msg)
        
        # Store user info in session
        session['user'] = user.to_dict()
        session.pop('oauth_state', None)
        
        logger.info(f"User {user.email} logged in successfully")
        flash(f'Welcome, {user.name}!', 'success')
        return redirect(url_for('main.index'))
        
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
def logout():
    """Log out user"""
    user_email = session.get('user', {}).get('email', 'unknown')
    session.clear()
    logger.info(f"User {user_email} logged out")
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))