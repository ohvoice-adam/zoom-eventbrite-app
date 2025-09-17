# services/auth_service.py - Authentication service
import logging
from typing import Dict, Optional
from models import db, User
from datetime import datetime

logger = logging.getLogger(__name__)

class AuthService:
    """Service for user authentication and management"""
    
    def __init__(self, config):
        self.config = config
        self.allowed_domain = config.ALLOWED_DOMAIN
    
    def create_or_update_user(self, user_info: Dict) -> Optional[User]:
        """Create or update user from OAuth info"""
        try:
            email = user_info.get('email', '').lower()
            
            if not email:
                logger.error("No email provided in user info")
                return None
            
            # Check domain restriction
            if not email.endswith(f'@{self.allowed_domain}'):
                logger.warning(f"User {email} not from allowed domain {self.allowed_domain}")
                return None
            
            # Find existing user or create new
            user = User.query.filter_by(email=email).first()
            
            if user:
                # Update existing user
                user.name = user_info.get('name', user.name)
                user.picture_url = user_info.get('picture', user.picture_url)
                user.last_login = datetime.utcnow()
                user.login_count = (user.login_count or 0) + 1
            else:
                # Create new user
                domain = email.split('@')[1]
                user = User(
                    email=email,
                    name=user_info.get('name', email.split('@')[0]),
                    picture_url=user_info.get('picture', ''),
                    domain=domain,
                    first_login=datetime.utcnow(),
                    last_login=datetime.utcnow(),
                    login_count=1
                )
                db.session.add(user)
            
            db.session.commit()
            logger.info(f"User {email} authenticated successfully")
            return user
            
        except Exception as e:
            logger.error(f"Error creating/updating user: {str(e)}")
            db.session.rollback()
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        return User.query.filter_by(email=email.lower()).first()
    
    def is_domain_allowed(self, email: str) -> bool:
        """Check if email domain is allowed"""
        return email.lower().endswith(f'@{self.allowed_domain}')
