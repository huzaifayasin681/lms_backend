import requests
import os
import logging
from ..models import DBSession
from ..models.course import Course
from ..models.content import CourseContent

log = logging.getLogger(__name__)


class LMSIntegrationService:
    def __init__(self):
        self.moodle_url = os.getenv('MOODLE_URL', '')
        self.moodle_token = os.getenv('MOODLE_TOKEN', '')
        self.canvas_url = os.getenv('CANVAS_URL', '')
        self.canvas_token = os.getenv('CANVAS_TOKEN', '')
    
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