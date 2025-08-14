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

log = logging.getLogger(__name__)


class MoodleError(Exception):
    """Base exception for Moodle API errors"""
    def __init__(self, message: str, error_code: str = None, status_code: int = None):
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
            log.info(f"[{request_id}] Moodle API request started", extra={
                'request_id': request_id,
                'wsfunction': wsfunction,
                'moodle_base_url': self.base_url.replace(self.token, '[REDACTED]') if self.token in self.base_url else self.base_url
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
        self.timeout = timeout or int(os.getenv('MOODLE_TIMEOUT_MS', '15000'))
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
        auth_errors = ['invalidtoken', 'accessexception', 'nopermissions', 'notloggedin']
        validation_errors = ['invalidparameter', 'missingparam', 'invalidrecord']
        not_found_errors = ['invaliduser', 'invalidcourse', 'coursenotexist']
        
        if error_code in auth_errors:
            if error_code == 'invalidtoken':
                return MoodleAuthError("Invalid Moodle token", error_code, 401)
            else:
                return MoodleAuthError(f"Access denied: {message}", error_code, 403)
        elif error_code in validation_errors:
            return MoodleValidationError(f"Validation error: {message}", error_code, 400)
        elif error_code in not_found_errors:
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
        idempotent_functions = [
            'core_webservice_get_site_info',
            'core_course_get_courses',
            'core_user_get_users_by_field',
            'message_popup_get_popup_notifications',
            'core_message_get_popup_notifications',
            'core_message_get_unread_popup_notifications_count'
        ]
        
        is_idempotent = wsfunction in idempotent_functions
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
        return self.call('core_course_update_courses', params)
    
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
        
        # Validate required fields
        for enrolment in enrolments:
            required_fields = ['roleid', 'userid', 'courseid']
            for field in required_fields:
                if field not in enrolment:
                    raise MoodleValidationError(f"Required field missing in enrolment: {field}")
        
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
            if 'function not found' in str(e).lower():
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
            if 'function not found' in str(e).lower():
                # Fall back to getting all notifications and counting
                notifications = self.get_popup_notifications(userid, limit=100)
                if isinstance(notifications, dict) and 'notifications' in notifications:
                    return len([n for n in notifications['notifications'] if not n.get('read', True)])
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
        upload_url = self.base_url.replace('/webservice/rest/server.php', '/webservice/upload.php')
        
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
        except Exception as e:
            raise MoodleError(f"File upload failed: {str(e)}")
    
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
            'assignments': [{
                'courseid': courseid,
                'name': name,
                'intro': intro,
                'introformat': 1,  # HTML format
                'files': draftitemid
            }]
        }
        
        return self.call('mod_resource_add_resource', params)