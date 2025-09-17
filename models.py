# models.py - Database models for SQLite
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
import json
import enum

db = SQLAlchemy()

class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class User(db.Model):
    """User model for authenticated users"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    picture_url = db.Column(db.String(500))
    domain = db.Column(db.String(100), nullable=False)
    
    # Authentication tracking
    first_login = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    login_count = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    processing_jobs = db.relationship('ProcessingJob', backref='user', lazy=True, cascade='all, delete-orphan')
    zoom_accounts = db.relationship('ZoomAccount', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'picture_url': self.picture_url,
            'domain': self.domain,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class ZoomAccount(db.Model):
    """Zoom account credentials per user"""
    __tablename__ = 'zoom_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Zoom credentials (for multi-account support in future)
    account_id = db.Column(db.String(255), nullable=False)
    account_name = db.Column(db.String(255))
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<ZoomAccount {self.account_id}>'

class ProcessingJob(db.Model):
    """Background processing job tracking"""
    __tablename__ = 'processing_jobs'
    
    id = db.Column(db.String(36), primary_key=True)  # UUID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Job details
    status = db.Column(db.String(20), default='pending')  # Use string for SQLite
    job_type = db.Column(db.String(50), default='match_processing')
    
    # Progress tracking
    current_step = db.Column(db.Integer, default=0)
    total_steps = db.Column(db.Integer, default=0)
    
    # Job data (stored as JSON text in SQLite)
    input_data = db.Column(db.Text)  # JSON as text
    result_data = db.Column(db.Text)  # JSON as text
    
    # Messages and errors (stored as JSON text)
    messages = db.Column(db.Text, default='[]')  # JSON array as text
    error_message = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)  # Auto-cleanup after 24h
    
    def __repr__(self):
        return f'<ProcessingJob {self.id}: {self.status}>'
    
    @property
    def messages_list(self):
        """Get messages as Python list"""
        try:
            return json.loads(self.messages or '[]')
        except:
            return []
    
    @messages_list.setter
    def messages_list(self, value):
        """Set messages as Python list"""
        self.messages = json.dumps(value or [])
    
    def add_message(self, message):
        """Add a message to the job"""
        messages = self.messages_list
        messages.append(message)
        self.messages_list = messages
    
    def to_dict(self):
        return {
            'id': self.id,
            'status': self.status,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'messages': self.messages_list,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress_percent': (self.current_step / self.total_steps * 100) if self.total_steps > 0 else 0
        }

class EventMatch(db.Model):
    """Store matched events for audit trail"""
    __tablename__ = 'event_matches'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    processing_job_id = db.Column(db.String(36), db.ForeignKey('processing_jobs.id'))
    
    # Match details
    zoom_meeting_id = db.Column(db.String(100), nullable=False)
    zoom_meeting_topic = db.Column(db.String(500))
    zoom_start_time = db.Column(db.DateTime)
    
    eventbrite_event_id = db.Column(db.String(100))
    eventbrite_event_name = db.Column(db.String(500))
    eventbrite_start_time = db.Column(db.DateTime)
    
    # Processing results
    video_downloaded = db.Column(db.Boolean, default=False)
    video_file_path = db.Column(db.String(1000))
    video_file_size = db.Column(db.Integer)
    
    youtube_uploaded = db.Column(db.Boolean, default=False)
    youtube_video_id = db.Column(db.String(100))
    youtube_url = db.Column(db.String(500))
    
    # Status and timestamps
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<EventMatch {self.zoom_meeting_id} -> {self.eventbrite_event_id}>'

class YouTubeVideo(db.Model):
    """Cache of existing YouTube videos for duplicate checking"""
    __tablename__ = 'youtube_videos'
    
    id = db.Column(db.Integer, primary_key=True)
    youtube_video_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    title_normalized = db.Column(db.String(500))  # Lowercase, no special chars for matching
    description = db.Column(db.Text)
    published_at = db.Column(db.DateTime)
    duration = db.Column(db.String(20))  # ISO 8601 duration format
    view_count = db.Column(db.Integer, default=0)
    
    # For matching with events
    channel_id = db.Column(db.String(100))
    privacy_status = db.Column(db.String(20))
    
    # Cache management
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<YouTubeVideo {self.title[:50]}...>'
    
    @staticmethod
    def normalize_title(title):
        """Normalize title for matching"""
        import re
        if not title:
            return ''
        # Convert to lowercase, remove special characters, normalize whitespace
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def matches_title(self, other_title):
        """Check if this video's title matches another title"""
        other_normalized = self.normalize_title(other_title)
        return self.title_normalized == other_normalized

class SystemSettings(db.Model):
    """System-wide configuration settings"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')  # string, int, bool, json
    description = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemSettings {self.key}>'
    
    @classmethod
    def get_value(cls, key, default=None):
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            return default
        
        if setting.value_type == 'int':
            try:
                return int(setting.value)
            except (ValueError, TypeError):
                return default
        elif setting.value_type == 'bool':
            return setting.value.lower() in ('true', '1', 'yes')
        elif setting.value_type == 'json':
            try:
                return json.loads(setting.value)
            except (ValueError, TypeError):
                return default
        else:
            return setting.value
    
    @classmethod 
    def set_value(cls, key, value, value_type='string', description=None):
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            setting = cls(key=key)
            db.session.add(setting)
        
        setting.value = str(value)
        setting.value_type = value_type
        if description:
            setting.description = description
        setting.updated_at = datetime.utcnow()
        
        db.session.commit()
        return setting

# Database initialization
def init_db(app=None):
    """Initialize database with default data"""
    if app:
        with app.app_context():
            db.create_all()
    else:
        db.create_all()
    
    # Add default system settings
    default_settings = [
        ('max_video_size_mb', '500', 'int', 'Maximum video file size in MB'),
        ('youtube_upload_enabled', 'true', 'bool', 'Enable YouTube uploads'),
        ('auto_cleanup_days', '7', 'int', 'Days to keep downloaded files'),
        ('max_concurrent_jobs', '3', 'int', 'Maximum concurrent processing jobs'),
        ('youtube_cache_hours', '24', 'int', 'Hours to cache YouTube video list'),
        ('check_existing_videos', 'true', 'bool', 'Check for existing YouTube videos before upload')
    ]
    
    for key, value, value_type, description in default_settings:
        if not SystemSettings.query.filter_by(key=key).first():
            setting = SystemSettings(
                key=key,
                value=value, 
                value_type=value_type,
                description=description
            )
            db.session.add(setting)
    
    try:
        db.session.commit()
        print("Database initialized successfully")
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing database: {e}")
        raise
