# routes/main.py - Main application routes
from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
@login_required
def index():
    """Main application page"""
    user = session.get('user', {})
    logger.info(f"User {user.get('email', 'unknown')} accessed main page")
    return render_template('index.html', user=user)

@main_bp.route('/health')
def health():
    """Health check endpoint"""
    return "healthy\n"
