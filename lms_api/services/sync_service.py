import asyncio
import logging
import time
from datetime import datetime, timedelta
from threading import Thread, Event
from ..models import DBSession
from ..models.course import Course
from .lms_integration import LMSIntegrationService

log = logging.getLogger(__name__)


class SyncService:
    def __init__(self, sync_interval=300):  # 5 minutes default
        self.sync_interval = sync_interval
        self.is_running = False
        self.stop_event = Event()
        self.sync_thread = None
        self.integration_service = LMSIntegrationService()
        self.last_sync = {}  # Track last sync time per LMS
        
    def start(self):
        """Start the background sync service"""
        if self.is_running:
            log.warning("Sync service is already running")
            return
            
        self.is_running = True
        self.stop_event.clear()
        self.sync_thread = Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        log.info("Background sync service started")
        
    def stop(self):
        """Stop the background sync service"""
        if not self.is_running:
            return
            
        self.is_running = False
        self.stop_event.set()
        if self.sync_thread:
            self.sync_thread.join(timeout=10)
        log.info("Background sync service stopped")
        
    def _sync_loop(self):
        """Main sync loop"""
        while not self.stop_event.is_set():
            try:
                self._perform_sync()
                # Wait for next sync interval or stop event
                self.stop_event.wait(timeout=self.sync_interval)
            except Exception as e:
                log.error(f"Error in sync loop: {str(e)}")
                # Wait a bit before retrying
                self.stop_event.wait(timeout=60)
                
    def _perform_sync(self):
        """Perform synchronization with all configured LMS platforms"""
        log.info("Starting scheduled course synchronization")
        
        # Check which LMS platforms are configured and sync them
        lms_platforms = self._get_configured_lms_platforms()
        
        for lms_type in lms_platforms:
            try:
                log.info(f"Syncing courses from {lms_type}")
                
                if lms_type == 'moodle':
                    result = self.integration_service.sync_moodle_courses()
                elif lms_type == 'canvas':
                    result = self.integration_service.sync_canvas_courses()
                elif lms_type == 'sakai':
                    result = self.integration_service.sync_sakai_courses()
                elif lms_type == 'chamilo':
                    result = self.integration_service.sync_chamilo_courses()
                else:
                    continue
                    
                self.last_sync[lms_type] = datetime.now()
                log.info(f"Successfully synced {lms_type}: {result}")
                
            except Exception as e:
                log.error(f"Failed to sync {lms_type}: {str(e)}")
                
    def _get_configured_lms_platforms(self):
        """Get list of configured LMS platforms"""
        platforms = []
        
        # Check Moodle configuration
        if (hasattr(self.integration_service, 'moodle_url') and 
            self.integration_service.moodle_url and 
            self.integration_service.moodle_token):
            platforms.append('moodle')
            
        # Check Canvas configuration
        if (hasattr(self.integration_service, 'canvas_url') and 
            self.integration_service.canvas_url and 
            self.integration_service.canvas_token):
            platforms.append('canvas')
            
        # Check Sakai configuration
        if (hasattr(self.integration_service, 'sakai_url') and 
            self.integration_service.sakai_url and 
            self.integration_service.sakai_username and
            self.integration_service.sakai_password):
            platforms.append('sakai')
            
        # Check Chamilo configuration
        if (hasattr(self.integration_service, 'chamilo_url') and 
            self.integration_service.chamilo_url and 
            self.integration_service.chamilo_api_key):
            platforms.append('chamilo')
            
        return platforms
        
    def force_sync(self, lms_type=None):
        """Force an immediate sync for specific LMS or all LMS"""
        try:
            if lms_type:
                # Sync specific LMS
                if lms_type == 'moodle':
                    result = self.integration_service.sync_moodle_courses()
                elif lms_type == 'canvas':
                    result = self.integration_service.sync_canvas_courses()
                elif lms_type == 'sakai':
                    result = self.integration_service.sync_sakai_courses()
                elif lms_type == 'chamilo':
                    result = self.integration_service.sync_chamilo_courses()
                else:
                    raise ValueError(f'Unsupported LMS type: {lms_type}')
                    
                self.last_sync[lms_type] = datetime.now()
                log.info(f"Force sync completed for {lms_type}: {result}")
                return result
            else:
                # Sync all configured LMS
                self._perform_sync()
                log.info("Force sync completed for all configured LMS platforms")
                return {"status": "success", "message": "All platforms synced"}
                
        except Exception as e:
            log.error(f"Force sync failed: {str(e)}")
            raise
            
    def get_sync_status(self):
        """Get current sync service status"""
        return {
            'is_running': self.is_running,
            'sync_interval': self.sync_interval,
            'last_sync': {
                lms: last_time.isoformat() if last_time else None
                for lms, last_time in self.last_sync.items()
            },
            'configured_lms': self._get_configured_lms_platforms()
        }
        
    def set_sync_interval(self, interval_seconds):
        """Update sync interval"""
        if interval_seconds < 60:  # Minimum 1 minute
            raise ValueError("Sync interval must be at least 60 seconds")
        self.sync_interval = interval_seconds
        log.info(f"Sync interval updated to {interval_seconds} seconds")


# Global sync service instance
sync_service = SyncService()


def start_sync_service(sync_interval=300):
    """Start the global sync service"""
    sync_service.sync_interval = sync_interval
    sync_service.start()


def stop_sync_service():
    """Stop the global sync service"""
    sync_service.stop()


def get_sync_service():
    """Get the global sync service instance"""
    return sync_service