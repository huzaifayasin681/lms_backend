"""
Moodle REST API Service

Provides secure, typed access to Moodle web services with proper error handling,
retry logic, and parameter encoding for Moodle's bracketed key syntax.
"""

import requests
import time
import logging
import os
from urllib.parse import urlencode
from typing import Dict, Any, List, Optional, Union
from functools import wraps
import uuid
import re

log = logging.getLogger(__name__)


class MoodleError(Exception):
    """Base exception for Moodle API errors"""
    def __init__(self, message: str, error_code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class MoodleAuthError(MoodleError):
    """Authentication/authorization errors"""
    pass


class MoodleValidationError(MoodleError):
    """Validation/parameter errors"""
    pass


class MoodleNotFoundError(MoodleError):
    """Resource not found errors"""
    pass


def log_moodle_request(func):
    """Decorator to log Moodle API requests with structured logging"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        # Extract function name for logging
        wsfunction = args[0] if args else kwargs.get('wsfunction', 'unknown')
        
        if self.debug_mode:
            # Safely redact token from URL
            safe_url = re.sub(r'wstoken=[^&]*', 'wstoken=[REDACTED]', self.base_url)
            log.info(f"[{request_id}] Moodle API request started", extra={
                'request_id': request_id,
                'wsfunction': wsfunction,
                'moodle_base_url': safe_url
            })
        
        try:
            result = func(self, *args, **kwargs)
            duration = (time.time() - start_time) * 1000
            
            if self.debug_mode:
                log.info(f"[{request_id}] Moodle API request completed", extra={
                    'request_id': request_id,
                    'wsfunction': wsfunction,
                    'duration_ms': round(duration, 2),
                    'status': 'success'
                })
            
            return result
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            log.error(f"[{request_id}] Moodle API request failed", extra={
                'request_id': request_id,
                'wsfunction': wsfunction,
                'duration_ms': round(duration, 2),
                'status': 'error',
                'error': str(e)
            })
            raise
    
    return wrapper


class MoodleParamEncoder:
    """Utility class for encoding parameters in Moodle's bracketed key format"""
    
    @staticmethod
    def encode_params(data: Dict[str, Any]) -> Dict[str, str]:
        """
        Convert nested dictionaries and lists into Moodle's bracketed key format
        
        Examples:
        {'courses': [{'fullname': 'Test', 'shortname': 'TEST'}]}
        becomes:
        {'courses[0][fullname]': 'Test', 'courses[0][shortname]': 'TEST'}
        """
        result = {}
        
        def _encode_recursive(obj, prefix=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{prefix}[{key}]" if prefix else key
                    _encode_recursive(value, new_key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_key = f"{prefix}[{i}]"
                    _encode_recursive(item, new_key)
            else:
                # Handle boolean values for Moodle API
                if isinstance(obj, bool):
                    result[prefix] = '1' if obj else '0'
                else:
                    # Convert to string, handle None values
                    result[prefix] = str(obj) if obj is not None else ''
        
        _encode_recursive(data)
        return result
    
    @staticmethod
    def encode_array_param(values: List[Any], param_name: str) -> Dict[str, str]:
        """
        Encode array parameters for Moodle
        
        Example:
        encode_array_param(['email', 'username'], 'values')
        becomes:
        {'values[0]': 'email', 'values[1]': 'username'}
        """
        return {f"{param_name}[{i}]": str(value) for i, value in enumerate(values)}


class MoodleService:
    """
    Moodle REST API Service
    
    Provides secure access to Moodle web services with:
    - Automatic retry logic for idempotent operations
    - Proper error handling and normalization
    - Parameter encoding for Moodle's bracket syntax
    - Structured logging with request tracking
    - Token security (never logged or exposed)
    """
    
    def __init__(self, base_url: str = None, token: str = None, timeout: int = 15000):
        """
        Initialize Moodle service
        
        Args:
            base_url: Moodle base URL (defaults to MOODLE_BASE_URL env var)
            token: Moodle web service token (defaults to MOODLE_TOKEN env var)
            timeout: Request timeout in milliseconds (defaults to MOODLE_TIMEOUT_MS env var)
        """
        self.base_url = base_url or os.getenv('MOODLE_BASE_URL')
        self.token = token or os.getenv('MOODLE_TOKEN')
        try:
            self.timeout = timeout or int(os.getenv('MOODLE_TIMEOUT_MS', '15000'))
        except ValueError:
            self.timeout = 15000
        self.debug_mode = os.getenv('MOODLE_DEBUG', 'false').lower() == 'true'
        
        if not self.base_url:
            raise ValueError("Moodle base URL is required (set MOODLE_BASE_URL env var)")
        if not self.token:
            raise ValueError("Moodle token is required (set MOODLE_TOKEN env var)")
        
        # Ensure base URL ends with webservice endpoint
        if not self.base_url.endswith('/webservice/rest/server.php'):
            self.base_url = self.base_url.rstrip('/') + '/webservice/rest/server.php'
        
        # Convert timeout to seconds for requests library
        self.timeout_seconds = self.timeout / 1000.0
    
    def get_user_token(self, username: str, password: str, service: str = 'moodle_mobile_app') -> str:
        """
        Get Moodle web service token for a user
        This uses Moodle's token generation endpoint
        
        Args:
            username: Moodle username
            password: Moodle password
            service: Service name (defaults to moodle_mobile_app)
            
        Returns:
            Web service token
            
        Raises:
            MoodleAuthError: If authentication fails
            MoodleError: For other errors
        """
        # Construct token endpoint URL using relative path
        base_path = self.base_url.replace('/webservice/rest/server.php', '')
        token_url = f"{base_path}/login/token.php"
        
        params = {
            'username': username,
            'password': password,
            'service': service
        }
        
        try:
            response = requests.post(
                token_url,
                data=params,  # Use data instead of params for POST
                timeout=self.timeout_seconds,
                headers={
                    'User-Agent': 'LMS-Backend/1.0',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
            if 'token' in data:
                return data['token']
            elif 'error' in data:
                raise MoodleAuthError(f"Authentication failed: {data['error']}")
            else:
                raise MoodleError("Unexpected response from token endpoint")
                
        except requests.exceptions.RequestException as e:
            raise MoodleError(f"Failed to get token: {str(e)}")
    
    def _normalize_error(self, response_data: Dict[str, Any]) -> MoodleError:
        """
        Normalize Moodle error responses to standard HTTP error types
        
        Args:
            response_data: Moodle error response
            
        Returns:
            Appropriate MoodleError subclass
        """
        error_code = response_data.get('errorcode', 'unknown')
        message = response_data.get('message', 'Unknown Moodle error')
        
        # Map Moodle error codes to HTTP status codes and error types
        AUTH_ERRORS = ['invalidtoken', 'accessexception', 'nopermissions', 'notloggedin']
        VALIDATION_ERRORS = ['invalidparameter', 'missingparam', 'invalidrecord']
        NOT_FOUND_ERRORS = ['invaliduser', 'invalidcourse', 'coursenotexist']
        
        if error_code in AUTH_ERRORS:
            if error_code == 'invalidtoken':
                return MoodleAuthError("Invalid Moodle token", error_code, 401)
            else:
                return MoodleAuthError(f"Access denied: {message}", error_code, 403)
        elif error_code in VALIDATION_ERRORS:
            return MoodleValidationError(f"Validation error: {message}", error_code, 400)
        elif error_code in NOT_FOUND_ERRORS:
            return MoodleNotFoundError(f"Resource not found: {message}", error_code, 404)
        else:
            return MoodleError(f"Moodle error: {message}", error_code, 500)
    
    def _make_request_with_retry(self, wsfunction: str, params: Dict[str, Any], 
                                max_retries: int = 2) -> Any:
        """
        Make HTTP request with exponential backoff retry for idempotent operations
        
        Args:
            wsfunction: Moodle web service function name
            params: Parameters for the function
            max_retries: Maximum number of retries (only for GET-like operations)
            
        Returns:
            Moodle API response data
            
        Raises:
            MoodleError: For various error conditions
        """
        # Determine if operation is idempotent (safe to retry)
        IDEMPOTENT_FUNCTIONS = [
            'core_webservice_get_site_info',
            'core_course_get_courses',
            'core_user_get_users_by_field',
            'message_popup_get_popup_notifications',
            'core_message_get_popup_notifications',
            'core_message_get_unread_popup_notifications_count'
        ]
        
        is_idempotent = wsfunction in IDEMPOTENT_FUNCTIONS
        retries = max_retries if is_idempotent else 0
        
        # Prepare request data
        request_data = {
            'wstoken': self.token,
            'wsfunction': wsfunction,
            'moodlewsrestformat': 'json'
        }
        
        # Add function parameters with proper encoding
        if params:
            encoded_params = MoodleParamEncoder.encode_params(params)
            request_data.update(encoded_params)
        
        last_exception = None
        
        for attempt in range(retries + 1):
            try:
                # Log attempt (but never log the token)
                if self.debug_mode and attempt > 0:
                    log.info(f"Retrying Moodle request (attempt {attempt + 1})", extra={
                        'wsfunction': wsfunction,
                        'attempt': attempt + 1,
                        'max_retries': retries
                    })
                
                response = requests.post(
                    self.base_url,
                    data=request_data,
                    timeout=self.timeout_seconds,
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'User-Agent': 'LMS-Backend/1.0'
                    }
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse JSON response
                try:
                    data = response.json()
                except ValueError:
                    raise MoodleError(f"Invalid JSON response from Moodle", status_code=502)
                
                # Check for Moodle-specific errors
                if isinstance(data, dict) and 'exception' in data:
                    raise self._normalize_error(data)
                
                return data
                
            except requests.exceptions.Timeout:
                last_exception = MoodleError(f"Request timeout after {self.timeout_seconds}s", status_code=504)
            except requests.exceptions.ConnectionError:
                last_exception = MoodleError("Connection error to Moodle server", status_code=503)
            except requests.exceptions.HTTPError as e:
                last_exception = MoodleError(f"HTTP error: {e.response.status_code}", status_code=e.response.status_code)
            except MoodleError:
                # Don't retry Moodle-specific errors
                raise
            except Exception as e:
                last_exception = MoodleError(f"Unexpected error: {str(e)}", status_code=500)
            
            # Wait before retry with exponential backoff
            if attempt < retries:
                wait_time = (2 ** attempt) * 0.1  # 0.1s, 0.2s, 0.4s, etc.
                time.sleep(wait_time)
        
        # All retries failed
        raise last_exception
    
    @log_moodle_request
    def call(self, wsfunction: str, params: Dict[str, Any] = None) -> Any:
        """
        Generic method to call any Moodle web service function
        
        Args:
            wsfunction: Moodle web service function name
            params: Parameters for the function
            
        Returns:
            Moodle API response data
            
        Raises:
            MoodleError: For various error conditions
        """
        return self._make_request_with_retry(wsfunction, params or {})
    
    # Typed helper methods
    
    def get_site_info(self) -> Dict[str, Any]:
        """
        Get Moodle site information
        
        Returns:
            Site information including version, release, functions available
        """
        return self.call('core_webservice_get_site_info')
    
    def list_courses(self, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get list of courses visible to the user
        
        Args:
            options: Optional filters (not implemented in basic version)
            
        Returns:
            List of course objects
        """
        result = self.call('core_course_get_courses')
        return result if isinstance(result, list) else []
    
    def create_course(self, course_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new course
        
        Args:
            course_data: Course data with fullname, shortname, categoryid, etc.
            
        Returns:
            Created course data
            
        Required fields:
            - fullname: Full course name
            - shortname: Short course name  
            - categoryid: Category ID (usually 1 for default)
        """
        # Validate required fields
        required_fields = ['fullname', 'shortname', 'categoryid']
        for field in required_fields:
            if field not in course_data:
                raise MoodleValidationError(f"Required field missing: {field}")
        
        params = {'courses': [course_data]}
        result = self.call('core_course_create_courses', params)
        
        # Return first course from result
        return result[0] if isinstance(result, list) and result else result
    
    def update_course(self, course_update: Dict[str, Any]) -> None:
        """
        Update an existing course
        
        Args:
            course_update: Course data including id and fields to update
            
        Required fields:
            - id: Course ID to update
        """
        if 'id' not in course_update:
            raise MoodleValidationError("Course ID is required for update")
        
        params = {'courses': [course_update]}
        result = self.call('core_course_update_courses', params)
        return result
    
    def get_users_by_field(self, field: str, values: List[str]) -> List[Dict[str, Any]]:
        """
        Get users by field value(s)
        
        Args:
            field: Field to search by (username, email, id, etc.)
            values: List of values to search for
            
        Returns:
            List of user objects
        """
        if not values:
            return []
        
        params = {
            'field': field,
            'values': values
        }
        
        result = self.call('core_user_get_users_by_field', params)
        return result if isinstance(result, list) else []
    
    def enrol_users(self, enrolments: List[Dict[str, Any]]) -> None:
        """
        Manually enrol users in courses
        
        Args:
            enrolments: List of enrolment objects with roleid, userid, courseid
            
        Each enrolment should contain:
            - roleid: Role ID (5 = student, 3 = teacher, etc.)
            - userid: User ID
            - courseid: Course ID
        """
        if not enrolments:
            return
        
        # Validate required fields and values
        for i, enrolment in enumerate(enrolments):
            required_fields = ['roleid', 'userid', 'courseid']
            for field in required_fields:
                if field not in enrolment:
                    raise MoodleValidationError(f"Required field missing in enrolment {i}: {field}")
                # Validate that IDs are positive integers
                try:
                    value = int(enrolment[field])
                    if value <= 0:
                        raise MoodleValidationError(f"Invalid {field} in enrolment {i}: must be positive integer")
                except (ValueError, TypeError):
                    raise MoodleValidationError(f"Invalid {field} in enrolment {i}: must be integer")
        
        params = {'enrolments': enrolments}
        return self.call('enrol_manual_enrol_users', params)
    
    def get_popup_notifications(self, userid: int, limit: int = 20, 
                               offset: int = 0) -> Dict[str, Any]:
        """
        Get popup notifications for a user
        
        Args:
            userid: User ID
            limit: Maximum number of notifications (default 20)
            offset: Offset for pagination (default 0)
            
        Returns:
            Notifications data with list of notifications and unread count
        """
        # Try modern endpoint first, fall back to legacy
        params = {
            'useridto': userid,
            'limitfrom': offset,
            'limitnum': limit
        }
        
        try:
            return self.call('message_popup_get_popup_notifications', params)
        except MoodleError as e:
            if e.error_code == 'invalidfunction' or 'function not found' in str(e).lower():
                # Fall back to core_message functions
                params = {
                    'userid': userid,
                    'limitfrom': offset,
                    'limitnum': limit
                }
                return self.call('core_message_get_popup_notifications', params)
            raise
    
    def get_unread_popup_count(self, userid: int) -> int:
        """
        Get count of unread popup notifications for a user
        
        Args:
            userid: User ID
            
        Returns:
            Count of unread notifications
        """
        try:
            result = self.call('core_message_get_unread_popup_notifications_count', 
                             {'useridto': userid})
            return result if isinstance(result, int) else 0
        except MoodleError as e:
            if e.error_code == 'invalidfunction' or 'function not found' in str(e).lower():
                # Fall back to getting all notifications and counting
                notifications = self.get_popup_notifications(userid, limit=100)
                if isinstance(notifications, dict) and 'notifications' in notifications:
                    return len([n for n in notifications['notifications'] if not n.get('read', True)])
                return 0
            raise
    
    # File handling methods
    
    def upload_file(self, file_data: bytes, filename: str, contextid: int = 1, 
                   component: str = 'user', filearea: str = 'draft', 
                   itemid: int = 0) -> Dict[str, Any]:
        """
        Upload a file to Moodle's draft area
        
        Args:
            file_data: File content as bytes
            filename: Name of the file
            contextid: Context ID (default 1 for system context)
            component: Component name (default 'user')
            filearea: File area (default 'draft')
            itemid: Item ID (default 0 for new draft)
            
        Returns:
            Upload result with draftitemid for attaching to content
        """
        # This requires a different endpoint and multipart/form-data
        # Implementation depends on available Moodle file upload endpoints
        base_path = self.base_url.replace('/webservice/rest/server.php', '')
        upload_url = f"{base_path}/webservice/upload.php"
        
        files = {
            'file': (filename, file_data, 'application/octet-stream')
        }
        
        data = {
            'token': self.token,
            'component': component,
            'filearea': filearea,
            'itemid': itemid,
            'contextid': contextid
        }
        
        try:
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise MoodleError(f"File upload failed: {str(e)}")
        except ValueError as e:
            raise MoodleError(f"Invalid response from file upload: {str(e)}")
    
    def attach_file_to_course_resource(self, courseid: int, draftitemid: int, 
                                     name: str, intro: str = '') -> Dict[str, Any]:
        """
        Create a file resource in a course using uploaded draft file
        
        Args:
            courseid: Course ID
            draftitemid: Draft item ID from upload_file
            name: Resource name
            intro: Resource description
            
        Returns:
            Created resource data
        """
        params = {
            'resources': [{
                'courseid': courseid,
                'name': name,
                'intro': intro,
                'introformat': 1,  # HTML format
                'files': draftitemid
            }]
        }
        
        return self.call('mod_resource_add_resource', params)
    
    def delete_course(self, course_id: int) -> Dict[str, Any]:
        """
        Delete a course from Moodle
        
        Args:
            course_id: Course ID to delete
            
        Returns:
            Deletion result
        """
        params = {
            'courseids': [course_id]
        }
        
        return self.call('core_course_delete_courses', params)
    
    def get_course_contents(self, courseid: int) -> List[Dict[str, Any]]:
        """
        Get course contents/modules
        
        Args:
            courseid: Course ID
            
        Returns:
            List of course sections and modules
        """
        params = {
            'courseid': courseid
        }
        
        result = self.call('core_course_get_contents', params)
        return result if isinstance(result, list) else []
    
    def delete_course_module(self, cmid: int) -> Dict[str, Any]:
        """
        Delete a course module (content)
        
        Args:
            cmid: Course module ID
            
        Returns:
            Deletion result
        """
        params = {
            'cmid': cmid
        }
        
        return self.call('core_course_delete_module', params)
    
    def create_course_section(self, courseid: int, section_name: str) -> Dict[str, Any]:
        """
        Create a new section in a course
        
        Args:
            courseid: Course ID
            section_name: Name of the section
            
        Returns:
            Created section data
        """
        params = {
            'courseid': courseid,
            'section': {
                'name': section_name,
                'summary': '',
                'summaryformat': 1
            }
        }
        
        return self.call('core_course_create_section', params)
    
    def add_url_to_course(self, courseid: int, section: int, name: str, 
                         externalurl: str, intro: str = '') -> Dict[str, Any]:
        """
        Add a URL resource to a course
        
        Args:
            courseid: Course ID
            section: Section number (0-based)
            name: URL resource name
            externalurl: The URL
            intro: Description
            
        Returns:
            Created URL resource data
        """
        params = {
            'urls': [{
                'courseid': courseid,
                'name': name,
                'intro': intro,
                'introformat': 1,
                'externalurl': externalurl,
                'section': section
            }]
        }
        
        return self.call('mod_url_add_url', params)
    
    def add_page_to_course(self, courseid: int, section: int, name: str, 
                          content: str, intro: str = '') -> Dict[str, Any]:
        """
        Add a page resource to a course
        
        Args:
            courseid: Course ID
            section: Section number (0-based)
            name: Page name
            content: Page content (HTML)
            intro: Description
            
        Returns:
            Created page resource data
        """
        params = {
            'pages': [{
                'courseid': courseid,
                'name': name,
                'intro': intro,
                'introformat': 1,
                'content': content,
                'contentformat': 1,
                'section': section
            }]
        }
        
        return self.call('mod_page_add_page', params)
    
    def get_course_categories(self) -> List[Dict[str, Any]]:
        """
        Get all course categories
        
        Returns:
            List of category objects
        """
        result = self.call('core_course_get_categories')
        return result if isinstance(result, list) else []
    
    def search_courses(self, search_term: str, page: int = 0, perpage: int = 20) -> Dict[str, Any]:
        """
        Search courses by name or description
        
        Args:
            search_term: Search term
            page: Page number (0-based)
            perpage: Results per page
            
        Returns:
            Search results with courses and pagination info
        """
        params = {
            'criterianame': 'search',
            'criteriavalue': search_term,
            'page': page,
            'perpage': perpage
        }
        
        return self.call('core_course_search_courses', params)
    
    def get_enrolled_courses(self, userid: int) -> List[Dict[str, Any]]:
        """
        Get courses a user is enrolled in
        
        Args:
            userid: User ID
            
        Returns:
            List of enrolled courses
        """
        params = {
            'userid': userid
        }
        
        result = self.call('core_enrol_get_users_courses', params)
        return result if isinstance(result, list) else []
    
    def validate_file_upload(self, file_size: int, filename: str) -> Dict[str, Any]:
        """
        Validate file for upload (client-side validation)
        
        Args:
            file_size: File size in bytes
            filename: Original filename
            
        Returns:
            Validation result
        """
        MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
        
        if file_size > MAX_FILE_SIZE:
            return {
                'valid': False,
                'error': f'File size ({file_size / 1024 / 1024:.1f}MB) exceeds maximum allowed size (100MB)'
            }
        
        # Check file extension
        allowed_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
            '.txt', '.md', '.html', '.css', '.js', '.json', '.xml',
            '.py', '.java', '.c', '.cpp', '.h', '.cs', '.php',
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.mp3', '.wav', '.mp4', '.avi', '.mov', '.webm'
        }
        
        file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
        if file_ext not in allowed_extensions:
            return {
                'valid': False,
                'error': f'File type {file_ext} is not allowed'
            }
        
        return {'valid': True}
    
    def get_error_notifications(self, userid: int) -> List[Dict[str, Any]]:
        """
        Get error notifications for instructor dashboard
        
        Args:
            userid: User ID
            
        Returns:
            List of error notifications
        """
        try:
            # Get recent notifications that might contain errors
            notifications = self.get_popup_notifications(userid, limit=50)
            
            error_notifications = []
            if isinstance(notifications, dict) and 'notifications' in notifications:
                for notif in notifications['notifications']:
                    # Filter for error-related notifications
                    if any(keyword in notif.get('subject', '').lower() for keyword in 
                          ['error', 'failed', 'problem', 'issue', 'warning']):
                        error_notifications.append({
                            'id': notif.get('id'),
                            'subject': notif.get('subject', ''),
                            'text': notif.get('text', ''),
                            'timecreated': notif.get('timecreated'),
                            'read': notif.get('read', False)
                        })
            
            return error_notifications
            
        except Exception as e:
            log.warning(f"Failed to get error notifications: {str(e)}")
            return []