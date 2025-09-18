# config.py - Simplified configuration with SQLite
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    # Flask settings
    SECRET_KEY: str = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
    DEBUG: bool = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    TESTING: bool = False
    
    # Database - Using SQLite for simplicity
    @property
    def DATABASE_URL(self):
        db_path = os.environ.get('DATABASE_PATH', '/opt/zoom-eventbrite-app/data/app.db')
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return f'sqlite:///{db_path}'
    
    # API Credentials
    ZOOM_API_KEY: str = os.environ.get('ZOOM_API_KEY', '')
    ZOOM_API_SECRET: str = os.environ.get('ZOOM_API_SECRET', '')
    ZOOM_ACCOUNT_ID: str = os.environ.get('ZOOM_ACCOUNT_ID', '')
    
    EVENTBRITE_PRIVATE_TOKEN: str = os.environ.get('EVENTBRITE_PRIVATE_TOKEN', '')
    
    # Google OAuth
    GOOGLE_SSO_CLIENT_ID: str = os.environ.get('GOOGLE_SSO_CLIENT_ID', '')
    GOOGLE_SSO_CLIENT_SECRET: str = os.environ.get('GOOGLE_SSO_CLIENT_SECRET', '')
    ALLOWED_DOMAIN: str = os.environ.get('ALLOWED_DOMAIN', 'ohvoice.org')
    
    # File storage
    @property
    def UPLOAD_FOLDER(self):
        folder = os.environ.get('UPLOAD_FOLDER', '/opt/zoom-eventbrite-app/uploads')
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder
    
    @property
    def DOWNLOAD_FOLDER(self):
        folder = os.environ.get('DOWNLOAD_FOLDER', '/opt/zoom-eventbrite-app/downloads')
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder
    
    @property
    def CREDENTIALS_FOLDER(self):
        folder = os.environ.get('CREDENTIALS_FOLDER', '/opt/zoom-eventbrite-app/credentials')
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder
    
    MAX_CONTENT_LENGTH: int = int(os.environ.get('MAX_CONTENT_LENGTH', '104857600'))  # 100MB
    
    # YouTube
    @property
    def YOUTUBE_CREDENTIALS_PATH(self):
        return os.path.join(self.CREDENTIALS_FOLDER, 'youtube_token.json')
    
    @property
    def YOUTUBE_CLIENT_SECRETS_PATH(self):
        return os.path.join(self.CREDENTIALS_FOLDER, 'client_secrets.json')
    
    # Logging
    LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')
    
    @property
    def LOG_FILE(self):
        log_file = os.environ.get('LOG_FILE', '/opt/zoom-eventbrite-app/logs/app.log')
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        return log_file
    
    # Server settings
    HOST: str = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT: int = int(os.environ.get('FLASK_PORT', '5000'))
    WORKERS: int = int(os.environ.get('GUNICORN_WORKERS', '4'))
    TIMEOUT: int = int(os.environ.get('GUNICORN_TIMEOUT', '300'))
    
    # Domain and SSL
    DOMAIN: str = os.environ.get('DOMAIN', 'localhost')
    USE_SSL: bool = os.environ.get('USE_SSL', 'False').lower() == 'true'
    
    # YouTube video checking
    YOUTUBE_CHANNEL_ID: str = os.environ.get('YOUTUBE_CHANNEL_ID', '')
    CHECK_EXISTING_VIDEOS: bool = os.environ.get('CHECK_EXISTING_VIDEOS', 'True').lower() == 'true'
    
    def validate(self) -> list[str]:
        """Validate required configuration"""
        errors = []
        
        required_fields = [
            'ZOOM_API_KEY', 'ZOOM_API_SECRET', 'ZOOM_ACCOUNT_ID',
            'EVENTBRITE_PRIVATE_TOKEN', 'GOOGLE_SSO_CLIENT_ID', 'GOOGLE_SSO_CLIENT_SECRET'
        ]
        
        for field in required_fields:
            if not getattr(self, field):
                errors.append(f"Missing required configuration: {field}")
        
        return errors

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    DEBUG = True
    
    # Use local directories for development
    @property
    def DATABASE_URL(self):
        # Get path from environment or use default
        db_path = os.environ.get('DATABASE_PATH', './data/app.db')
        
        # Convert to absolute path if relative
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        
        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            Path(db_dir).mkdir(parents=True, exist_ok=True)
        
        return f'sqlite:///{db_path}'
    
    @property
    def UPLOAD_FOLDER(self):
        folder = os.environ.get('UPLOAD_FOLDER', './uploads')
        if not os.path.isabs(folder):
            folder = os.path.abspath(folder)
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder
    
    @property
    def DOWNLOAD_FOLDER(self):
        folder = os.environ.get('DOWNLOAD_FOLDER', './downloads')
        if not os.path.isabs(folder):
            folder = os.path.abspath(folder)
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder
    
    @property
    def CREDENTIALS_FOLDER(self):
        folder = os.environ.get('CREDENTIALS_FOLDER', './credentials')
        if not os.path.isabs(folder):
            folder = os.path.abspath(folder)
        Path(folder).mkdir(parents=True, exist_ok=True)
        return folder
    
    @property
    def LOG_FILE(self):
        log_file = os.environ.get('LOG_FILE', './logs/app.log')
        if not os.path.isabs(log_file):
            log_file = os.path.abspath(log_file)
        log_dir = os.path.dirname(log_file)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        return log_file

class TestingConfig(Config):
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'

# Factory function
def get_config() -> Config:
    env = os.environ.get('FLASK_ENV', 'production').lower()
    
    if env == 'development':
        return DevelopmentConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return ProductionConfig()