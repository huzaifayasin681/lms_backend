import requests
import os
import logging
from ..models import DBSession
from ..models.course import Course
from ..models.content import CourseContent
from .retry_service import (
    get_retry_service, get_token_manager, get_http_client,
    TokenExpiredError, RateLimitError, ServiceUnavailableError
)

log = logging.getLogger(__name__)
retry_service = get_retry_service()
token_manager = get_token_manager()
http_client = get_http_client()


class LMSIntegrationService:
    def __init__(self):
        self.moodle_url = os.getenv('MOODLE_URL', '')
        self.moodle_token = os.getenv('MOODLE_TOKEN', '')
        self.canvas_url = os.getenv('CANVAS_URL', '')
        self.canvas_token = os.getenv('CANVAS_TOKEN', '')
        self.sakai_url = os.getenv('SAKAI_URL', '')
        self.sakai_username = os.getenv('SAKAI_USERNAME', '')
        self.sakai_password = os.getenv('SAKAI_PASSWORD', '')
        self.chamilo_url = os.getenv('CHAMILO_URL', '')
        self.chamilo_api_key = os.getenv('CHAMILO_API_KEY', '')
    
    @retry_service.with_retry(max_attempts=3, backoff_factor=2.0, 
                             exceptions=(requests.RequestException, ServiceUnavailableError))
    @retry_service.circuit_breaker(failure_threshold=5, recovery_timeout=300)
    def sync_moodle_courses(self):
        """Sync courses from Moodle via Web Services API"""
        if not self.moodle_url or not self.moodle_token:
            raise Exception('Moodle URL and token must be configured')
        
        try:
            # Moodle Web Services API call
            url = f"{self.moodle_url}/webservice/rest/server.php"
            params = {
                'wstoken': self.moodle_token,
                'wsfunction': 'core_course_get_courses',
                'moodlewsrestformat': 'json'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            moodle_courses = response.json()
            
            if 'exception' in moodle_courses:
                raise Exception(f"Moodle API error: {moodle_courses['message']}")
            
            synced_count = 0
            updated_count = 0
            
            for moodle_course in moodle_courses:
                course_data = {
                    'course_id': f"moodle_{moodle_course['id']}",
                    'name': moodle_course['fullname'],
                    'short_name': moodle_course['shortname'],
                    'description': moodle_course.get('summary', ''),
                    'category': moodle_course.get('categoryname', 'General'),
                    'lms': 'moodle',
                    'external_id': str(moodle_course['id'])
                }
                
                existing_course = DBSession.query(Course).filter_by(
                    course_id=course_data['course_id']
                ).first()
                
                if existing_course:
                    # Update existing course
                    for key, value in course_data.items():
                        if key != 'course_id':
                            setattr(existing_course, key, value)
                    updated_count += 1
                else:
                    # Create new course
                    course = Course.from_dict(course_data)
                    DBSession.add(course)
                    synced_count += 1
            
            DBSession.commit()
            
            return {
                'status': 'success',
                'synced': synced_count,
                'updated': updated_count,
                'total_processed': len(moodle_courses)
            }
        
        except requests.RequestException as e:
            log.error(f"Moodle API request error: {str(e)}")
            raise Exception(f"Failed to connect to Moodle: {str(e)}")
        except Exception as e:
            DBSession.rollback()
            log.error(f"Moodle sync error: {str(e)}")
            raise
    
    @retry_service.with_retry(max_attempts=3, backoff_factor=2.0,
                             exceptions=(requests.RequestException, ServiceUnavailableError, TokenExpiredError))
    @retry_service.circuit_breaker(failure_threshold=5, recovery_timeout=300)
    def sync_canvas_courses(self):
        """Sync courses from Canvas via REST API"""
        if not self.canvas_url or not self.canvas_token:
            raise Exception('Canvas URL and token must be configured')
        
        try:
            # Canvas API call
            url = f"{self.canvas_url}/api/v1/courses"
            headers = {
                'Authorization': f'Bearer {self.canvas_token}'
            }
            params = {
                'enrollment_type': 'teacher',
                'state': ['available', 'completed'],
                'per_page': 100
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            canvas_courses = response.json()
            
            synced_count = 0
            updated_count = 0
            
            for canvas_course in canvas_courses:
                course_data = {
                    'course_id': f"canvas_{canvas_course['id']}",
                    'name': canvas_course['name'],
                    'short_name': canvas_course['course_code'],
                    'description': canvas_course.get('public_description', ''),
                    'category': 'Canvas',
                    'lms': 'canvas',
                    'external_id': str(canvas_course['id'])
                }
                
                existing_course = DBSession.query(Course).filter_by(
                    course_id=course_data['course_id']
                ).first()
                
                if existing_course:
                    # Update existing course
                    for key, value in course_data.items():
                        if key != 'course_id':
                            setattr(existing_course, key, value)
                    updated_count += 1
                else:
                    # Create new course
                    course = Course.from_dict(course_data)
                    DBSession.add(course)
                    synced_count += 1
            
            DBSession.commit()
            
            return {
                'status': 'success',
                'synced': synced_count,
                'updated': updated_count,
                'total_processed': len(canvas_courses)
            }
        
        except requests.RequestException as e:
            log.error(f"Canvas API request error: {str(e)}")
            raise Exception(f"Failed to connect to Canvas: {str(e)}")
        except Exception as e:
            DBSession.rollback()
            log.error(f"Canvas sync error: {str(e)}")
            raise
    
    def test_moodle_connection(self):
        """Test Moodle API connection"""
        if not self.moodle_url or not self.moodle_token:
            return False, 'Moodle URL and token must be configured'
        
        try:
            url = f"{self.moodle_url}/webservice/rest/server.php"
            params = {
                'wstoken': self.moodle_token,
                'wsfunction': 'core_webservice_get_site_info',
                'moodlewsrestformat': 'json'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if 'exception' in result:
                return False, f"Moodle API error: {result['message']}"
            
            return True, f"Connected to {result.get('sitename', 'Moodle')}"
        
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def test_canvas_connection(self):
        """Test Canvas API connection"""
        if not self.canvas_url or not self.canvas_token:
            return False, 'Canvas URL and token must be configured'
        
        try:
            url = f"{self.canvas_url}/api/v1/users/self"
            headers = {
                'Authorization': f'Bearer {self.canvas_token}'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            return True, f"Connected as {result.get('name', 'Canvas User')}"
        
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    @retry_service.with_retry(max_attempts=3, backoff_factor=2.0,
                             exceptions=(requests.RequestException, ServiceUnavailableError))
    @retry_service.circuit_breaker(failure_threshold=5, recovery_timeout=300)
    def sync_sakai_courses(self):
        """Sync courses from Sakai via REST API"""
        if not self.sakai_url or not self.sakai_username or not self.sakai_password:
            raise Exception('Sakai URL, username, and password must be configured')
        
        try:
            # Sakai authentication and course retrieval
            session = requests.Session()
            
            # Authenticate with Sakai
            auth_url = f"{self.sakai_url}/direct/session.json"
            auth_data = {
                '_username': self.sakai_username,
                '_password': self.sakai_password
            }
            
            auth_response = session.post(auth_url, data=auth_data, timeout=30)
            auth_response.raise_for_status()
            
            # Get courses/sites
            sites_url = f"{self.sakai_url}/direct/site.json"
            params = {'_limit': 1000}
            
            response = session.get(sites_url, params=params, timeout=30)
            response.raise_for_status()
            
            sakai_data = response.json()
            sakai_sites = sakai_data.get('site_collection', [])
            
            synced_count = 0
            updated_count = 0
            
            for sakai_site in sakai_sites:
                # Filter for course sites (type 'course' or containing course indicators)
                if sakai_site.get('type') not in ['course', 'project']:
                    continue
                    
                course_data = {
                    'course_id': f"sakai_{sakai_site['id']}",
                    'name': sakai_site.get('title', ''),
                    'short_name': sakai_site.get('short_description', sakai_site.get('title', '')),
                    'description': sakai_site.get('description', ''),
                    'category': sakai_site.get('type', 'Sakai'),
                    'lms': 'sakai',
                    'external_id': str(sakai_site['id'])
                }
                
                existing_course = DBSession.query(Course).filter_by(
                    course_id=course_data['course_id']
                ).first()
                
                if existing_course:
                    # Update existing course
                    for key, value in course_data.items():
                        if key != 'course_id':
                            setattr(existing_course, key, value)
                    updated_count += 1
                else:
                    # Create new course
                    course = Course.from_dict(course_data)
                    DBSession.add(course)
                    synced_count += 1
            
            DBSession.commit()
            
            return {
                'status': 'success',
                'synced': synced_count,
                'updated': updated_count,
                'total_processed': len([s for s in sakai_sites if s.get('type') in ['course', 'project']])
            }
        
        except requests.RequestException as e:
            log.error(f"Sakai API request error: {str(e)}")
            raise Exception(f"Failed to connect to Sakai: {str(e)}")
        except Exception as e:
            DBSession.rollback()
            log.error(f"Sakai sync error: {str(e)}")
            raise
    
    def test_sakai_connection(self):
        """Test Sakai API connection"""
        if not self.sakai_url or not self.sakai_username or not self.sakai_password:
            return False, 'Sakai URL, username, and password must be configured'
        
        try:
            session = requests.Session()
            
            # Test authentication
            auth_url = f"{self.sakai_url}/direct/session.json"
            auth_data = {
                '_username': self.sakai_username,
                '_password': self.sakai_password
            }
            
            response = session.post(auth_url, data=auth_data, timeout=10)
            response.raise_for_status()
            
            session_data = response.json()
            if session_data.get('id'):
                return True, f"Connected to Sakai as {session_data.get('userId', 'User')}"
            else:
                return False, "Authentication failed"
        
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    @retry_service.with_retry(max_attempts=3, backoff_factor=2.0,
                             exceptions=(requests.RequestException, ServiceUnavailableError))
    @retry_service.circuit_breaker(failure_threshold=5, recovery_timeout=300)
    def sync_chamilo_courses(self):
        """Sync courses from Chamilo via REST API"""
        if not self.chamilo_url or not self.chamilo_api_key:
            raise Exception('Chamilo URL and API key must be configured')
        
        try:
            # Chamilo API endpoint for courses
            url = f"{self.chamilo_url}/main/webservices/api/v2.php"
            params = {
                'api_key': self.chamilo_api_key,
                'action': 'get_courses'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            chamilo_data = response.json()
            
            if not chamilo_data.get('success', False):
                raise Exception(f"Chamilo API error: {chamilo_data.get('message', 'Unknown error')}")
            
            chamilo_courses = chamilo_data.get('data', [])
            
            synced_count = 0
            updated_count = 0
            
            for chamilo_course in chamilo_courses:
                course_data = {
                    'course_id': f"chamilo_{chamilo_course['id']}",
                    'name': chamilo_course.get('title', ''),
                    'short_name': chamilo_course.get('code', ''),
                    'description': chamilo_course.get('course_description', ''),
                    'category': chamilo_course.get('category_name', 'Chamilo'),
                    'lms': 'chamilo',
                    'external_id': str(chamilo_course['id'])
                }
                
                existing_course = DBSession.query(Course).filter_by(
                    course_id=course_data['course_id']
                ).first()
                
                if existing_course:
                    # Update existing course
                    for key, value in course_data.items():
                        if key != 'course_id':
                            setattr(existing_course, key, value)
                    updated_count += 1
                else:
                    # Create new course
                    course = Course.from_dict(course_data)
                    DBSession.add(course)
                    synced_count += 1
            
            DBSession.commit()
            
            return {
                'status': 'success',
                'synced': synced_count,
                'updated': updated_count,
                'total_processed': len(chamilo_courses)
            }
        
        except requests.RequestException as e:
            log.error(f"Chamilo API request error: {str(e)}")
            raise Exception(f"Failed to connect to Chamilo: {str(e)}")
        except Exception as e:
            DBSession.rollback()
            log.error(f"Chamilo sync error: {str(e)}")
            raise
    
    def test_chamilo_connection(self):
        """Test Chamilo API connection"""
        if not self.chamilo_url or not self.chamilo_api_key:
            return False, 'Chamilo URL and API key must be configured'
        
        try:
            # Test API connection
            url = f"{self.chamilo_url}/main/webservices/api/v2.php"
            params = {
                'api_key': self.chamilo_api_key,
                'action': 'ping'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('success', False):
                return True, "Connected to Chamilo LMS"
            else:
                return False, f"API error: {result.get('message', 'Unknown error')}"
        
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def upload_to_moodle(self, course_content, file_path=None):
        """Upload content to Moodle course"""
        if not self.moodle_url or not self.moodle_token:
            raise Exception('Moodle URL and token must be configured')
        
        try:
            # Get the course external_id
            course = DBSession.query(Course).filter_by(course_id=course_content.course_id).first()
            if not course or not course.external_id:
                raise Exception('Course not found or missing external ID')
            
            moodle_course_id = course.external_id
            
            if course_content.content_type == 'file' and file_path:
                return self._upload_file_to_moodle(moodle_course_id, course_content, file_path)
            elif course_content.content_type == 'url':
                return self._add_url_to_moodle(moodle_course_id, course_content)
            elif course_content.content_type == 'text':
                return self._add_page_to_moodle(moodle_course_id, course_content)
            else:
                raise Exception(f'Unsupported content type: {course_content.content_type}')
                
        except Exception as e:
            log.error(f"Error uploading to Moodle: {str(e)}")
            raise
    
    def _upload_file_to_moodle(self, course_id, content, file_path):
        """Upload file to Moodle course"""
        # Step 1: Upload file to Moodle
        upload_url = f"{self.moodle_url}/webservice/upload.php"
        
        with open(file_path, 'rb') as file:
            files = {
                'file_1': (content.file_name, file, content.mime_type)
            }
            data = {
                'token': self.moodle_token,
                'filearea': 'draft',
                'itemid': 0
            }
            
            response = requests.post(upload_url, files=files, data=data, timeout=60)
            response.raise_for_status()
            
            upload_result = response.json()
            
            if 'error' in upload_result:
                raise Exception(f"Moodle file upload error: {upload_result['error']}")
        
        # Step 2: Create resource in course
        api_url = f"{self.moodle_url}/webservice/rest/server.php"
        params = {
            'wstoken': self.moodle_token,
            'wsfunction': 'mod_resource_add_resource',
            'moodlewsrestformat': 'json',
            'course': course_id,
            'name': content.title,
            'intro': f'Uploaded via LMS API',
            'introformat': 1,
            'files[0][filename]': content.file_name,
            'files[0][filepath]': '/',
            'files[0][filearea]': 'content',
            'files[0][itemid]': upload_result[0]['itemid']
        }
        
        response = requests.post(api_url, data=params, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if 'exception' in result:
            raise Exception(f"Moodle API error: {result['message']}")
        
        return result.get('id', None)
    
    def _add_url_to_moodle(self, course_id, content):
        """Add URL resource to Moodle course"""
        api_url = f"{self.moodle_url}/webservice/rest/server.php"
        
        content_data = content.content_data
        if isinstance(content_data, str):
            import json
            content_data = json.loads(content_data)
        
        params = {
            'wstoken': self.moodle_token,
            'wsfunction': 'mod_url_add_url',
            'moodlewsrestformat': 'json',
            'course': course_id,
            'name': content.title,
            'intro': content_data.get('description', ''),
            'introformat': 1,
            'externalurl': content_data.get('url', ''),
            'display': 0  # Automatic
        }
        
        response = requests.post(api_url, data=params, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if 'exception' in result:
            raise Exception(f"Moodle API error: {result['message']}")
        
        return result.get('id', None)
    
    def _add_page_to_moodle(self, course_id, content):
        """Add page resource to Moodle course"""
        api_url = f"{self.moodle_url}/webservice/rest/server.php"
        
        content_data = content.content_data
        if isinstance(content_data, str):
            import json
            content_data = json.loads(content_data)
        
        params = {
            'wstoken': self.moodle_token,
            'wsfunction': 'mod_page_add_page',
            'moodlewsrestformat': 'json',
            'course': course_id,
            'name': content.title,
            'intro': 'Text content uploaded via LMS API',
            'introformat': 1,
            'content': content_data.get('text', ''),
            'contentformat': 1
        }
        
        response = requests.post(api_url, data=params, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if 'exception' in result:
            raise Exception(f"Moodle API error: {result['message']}")
        
        return result.get('id', None)
    
    def upload_to_canvas(self, course_content, file_path=None):
        """Upload content to Canvas course"""
        if not self.canvas_url or not self.canvas_token:
            raise Exception('Canvas URL and token must be configured')
        
        try:
            # Get the course external_id
            course = DBSession.query(Course).filter_by(course_id=course_content.course_id).first()
            if not course or not course.external_id:
                raise Exception('Course not found or missing external ID')
            
            canvas_course_id = course.external_id
            
            if course_content.content_type == 'file' and file_path:
                return self._upload_file_to_canvas(canvas_course_id, course_content, file_path)
            elif course_content.content_type == 'url':
                return self._add_url_to_canvas(canvas_course_id, course_content)
            elif course_content.content_type == 'text':
                return self._add_page_to_canvas(canvas_course_id, course_content)
            else:
                raise Exception(f'Unsupported content type: {course_content.content_type}')
                
        except Exception as e:
            log.error(f"Error uploading to Canvas: {str(e)}")
            raise
    
    def _upload_file_to_canvas(self, course_id, content, file_path):
        """Upload file to Canvas course"""
        headers = {'Authorization': f'Bearer {self.canvas_token}'}
        
        # Step 1: Request file upload
        upload_url = f"{self.canvas_url}/api/v1/courses/{course_id}/files"
        data = {
            'name': content.file_name,
            'size': content.file_size,
            'content_type': content.mime_type,
            'parent_folder_path': '/course files'
        }
        
        response = requests.post(upload_url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        
        upload_info = response.json()
        
        # Step 2: Upload file
        with open(file_path, 'rb') as file:
            upload_response = requests.post(
                upload_info['upload_url'],
                files={'file': file},
                data=upload_info['upload_params'],
                timeout=60
            )
            upload_response.raise_for_status()
        
        # Step 3: Confirm upload
        confirm_response = requests.get(upload_info['upload_url'], headers=headers, timeout=30)
        confirm_response.raise_for_status()
        
        return confirm_response.json().get('id')
    
    def _add_url_to_canvas(self, course_id, content):
        """Add external URL to Canvas course"""
        headers = {
            'Authorization': f'Bearer {self.canvas_token}',
            'Content-Type': 'application/json'
        }
        
        content_data = content.content_data
        if isinstance(content_data, str):
            import json
            content_data = json.loads(content_data)
        
        url = f"{self.canvas_url}/api/v1/courses/{course_id}/external_tools"
        data = {
            'name': content.title,
            'url': content_data.get('url', ''),
            'description': content_data.get('description', ''),
            'privacy_level': 'public'
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        return response.json().get('id')
    
    def _add_page_to_canvas(self, course_id, content):
        """Add page to Canvas course"""
        headers = {
            'Authorization': f'Bearer {self.canvas_token}',
            'Content-Type': 'application/json'
        }
        
        content_data = content.content_data
        if isinstance(content_data, str):
            import json
            content_data = json.loads(content_data)
        
        url = f"{self.canvas_url}/api/v1/courses/{course_id}/pages"
        data = {
            'wiki_page': {
                'title': content.title,
                'body': content_data.get('text', ''),
                'published': True
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        return response.json().get('page_id')
    
    # Course creation methods for external LMS platforms
    
    def create_moodle_course(self, course_data):
        """Create a new course in Moodle"""
        if not self.moodle_url or not self.moodle_token:
            raise Exception('Moodle URL and token must be configured')
        
        try:
            url = f"{self.moodle_url}/webservice/rest/server.php"
            params = {
                'wstoken': self.moodle_token,
                'wsfunction': 'core_course_create_courses',
                'moodlewsrestformat': 'json',
                'courses[0][fullname]': course_data['name'],
                'courses[0][shortname]': course_data['short_name'],
                'courses[0][summary]': course_data.get('description', ''),
                'courses[0][categoryid]': 1,  # Default category
                'courses[0][visible]': 1 if course_data.get('visibility', 'private') == 'public' else 0
            }
            
            response = requests.post(url, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if 'exception' in result:
                raise Exception(f"Moodle API error: {result['message']}")
            
            return result[0]['id'] if result else None
        
        except Exception as e:
            log.error(f"Error creating Moodle course: {str(e)}")
            raise
    
    def create_canvas_course(self, course_data):
        """Create a new course in Canvas"""
        if not self.canvas_url or not self.canvas_token:
            raise Exception('Canvas URL and token must be configured')
        
        try:
            headers = {
                'Authorization': f'Bearer {self.canvas_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.canvas_url}/api/v1/accounts/1/courses"  # Default account
            data = {
                'course': {
                    'name': course_data['name'],
                    'course_code': course_data['short_name'],
                    'public_description': course_data.get('description', ''),
                    'is_public': course_data.get('visibility', 'private') == 'public'
                }
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('id')
        
        except Exception as e:
            log.error(f"Error creating Canvas course: {str(e)}")
            raise
    
    def create_sakai_course(self, course_data):
        """Create a new course/site in Sakai"""
        if not self.sakai_url or not self.sakai_username or not self.sakai_password:
            raise Exception('Sakai URL, username, and password must be configured')
        
        try:
            session = requests.Session()
            
            # Authenticate
            auth_url = f"{self.sakai_url}/direct/session.json"
            auth_data = {
                '_username': self.sakai_username,
                '_password': self.sakai_password
            }
            session.post(auth_url, data=auth_data, timeout=30)
            
            # Create site
            site_url = f"{self.sakai_url}/direct/site/new"
            site_data = {
                'title': course_data['name'],
                'short_description': course_data['short_name'],
                'description': course_data.get('description', ''),
                'type': 'course',
                'published': course_data.get('visibility', 'private') == 'public'
            }
            
            response = session.post(site_url, data=site_data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('id')
        
        except Exception as e:
            log.error(f"Error creating Sakai course: {str(e)}")
            raise
    
    def create_chamilo_course(self, course_data):
        """Create a new course in Chamilo"""
        if not self.chamilo_url or not self.chamilo_api_key:
            raise Exception('Chamilo URL and API key must be configured')
        
        try:
            url = f"{self.chamilo_url}/main/webservices/api/v2.php"
            params = {
                'api_key': self.chamilo_api_key,
                'action': 'create_course',
                'title': course_data['name'],
                'code': course_data['short_name'],
                'course_description': course_data.get('description', ''),
                'visibility': 1 if course_data.get('visibility', 'private') == 'public' else 0
            }
            
            response = requests.post(url, data=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if not result.get('success', False):
                raise Exception(f"Chamilo API error: {result.get('message', 'Unknown error')}")
            
            return result.get('data', {}).get('id')
        
        except Exception as e:
            log.error(f"Error creating Chamilo course: {str(e)}")
            raise
    
    # Course update methods for external LMS platforms
    
    def update_moodle_course(self, course_id, course_data):
        """Update an existing course in Moodle"""
        if not self.moodle_url or not self.moodle_token:
            raise Exception('Moodle URL and token must be configured')
        
        try:
            url = f"{self.moodle_url}/webservice/rest/server.php"
            params = {
                'wstoken': self.moodle_token,
                'wsfunction': 'core_course_update_courses',
                'moodlewsrestformat': 'json',
                'courses[0][id]': course_id,
                'courses[0][fullname]': course_data.get('name'),
                'courses[0][shortname]': course_data.get('short_name'),
                'courses[0][summary]': course_data.get('description', ''),
                'courses[0][visible]': 1 if course_data.get('visibility', 'private') == 'public' else 0
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
            
            response = requests.post(url, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if 'exception' in result:
                raise Exception(f"Moodle API error: {result['message']}")
            
            return True
        
        except Exception as e:
            log.error(f"Error updating Moodle course: {str(e)}")
            raise
    
    def update_canvas_course(self, course_id, course_data):
        """Update an existing course in Canvas"""
        if not self.canvas_url or not self.canvas_token:
            raise Exception('Canvas URL and token must be configured')
        
        try:
            headers = {
                'Authorization': f'Bearer {self.canvas_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.canvas_url}/api/v1/courses/{course_id}"
            data = {
                'course': {}
            }
            
            if course_data.get('name'):
                data['course']['name'] = course_data['name']
            if course_data.get('short_name'):
                data['course']['course_code'] = course_data['short_name']
            if course_data.get('description'):
                data['course']['public_description'] = course_data['description']
            if 'visibility' in course_data:
                data['course']['is_public'] = course_data['visibility'] == 'public'
            
            response = requests.put(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            return True
        
        except Exception as e:
            log.error(f"Error updating Canvas course: {str(e)}")
            raise
    
    def update_sakai_course(self, course_id, course_data):
        """Update an existing course/site in Sakai"""
        if not self.sakai_url or not self.sakai_username or not self.sakai_password:
            raise Exception('Sakai URL, username, and password must be configured')
        
        try:
            session = requests.Session()
            
            # Authenticate
            auth_url = f"{self.sakai_url}/direct/session.json"
            auth_data = {
                '_username': self.sakai_username,
                '_password': self.sakai_password
            }
            session.post(auth_url, data=auth_data, timeout=30)
            
            # Update site
            site_url = f"{self.sakai_url}/direct/site/{course_id}/edit"
            site_data = {}
            
            if course_data.get('name'):
                site_data['title'] = course_data['name']
            if course_data.get('short_name'):
                site_data['short_description'] = course_data['short_name']
            if course_data.get('description'):
                site_data['description'] = course_data['description']
            if 'visibility' in course_data:
                site_data['published'] = course_data['visibility'] == 'public'
            
            response = session.post(site_url, data=site_data, timeout=30)
            response.raise_for_status()
            
            return True
        
        except Exception as e:
            log.error(f"Error updating Sakai course: {str(e)}")
            raise
    
    def update_chamilo_course(self, course_id, course_data):
        """Update an existing course in Chamilo"""
        if not self.chamilo_url or not self.chamilo_api_key:
            raise Exception('Chamilo URL and API key must be configured')
        
        try:
            url = f"{self.chamilo_url}/main/webservices/api/v2.php"
            params = {
                'api_key': self.chamilo_api_key,
                'action': 'update_course',
                'course_id': course_id
            }
            
            if course_data.get('name'):
                params['title'] = course_data['name']
            if course_data.get('short_name'):
                params['code'] = course_data['short_name']
            if course_data.get('description'):
                params['course_description'] = course_data['description']
            if 'visibility' in course_data:
                params['visibility'] = 1 if course_data['visibility'] == 'public' else 0
            
            response = requests.post(url, data=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if not result.get('success', False):
                raise Exception(f"Chamilo API error: {result.get('message', 'Unknown error')}")
            
            return True
        
        except Exception as e:
            log.error(f"Error updating Chamilo course: {str(e)}")
            raise