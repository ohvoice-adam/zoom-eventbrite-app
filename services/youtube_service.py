# services/youtube_service.py - YouTube integration with video checking
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from models import db, YouTubeVideo, SystemSettings

logger = logging.getLogger(__name__)

class YouTubeService:
    """Service for YouTube integration and video management"""
    
    def __init__(self, config):
        self.config = config
        self.service = None
        self.channel_id = config.YOUTUBE_CHANNEL_ID
        
    def get_service(self):
        """Get authenticated YouTube service"""
        if self.service:
            return self.service
            
        credentials_path = self.config.YOUTUBE_CREDENTIALS_PATH
        
        if not os.path.exists(credentials_path):
            logger.warning(f"YouTube credentials not found at {credentials_path}")
            return None
            
        try:
            # Load credentials
            creds = Credentials.from_authorized_user_file(
                credentials_path, 
                ['https://www.googleapis.com/auth/youtube.upload',
                 'https://www.googleapis.com/auth/youtube.readonly']
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                logger.info("Refreshing YouTube credentials")
                creds.refresh(Request())
                
                # Save refreshed credentials
                with open(credentials_path, 'w') as f:
                    f.write(creds.to_json())
            
            if not creds.valid:
                logger.error("YouTube credentials are not valid")
                return None
                
            # Create service
            self.service = googleapiclient.discovery.build('youtube', 'v3', credentials=creds)
            logger.info("YouTube service authenticated successfully")
            return self.service
            
        except Exception as e:
            logger.error(f"Error creating YouTube service: {str(e)}")
            return None
    
    def check_existing_video(self, title: str) -> Optional[Dict]:
        """Check if a video with the given title already exists"""
        if not self.config.CHECK_EXISTING_VIDEOS:
            return None
            
        # First check cached videos
        normalized_title = YouTubeVideo.normalize_title(title)
        cached_video = YouTubeVideo.query.filter_by(title_normalized=normalized_title).first()
        
        if cached_video:
            # Check if cache is still fresh
            cache_hours = SystemSettings.get_value('youtube_cache_hours', 24)
            cache_expiry = cached_video.last_updated + timedelta(hours=cache_hours)
            
            if datetime.utcnow() < cache_expiry:
                logger.info(f"Found cached video match for '{title}': {cached_video.youtube_video_id}")
                return {
                    'video_id': cached_video.youtube_video_id,
                    'title': cached_video.title,
                    'url': f'https://www.youtube.com/watch?v={cached_video.youtube_video_id}',
                    'published_at': cached_video.published_at,
                    'cached': True
                }
        
        # If not in cache or cache expired, search YouTube
        return self._search_youtube_for_title(title)
    
    def _search_youtube_for_title(self, title: str) -> Optional[Dict]:
        """Search YouTube for videos with similar title"""
        service = self.get_service()
        if not service:
            return None
            
        try:
            # Search parameters
            search_params = {
                'part': 'snippet',
                'q': title,
                'type': 'video',
                'maxResults': 50,  # Check more results for better matching
                'order': 'relevance'
            }
            
            # If we have a specific channel, search only in that channel
            if self.channel_id:
                search_params['channelId'] = self.channel_id
            
            logger.info(f"Searching YouTube for title: '{title}'")
            search_response = service.search().list(**search_params).execute()
            
            normalized_search_title = YouTubeVideo.normalize_title(title)
            
            # Check each result for exact title match
            for item in search_response.get('items', []):
                video_title = item['snippet']['title']
                video_id = item['id']['videoId']
                
                # Check for exact match after normalization
                if YouTubeVideo.normalize_title(video_title) == normalized_search_title:
                    logger.info(f"Found exact title match: {video_id}")
                    
                    # Cache this result
                    self._cache_video(item)
                    
                    return {
                        'video_id': video_id,
                        'title': video_title,
                        'url': f'https://www.youtube.com/watch?v={video_id}',
                        'published_at': datetime.fromisoformat(item['snippet']['publishedAt'].replace('Z', '+00:00')),
                        'cached': False
                    }
            
            logger.info(f"No exact title match found for '{title}'")
            return None
            
        except Exception as e:
            logger.error(f"Error searching YouTube: {str(e)}")
            return None
    
    def _cache_video(self, youtube_item: Dict):
        """Cache a YouTube video in the database"""
        try:
            video_id = youtube_item['id']['videoId']
            snippet = youtube_item['snippet']
            
            # Check if already exists
            existing = YouTubeVideo.query.filter_by(youtube_video_id=video_id).first()
            
            if existing:
                # Update existing
                existing.title = snippet['title']
                existing.title_normalized = YouTubeVideo.normalize_title(snippet['title'])
                existing.description = snippet.get('description', '')
                existing.last_updated = datetime.utcnow()
            else:
                # Create new
                video = YouTubeVideo(
                    youtube_video_id=video_id,
                    title=snippet['title'],
                    title_normalized=YouTubeVideo.normalize_title(snippet['title']),
                    description=snippet.get('description', ''),
                    published_at=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                    channel_id=snippet.get('channelId', ''),
                    last_updated=datetime.utcnow()
                )
                db.session.add(video)
            
            db.session.commit()
            logger.debug(f"Cached video: {snippet['title']}")
            
        except Exception as e:
            logger.error(f"Error caching video: {str(e)}")
            db.session.rollback()
    
    def upload_video(self, file_path: str, title: str, description: str = '', 
                    recording_date: Optional[datetime] = None, 
                    check_existing: bool = True) -> Optional[Dict]:
        """Upload video to YouTube with duplicate checking"""
        
        # Check for existing video first
        if check_existing:
            existing = self.check_existing_video(title)
            if existing:
                logger.warning(f"Video with title '{title}' already exists: {existing['video_id']}")
                return {
                    'success': False,
                    'error': 'Video already exists',
                    'existing_video': existing
                }
        
        service = self.get_service()
        if not service:
            return {
                'success': False,
                'error': 'YouTube service not available'
            }
        
        try:
            # Prepare request body
            request_body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': ['event', 'recording'],
                    'categoryId': '22'  # People & Blogs
                },
                'status': {
                    'privacyStatus': 'private',  # Start as private
                    'selfDeclaredMadeForKids': False
                }
            }
            
            if recording_date:
                request_body['recordingDetails'] = {
                    'recordingDate': recording_date.isoformat()
                }
            
            # Create media file upload
            media_file = googleapiclient.http.MediaFileUpload(
                file_path, 
                chunksize=-1, 
                resumable=True
            )
            
            logger.info(f"Starting upload: '{title}'")
            
            # Execute upload
            upload_response = service.videos().insert(
                part='snippet,status,recordingDetails',
                body=request_body,
                media_body=media_file
            ).execute()
            
            video_id = upload_response.get('id')
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            
            logger.info(f"Upload successful: {video_id}")
            
            # Cache the uploaded video
            cache_item = {
                'id': {'videoId': video_id},
                'snippet': upload_response['snippet']
            }
            self._cache_video(cache_item)
            
            return {
                'success': True,
                'video_id': video_id,
                'url': video_url,
                'title': upload_response['snippet']['title']
            }
            
        except googleapiclient.errors.HttpError as e:
            error_content = json.loads(e.content.decode()) if e.content else {}
            error_message = error_content.get('error', {}).get('message', str(e))
            
            logger.error(f"YouTube API error uploading '{title}': {error_message}")
            
            return {
                'success': False,
                'error': f'YouTube API error: {error_message}',
                'status_code': e.resp.status
            }
            
        except Exception as e:
            logger.error(f"Unexpected error uploading '{title}': {str(e)}")
            return {
                'success': False,
                'error': f'Upload failed: {str(e)}'
            }
    
    def refresh_video_cache(self, max_results: int = 200) -> int:
        """Refresh the cache of YouTube videos"""
        service = self.get_service()
        if not service:
            logger.warning("Cannot refresh cache - YouTube service not available")
            return 0
            
        try:
            logger.info("Refreshing YouTube video cache...")
            cached_count = 0
            next_page_token = None
            
            while cached_count < max_results:
                # Search parameters
                search_params = {
                    'part': 'snippet',
                    'type': 'video',
                    'maxResults': min(50, max_results - cached_count),
                    'order': 'date'  # Get most recent videos
                }
                
                if self.channel_id:
                    search_params['channelId'] = self.channel_id
                else:
                    # If no specific channel, search for videos from our uploads
                    search_params['forMine'] = True
                
                if next_page_token:
                    search_params['pageToken'] = next_page_token
                
                response = service.search().list(**search_params).execute()
                
                # Cache each video
                for item in response.get('items', []):
                    self._cache_video(item)
                    cached_count += 1
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            logger.info(f"Cached {cached_count} videos")
            return cached_count
            
        except Exception as e:
            logger.error(f"Error refreshing video cache: {str(e)}")
            return 0
    
    def is_authenticated(self) -> bool:
        """Check if YouTube service is authenticated"""
        return self.get_service() is not None
    
    def get_auth_status(self) -> Dict:
        """Get detailed authentication status"""
        credentials_path = self.config.YOUTUBE_CREDENTIALS_PATH
        
        if not os.path.exists(credentials_path):
            return {
                'authenticated': False,
                'status': 'no_token_file',
                'message': 'YouTube token file not found'
            }
        
        try:
            creds = Credentials.from_authorized_user_file(credentials_path)
            
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    return {
                        'authenticated': True,
                        'status': 'expired_but_refreshable',
                        'message': 'Token expired but can be refreshed'
                    }
                else:
                    return {
                        'authenticated': False,
                        'status': 'invalid_token',
                        'message': 'Token is invalid and cannot be refreshed'
                    }
            
            # Test API call
            service = self.get_service()
            if service:
                return {
                    'authenticated': True,
                    'status': 'valid',
                    'message': 'YouTube API authenticated successfully'
                }
            else:
                return {
                    'authenticated': False,
                    'status': 'service_error',
                    'message': 'Failed to create YouTube service'
                }
                
        except Exception as e:
            return {
                'authenticated': False,
                'status': 'error',
                'message': f'Authentication error: {str(e)}'
            }
