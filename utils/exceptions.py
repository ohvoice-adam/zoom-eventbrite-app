"""Custom exceptions for the application"""

class ZoomAppException(Exception):
    """Base exception for the application"""
    pass

class APIError(ZoomAppException):
    """API related errors"""
    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.status_code = status_code

class AuthenticationError(ZoomAppException):
    """Authentication related errors"""
    pass

class ConfigurationError(ZoomAppException):
    """Configuration related errors"""
    pass

class YouTubeError(ZoomAppException):
    """YouTube API related errors"""
    pass

class ZoomError(ZoomAppException):
    """Zoom API related errors"""
    pass

class EventbriteError(ZoomAppException):
    """Eventbrite API related errors"""
    pass
