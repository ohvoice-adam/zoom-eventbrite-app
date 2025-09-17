# services/eventbrite_service.py - Eventbrite API integration
import requests
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class EventbriteService:
    """Service for Eventbrite API integration"""
    
    def __init__(self, config):
        self.config = config
        self.private_token = config.EVENTBRITE_PRIVATE_TOKEN
        self.base_url = 'https://www.eventbriteapi.com/v3'
        
    def get_organizations(self) -> List[Dict]:
        """Get all organizations the user belongs to"""
        try:
            orgs_url = f'{self.base_url}/users/me/organizations/'
            headers = {'Authorization': f'Bearer {self.private_token}'}
            
            response = requests.get(orgs_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                orgs = response.json().get('organizations', [])
                logger.info(f"Retrieved {len(orgs)} Eventbrite organizations")
                return orgs
            else:
                logger.error(f"Failed to get organizations: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Exception getting organizations: {str(e)}")
            return []
    
    def get_events_by_date(self, organization_id: str, event_date: datetime) -> List[Dict]:
        """Get events for a specific date and organization"""
        try:
            search_url = f'{self.base_url}/organizations/{organization_id}/events/'
            headers = {'Authorization': f'Bearer {self.private_token}'}
            
            date_str = event_date.strftime('%Y-%m-%d')
            
            params = {
                'start_date.range_start': date_str,
                'start_date.range_end': date_str,
                'expand': 'description'
            }
            
            logger.debug(f"Searching events for {date_str} in org {organization_id}")
            
            response = requests.get(search_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                events = response.json().get('events', [])
                logger.info(f"Found {len(events)} events for {date_str}")
                return events
            else:
                logger.error(f"Failed to get events: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Exception getting events: {str(e)}")
            return []
