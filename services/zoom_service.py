# services/zoom_service.py - Zoom API integration
import os
import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ZoomService:
    """Service for Zoom API integration"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.ZOOM_API_KEY
        self.api_secret = config.ZOOM_API_SECRET
        self.account_id = config.ZOOM_ACCOUNT_ID
        
    def get_access_token(self) -> Optional[str]:
        """Get OAuth access token from Zoom"""
        try:
            auth_url = 'https://zoom.us/oauth/token'
            auth_payload = {
                'grant_type': 'account_credentials',
                'account_id': self.account_id
            }
            
            response = requests.post(
                auth_url, 
                auth=(self.api_key, self.api_secret), 
                data=auth_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("Successfully obtained Zoom access token")
                return response.json()['access_token']
            else:
                logger.error(f"Failed to get Zoom token: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Exception getting Zoom token: {str(e)}")
            return None
    
    def get_users(self, access_token: str) -> List[Dict]:
        """Get list of users from Zoom account"""
        try:
            users_url = 'https://api.zoom.us/v2/users'
            headers = {'Authorization': f'Bearer {access_token}'}
            params = {
                'status': 'active',
                'page_size': 300
            }
            
            response = requests.get(users_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                
                user_list = []
                for user in users:
                    user_list.append({
                        'id': user.get('id'),
                        'email': user.get('email'),
                        'display_name': user.get('display_name', user.get('email', 'Unknown User')),
                        'first_name': user.get('first_name', ''),
                        'last_name': user.get('last_name', ''),
                        'type': user.get('type', 1)
                    })
                
                logger.info(f"Retrieved {len(user_list)} Zoom users")
                return user_list
            else:
                logger.error(f"Failed to get users: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Exception getting Zoom users: {str(e)}")
            return []
    
    def get_recordings(self, access_token: str, start_date: str, end_date: str, 
                      user_id: str = 'me') -> List[Dict]:
        """Get recordings for date range"""
        try:
            recordings = []
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            current_date = start_dt
            chunk_size = timedelta(days=30)
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            if user_id and user_id != 'me':
                recordings_url = f'https://api.zoom.us/v2/users/{user_id}/recordings'
            else:
                recordings_url = 'https://api.zoom.us/v2/users/me/recordings'
            
            while current_date <= end_dt:
                chunk_end = min(current_date + chunk_size, end_dt)
                
                from_date = current_date.strftime('%Y-%m-%d')
                to_date = chunk_end.strftime('%Y-%m-%d')
                
                params = {
                    'from': from_date,
                    'to': to_date,
                    'page_size': 300
                }
                
                logger.debug(f"Fetching recordings from {from_date} to {to_date}")
                
                response = requests.get(recordings_url, headers=headers, params=params, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    meetings = data.get('meetings', [])
                    
                    for meeting in meetings:
                        if meeting.get('recording_files'):
                            recordings.append({
                                'topic': meeting.get('topic', 'Untitled Meeting'),
                                'id': meeting.get('id'),
                                'start_time': meeting.get('start_time'),
                                'duration': meeting.get('duration', 0),
                                'recording_count': meeting.get('recording_count', 0),
                                'host_email': meeting.get('host_email', ''),
                                'recording_files': meeting.get('recording_files', [])
                            })
                else:
                    logger.warning(f"API error for chunk {from_date}-{to_date}: {response.status_code}")
                
                current_date = chunk_end + timedelta(days=1)
            
            logger.info(f"Retrieved {len(recordings)} meetings with recordings")
            return recordings
            
        except Exception as e:
            logger.error(f"Exception getting recordings: {str(e)}")
            return []
    
    def get_recording_files(self, access_token: str, meeting_id: str) -> List[Dict]:
        """Get recording files for a specific meeting"""
        try:
            details_url = f'https://api.zoom.us/v2/meetings/{meeting_id}/recordings'
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = requests.get(details_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json().get('recording_files', [])
            else:
                logger.error(f"Error fetching recording files for {meeting_id}: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Exception getting recording files: {str(e)}")
            return []
    
    def download_video(self, access_token: str, recording_file: Dict) -> Optional[str]:
        """Download a video file from Zoom"""
        try:
            download_url = recording_file.get('download_url')
            if not download_url:
                logger.error("No download URL in recording file")
                return None
            
            # Ensure download directory exists
            download_dir = Path(self.config.DOWNLOAD_FOLDER)
            download_dir.mkdir(parents=True, exist_ok=True)
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Use access token in URL as backup
            if '?' in download_url:
                download_url += f'&access_token={access_token}'
            else:
                download_url += f'?access_token={access_token}'
            
            response = requests.get(download_url, headers=headers, stream=True, timeout=300)
            
            if response.status_code == 200:
                file_extension = recording_file.get('file_type', 'mp4').lower()
                file_id = recording_file.get('id', 'temp')
                file_name = f"zoom_video_{file_id}.{file_extension}"
                file_path = download_dir / file_name
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                logger.info(f"Downloaded video: {file_name}")
                return str(file_path)
            else:
                logger.error(f"Download failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Exception downloading video: {str(e)}")
            return None
