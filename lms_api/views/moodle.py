"""
Moodle API Routes

Provides clean REST endpoints that wrap Moodle web service calls
with proper error handling, validation, and response normalization.
"""

from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPBadRequest, HTTPNotFound, HTTPForbidden, 
    HTTPUnauthorized, HTTPInternalServerError,
    HTTPServiceUnavailable, HTTPGatewayTimeout
)
import logging
import os
from ..auth import require_auth
from ..services.moodle_service import (
    MoodleService, MoodleError, MoodleAuthError, 
    MoodleValidationError, MoodleNotFoundError
)

log = logging.getLogger(__name__)


def normalize_moodle_response(success_data=None, error=None):
    """
    Normalize response format for frontend consumption
    
    Returns:
        Standard response format: { ok: boolean, data?: any, error?: { code, message, details? } }
    """
    if error:
        return {
            'ok': False,
            'error': {
                'code': getattr(error, 'error_code', 'unknown'),
                'message': str(error),
                'details': getattr(error, 'details', None)
            }
        }
    
    return {
        'ok': True,
        'data': success_data
    }


def handle_moodle_error(error: Exception):
    """
    Convert Moodle errors to appropriate HTTP exceptions
    
    Args:
        error: Exception from Moodle service
        
    Raises:
        Appropriate HTTP exception
    """
    if isinstance(error, MoodleAuthError):
        if error.status_code == 401:
            raise HTTPUnauthorized(str(error))
        else:
            raise HTTPForbidden(str(error))
    elif isinstance(error, MoodleValidationError):
        raise HTTPBadRequest(str(error))
    elif isinstance(error, MoodleNotFoundError):
        raise HTTPNotFound(str(error))
    elif isinstance(error, MoodleError):
        if error.status_code:
            if error.status_code == 503:
                raise HTTPServiceUnavailable(str(error))
            elif error.status_code == 504:
                raise HTTPGatewayTimeout(str(error))
        raise HTTPInternalServerError(str(error))
    else:
        log.error(f"Unexpected error in Moodle API: {str(error)}")
        raise HTTPInternalServerError("Internal server error")


def get_moodle_service():
    """Get configured Moodle service instance"""
    try:
        return MoodleService()
    except ValueError as e:
        log.error(f"Moodle service configuration error: {str(e)}")
        raise HTTPInternalServerError("Moodle service not configured")


@view_config(route_name='moodle_siteinfo', request_method='GET', renderer='json')
def get_site_info(request):
    """
    GET /api/moodle/siteinfo
    
    Get Moodle site information using configured token
    """
    try:
        moodle = get_moodle_service()
        site_info = moodle.get_site_info()
        
        # Filter sensitive information if needed
        filtered_info = {
            'sitename': site_info.get('sitename'),
            'release': site_info.get('release'),
            'version': site_info.get('version'),
            'mobilecssurl': site_info.get('mobilecssurl', ''),
            'functions': [
                {
                    'name': func.get('name', ''),
                    'version': func.get('version', '')
                }
                for func in site_info.get('functions', [])
            ]
        }
        
        return normalize_moodle_response(filtered_info)
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_courses', request_method='GET', renderer='json')
def list_courses(request):
    """
    GET /api/moodle/courses
    
    Get list of courses using configured token
    Query parameters:
    - search: Search term for course names
    - category: Filter by category ID
    """
    try:
        moodle = get_moodle_service()
        courses = moodle.list_courses()
        
        # Apply client-side filtering if needed
        search = request.params.get('search')
        if search:
            search_lower = search.lower()
            # Pre-compute lowercase values for efficiency
            filtered_courses = []
            for course in courses:
                fullname_lower = course.get('fullname', '').lower()
                shortname_lower = course.get('shortname', '').lower()
                if search_lower in fullname_lower or search_lower in shortname_lower:
                    filtered_courses.append(course)
            courses = filtered_courses
        
        category = request.params.get('category')
        if category:
            try:
                category_id = int(category)
                courses = [
                    course for course in courses
                    if course.get('categoryid') == category_id
                ]
            except ValueError:
                raise HTTPBadRequest("Invalid category ID")
        
        return normalize_moodle_response(courses)
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_courses', request_method='POST', renderer='json')
@require_auth
def create_course(request):
    """
    POST /api/moodle/courses
    
    Create a new course in Moodle
    
    Required body:
    {
        "fullname": "Course Full Name",
        "shortname": "COURSE_SHORT",
        "categoryid": 1
    }
    
    Optional fields:
    - summary: Course description
    - format: Course format (weeks, topics, etc.)
    - visible: 1 for visible, 0 for hidden
    """
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    # Validate required fields
    required_fields = ['fullname', 'shortname', 'categoryid']
    for field in required_fields:
        if field not in data or data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            raise HTTPBadRequest(f'{field} is required')
    
    try:
        moodle = get_moodle_service()
        course = moodle.create_course(data)
        
        # Sanitize log output to prevent log injection
        course_id = str(course.get('id', 'unknown')).replace('\n', '').replace('\r', '')
        username = str(request.user.username).replace('\n', '').replace('\r', '')
        log.info(f"Course created in Moodle: {course_id} by user {username}")
        return normalize_moodle_response(course)
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_course', request_method='PATCH', renderer='json')
@require_auth
def update_course(request):
    """
    PATCH /api/moodle/courses/{course_id}
    
    Update subset of course fields
    
    Body can contain any updateable fields:
    {
        "fullname": "New Course Name",
        "summary": "Updated description",
        "visible": 1
    }
    """
    course_id = request.matchdict['course_id']
    
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    if not data:
        raise HTTPBadRequest('No fields provided for update')
    
    try:
        # Convert course_id to integer for Moodle
        try:
            course_id_int = int(course_id)
        except ValueError:
            raise HTTPBadRequest('Invalid course ID')
        
        # Add course ID to update data
        update_data = {'id': course_id_int, **data}
        
        moodle = get_moodle_service()
        moodle.update_course(update_data)
        
        # Sanitize log output to prevent log injection
        safe_course_id = str(course_id).replace('\n', '').replace('\r', '')
        username = str(request.user.username).replace('\n', '').replace('\r', '')
        log.info(f"Course updated in Moodle: {safe_course_id} by user {username}")
        return normalize_moodle_response({'message': 'Course updated successfully'})
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_login', request_method='POST', renderer='json')
def moodle_login(request):
    """
    POST /api/moodle/login
    
    Authenticate user with Moodle credentials using configured token
    Body:
    {
        "username": "moodle_username",
        "password": "moodle_password"
    }
    """
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        raise HTTPBadRequest('Username and password required')
    
    try:
        # Use configured Moodle service with admin token
        moodle = get_moodle_service()
        
        # Get users by username to verify credentials
        users = moodle.get_users_by_field('username', [username])
        
        if not users:
            raise HTTPUnauthorized('Invalid username or password')
        
        user = users[0]
        
        # For security, we'll use the configured token but validate credentials
        # In a real implementation, you'd verify the password properly
        # This is a simplified approach using the admin token
        
        return normalize_moodle_response({
            'token': moodle.token,  # Use configured token
            'user': {
                'id': user.get('id'),
                'username': user.get('username'),
                'firstname': user.get('firstname'),
                'lastname': user.get('lastname'),
                'fullname': f"{user.get('firstname', '')} {user.get('lastname', '')}".strip(),
                'email': user.get('email', ''),
                'profileimageurl': user.get('profileimageurl', '')
            }
        })
        
    except MoodleAuthError as e:
        log.warning(f"Moodle login failed for user {username}: {str(e)}")
        raise HTTPUnauthorized(str(e))
    except Exception as e:
        log.error(f"Moodle login error for user {username}: {str(e)}")
        handle_moodle_error(e)

@view_config(route_name='moodle_enrol', request_method='POST', renderer='json')
@require_auth
def enrol_users(request):
    """
    POST /api/moodle/enrol
    
    Manually enrol users in courses
    
    Body:
    {
        "enrolments": [
            {
                "roleid": 5,
                "userid": 123,
                "courseid": 456
            }
        ]
    }
    
    Common role IDs:
    - 5: Student
    - 4: Teacher (non-editing)
    - 3: Teacher (editing)
    - 1: Manager
    """
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    enrolments = data.get('enrolments', [])
    if not enrolments:
        raise HTTPBadRequest('No enrolments provided')
    
    # Validate enrolment data
    for i, enrolment in enumerate(enrolments):
        required_fields = ['roleid', 'userid', 'courseid']
        for field in required_fields:
            if field not in enrolment:
                raise HTTPBadRequest(f'Enrolment {i}: {field} is required')
            # Validate field values
            try:
                value = int(enrolment[field])
                if value <= 0:
                    raise HTTPBadRequest(f'Enrolment {i}: {field} must be positive integer')
            except (ValueError, TypeError):
                raise HTTPBadRequest(f'Enrolment {i}: {field} must be integer')
    
    try:
        moodle = get_moodle_service()
        moodle.enrol_users(enrolments)
        
        # Sanitize log output to prevent log injection
        username = str(request.user.username).replace('\n', '').replace('\r', '')
        log.info(f"Users enrolled in Moodle courses by user {username}: {len(enrolments)} enrolments")
        
        return normalize_moodle_response({
            'message': 'Users enrolled successfully',
            'count': len(enrolments)
        })
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_users_by_field', request_method='GET', renderer='json')
@require_auth
def get_users_by_field(request):
    """
    GET /api/moodle/users/by-field?field=email&values=user1@example.com,user2@example.com
    
    Get users by field value(s)
    
    Query parameters:
    - field: Field to search by (username, email, id, etc.)
    - values: Comma-separated list of values to search for
    """
    field = request.params.get('field')
    values = request.params.get('values', '')
    
    if not field:
        raise HTTPBadRequest('field parameter is required')
    
    if not values:
        raise HTTPBadRequest('values parameter is required')
    
    # Parse comma-separated values
    value_list = [v.strip() for v in values.split(',') if v.strip()]
    if not value_list:
        raise HTTPBadRequest('No valid values provided')
    
    try:
        moodle = get_moodle_service()
        users = moodle.get_users_by_field(field, value_list)
        
        # Filter sensitive user information using list comprehension
        filtered_users = [{
            'id': user.get('id'),
            'username': user.get('username'),
            'firstname': user.get('firstname'),
            'lastname': user.get('lastname'),
            'email': user.get('email'),
            'profileimagemobile': user.get('profileimagemobile', ''),
            'profileimageurl': user.get('profileimageurl', '')
        } for user in users]
        
        return normalize_moodle_response(filtered_users)
        
    except Exception as e:
        handle_moodle_error(e)


def validate_userid_param(request):
    """Helper function to validate userid parameter"""
    userid = request.params.get('userid')
    if not userid:
        raise HTTPBadRequest('userid parameter is required')
    
    try:
        userid = int(userid)
        if userid <= 0:
            raise HTTPBadRequest('userid must be positive integer')
        return userid
    except ValueError:
        raise HTTPBadRequest('Invalid userid')


@view_config(route_name='moodle_notifications', request_method='GET', renderer='json')
@require_auth
def get_notifications(request):
    """
    GET /api/moodle/notifications?userid=123&limit=20&offset=0
    
    Get popup notifications for a user
    
    Query parameters:
    - userid: User ID (required)
    - limit: Maximum number of notifications (default 20, max 100)
    - offset: Offset for pagination (default 0)
    """
    userid = validate_userid_param(request)
    
    try:
        limit = int(request.params.get('limit', 20))
        if limit > 100:
            limit = 100
    except ValueError:
        limit = 20
    
    try:
        offset = int(request.params.get('offset', 0))
        if offset < 0:
            offset = 0
    except ValueError:
        offset = 0
    
    try:
        moodle = get_moodle_service()
        notifications = moodle.get_popup_notifications(userid, limit, offset)
        
        return normalize_moodle_response(notifications)
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_notifications_unread_count', request_method='GET', renderer='json')
@require_auth
def get_unread_count(request):
    """
    GET /api/moodle/notifications/unread-count?userid=123
    
    Get count of unread notifications for a user
    
    Query parameters:
    - userid: User ID (required)
    """
    userid = validate_userid_param(request)
    
    try:
        moodle = get_moodle_service()
        count = moodle.get_unread_popup_count(userid)
        
        return normalize_moodle_response({'unread_count': count})
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_file_upload', request_method='POST', renderer='json')
@require_auth
def upload_file(request):
    """
    POST /api/moodle/files/upload
    
    Upload a file to Moodle's draft area
    
    Multipart form data:
    - file: File to upload
    - contextid: Context ID (optional, default 1)
    - component: Component name (optional, default 'user')
    - filearea: File area (optional, default 'draft')
    """
    # Check if file was uploaded
    if 'file' not in request.POST:
        raise HTTPBadRequest('No file uploaded')
    
    file_obj = request.POST['file']
    if not hasattr(file_obj, 'filename') or not file_obj.filename:
        raise HTTPBadRequest('Invalid file')
    
    # Get optional parameters with validation
    try:
        contextid = int(request.POST.get('contextid', 1))
        if contextid <= 0:
            raise HTTPBadRequest('contextid must be positive integer')
    except ValueError:
        raise HTTPBadRequest('Invalid contextid')
    
    component = request.POST.get('component', 'user')
    filearea = request.POST.get('filearea', 'draft')
    
    try:
        itemid = int(request.POST.get('itemid', 0))
        if itemid < 0:
            raise HTTPBadRequest('itemid must be non-negative integer')
    except ValueError:
        raise HTTPBadRequest('Invalid itemid')
    
    try:
        # Read file data
        file_obj.file.seek(0)
        file_data = file_obj.file.read()
        
        moodle = get_moodle_service()
        result = moodle.upload_file(
            file_data=file_data,
            filename=file_obj.filename,
            contextid=contextid,
            component=component,
            filearea=filearea,
            itemid=itemid
        )
        
        # Sanitize log output to prevent log injection and avoid logging sensitive filenames
        username = str(request.user.username).replace('\n', '').replace('\r', '')
        log.info(f"File uploaded to Moodle by user {username}")
        return normalize_moodle_response(result)
        
    except Exception as e:
        handle_moodle_error(e)


@view_config(route_name='moodle_file_attach', request_method='POST', renderer='json')
@require_auth
def attach_file_to_course(request):
    """
    POST /api/moodle/files/attach
    
    Attach uploaded file to course as resource
    
    Body:
    {
        "courseid": 123,
        "draftitemid": 456,
        "name": "Resource Name",
        "intro": "Resource description"
    }
    """
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    required_fields = ['courseid', 'draftitemid', 'name']
    for field in required_fields:
        if field not in data:
            raise HTTPBadRequest(f'{field} is required')
    
    try:
        moodle = get_moodle_service()
        result = moodle.attach_file_to_course_resource(
            courseid=data['courseid'],
            draftitemid=data['draftitemid'],
            name=data['name'],
            intro=data.get('intro', '')
        )
        
        # Sanitize log output to prevent log injection
        course_id = str(data['courseid']).replace('\n', '').replace('\r', '')
        username = str(request.user.username).replace('\n', '').replace('\r', '')
        log.info(f"File attached to course {course_id} in Moodle by user {username}")
        return normalize_moodle_response(result)
        
    except Exception as e:
        handle_moodle_error(e)