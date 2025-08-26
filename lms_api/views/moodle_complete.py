"""
Complete Moodle API Routes with all CRUD operations and file upload
"""

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPForbidden, HTTPUnauthorized, HTTPInternalServerError, HTTPServiceUnavailable, HTTPGatewayTimeout
import logging
import os
from ..auth import require_auth
from ..services.moodle_service import MoodleService, MoodleError, MoodleAuthError, MoodleValidationError, MoodleNotFoundError

log = logging.getLogger(__name__)

def normalize_moodle_response(success_data=None, error=None):
    if error:
        return {
            'ok': False,
            'error': {
                'code': getattr(error, 'error_code', 'unknown'),
                'message': str(error),
                'details': getattr(error, 'details', None)
            }
        }
    return {'ok': True, 'data': success_data}

def handle_moodle_error(error: Exception):
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
    try:
        return MoodleService()
    except ValueError as e:
        log.error(f"Moodle service configuration error: {str(e)}")
        raise HTTPInternalServerError("Moodle service not configured")

# Course CRUD Operations
@view_config(route_name='moodle_courses', request_method='GET', renderer='json')
def list_courses(request):
    try:
        moodle = get_moodle_service()
        courses = moodle.list_courses()
        
        search = request.params.get('search')
        if search:
            search_lower = search.lower()
            courses = [c for c in courses if search_lower in c.get('fullname', '').lower() or search_lower in c.get('shortname', '').lower()]
        
        category = request.params.get('category')
        if category:
            try:
                category_id = int(category)
                courses = [c for c in courses if c.get('categoryid') == category_id]
            except ValueError:
                raise HTTPBadRequest("Invalid category ID")
        
        return normalize_moodle_response(courses)
    except Exception as e:
        handle_moodle_error(e)

@view_config(route_name='moodle_courses', request_method='POST', renderer='json')
def create_course(request):
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    required_fields = ['fullname', 'shortname', 'categoryid']
    for field in required_fields:
        if field not in data or not data[field]:
            raise HTTPBadRequest(f'{field} is required')
    
    try:
        moodle = get_moodle_service()
        course = moodle.create_course(data)
        log.info(f"Course created: {course.get('id')}")
        return normalize_moodle_response(course)
    except Exception as e:
        handle_moodle_error(e)

@view_config(route_name='moodle_course', request_method='PATCH', renderer='json')
def update_course(request):
    course_id = request.matchdict['course_id']
    
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    if not data:
        raise HTTPBadRequest('No fields provided for update')
    
    try:
        course_id_int = int(course_id)
        update_data = {'id': course_id_int, **data}
        
        moodle = get_moodle_service()
        moodle.update_course(update_data)
        
        log.info(f"Course updated: {course_id}")
        return normalize_moodle_response({'message': 'Course updated successfully'})
    except Exception as e:
        handle_moodle_error(e)

@view_config(route_name='moodle_course_delete', request_method='DELETE', renderer='json')
def delete_course(request):
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
    except ValueError:
        raise HTTPBadRequest('Invalid course ID')
    
    try:
        moodle = get_moodle_service()
        moodle.delete_course(course_id_int)
        
        log.info(f"Course deleted: {course_id}")
        return normalize_moodle_response({'message': 'Course deleted successfully'})
    except Exception as e:
        handle_moodle_error(e)

# Content Operations
@view_config(route_name='moodle_course_contents', request_method='GET', renderer='json')
def get_course_contents(request):
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
    except ValueError:
        raise HTTPBadRequest('Invalid course ID')
    
    try:
        moodle = get_moodle_service()
        contents = moodle.get_course_contents(course_id_int)
        return normalize_moodle_response(contents)
    except Exception as e:
        handle_moodle_error(e)

@view_config(route_name='moodle_content_delete', request_method='DELETE', renderer='json')
def delete_content(request):
    module_id = request.matchdict['module_id']
    
    try:
        module_id_int = int(module_id)
    except ValueError:
        raise HTTPBadRequest('Invalid module ID')
    
    try:
        moodle = get_moodle_service()
        moodle.delete_course_module(module_id_int)
        
        log.info(f"Content deleted: {module_id}")
        return normalize_moodle_response({'message': 'Content deleted successfully'})
    except Exception as e:
        handle_moodle_error(e)

# File Upload Operations
@view_config(route_name='moodle_file_upload', request_method='POST', renderer='json')
def upload_file(request):
    if 'file' not in request.POST:
        raise HTTPBadRequest('No file uploaded')
    
    file_obj = request.POST['file']
    if not hasattr(file_obj, 'filename') or not file_obj.filename:
        raise HTTPBadRequest('Invalid file')
    
    # Validate file size
    file_obj.file.seek(0, 2)
    file_size = file_obj.file.tell()
    file_obj.file.seek(0)
    
    MAX_SIZE = 100 * 1024 * 1024  # 100MB
    if file_size > MAX_SIZE:
        raise HTTPBadRequest(f'File too large. Max 100MB, got {file_size/1024/1024:.1f}MB')
    
    try:
        file_data = file_obj.file.read()
        
        moodle = get_moodle_service()
        result = moodle.upload_file(
            file_data=file_data,
            filename=file_obj.filename,
            contextid=int(request.POST.get('contextid', 1)),
            component=request.POST.get('component', 'user'),
            filearea=request.POST.get('filearea', 'draft')
        )
        
        log.info(f"File uploaded: {file_obj.filename}")
        return normalize_moodle_response(result)
    except Exception as e:
        handle_moodle_error(e)

@view_config(route_name='moodle_file_upload_course', request_method='POST', renderer='json')
def upload_file_to_course(request):
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
    except ValueError:
        raise HTTPBadRequest('Invalid course ID')
    
    if 'file' not in request.POST:
        raise HTTPBadRequest('No file uploaded')
    
    file_obj = request.POST['file']
    if not hasattr(file_obj, 'filename') or not file_obj.filename:
        raise HTTPBadRequest('Invalid file')
    
    # Validate file size
    file_obj.file.seek(0, 2)
    file_size = file_obj.file.tell()
    file_obj.file.seek(0)
    
    MAX_SIZE = 100 * 1024 * 1024  # 100MB
    if file_size > MAX_SIZE:
        raise HTTPBadRequest(f'File too large. Max 100MB, got {file_size/1024/1024:.1f}MB')
    
    try:
        file_data = file_obj.file.read()
        
        moodle = get_moodle_service()
        
        # Upload to draft area first
        upload_result = moodle.upload_file(
            file_data=file_data,
            filename=file_obj.filename
        )
        
        # Attach to course if upload successful
        if 'draftitemid' in upload_result:
            attach_result = moodle.attach_file_to_course_resource(
                courseid=course_id_int,
                draftitemid=upload_result['draftitemid'],
                name=request.POST.get('name', file_obj.filename),
                intro=request.POST.get('intro', '')
            )
            
            log.info(f"File uploaded to course {course_id}: {file_obj.filename}")
            return normalize_moodle_response({
                'upload': upload_result,
                'attach': attach_result,
                'message': 'File uploaded successfully'
            })
        
        return normalize_moodle_response(upload_result)
    except Exception as e:
        handle_moodle_error(e)

# URL and Page Resources
@view_config(route_name='moodle_add_url', request_method='POST', renderer='json')
def add_url_resource(request):
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
        data = request.json_body
    except (ValueError, TypeError):
        raise HTTPBadRequest('Invalid course ID or JSON')
    
    if 'name' not in data or 'externalurl' not in data:
        raise HTTPBadRequest('name and externalurl are required')
    
    try:
        moodle = get_moodle_service()
        result = moodle.add_url_to_course(
            courseid=course_id_int,
            section=data.get('section', 0),
            name=data['name'],
            externalurl=data['externalurl'],
            intro=data.get('intro', '')
        )
        
        log.info(f"URL added to course {course_id}: {data['name']}")
        return normalize_moodle_response(result)
    except Exception as e:
        handle_moodle_error(e)

@view_config(route_name='moodle_add_page', request_method='POST', renderer='json')
def add_page_resource(request):
    course_id = request.matchdict['course_id']
    
    try:
        course_id_int = int(course_id)
        data = request.json_body
    except (ValueError, TypeError):
        raise HTTPBadRequest('Invalid course ID or JSON')
    
    if 'name' not in data or 'content' not in data:
        raise HTTPBadRequest('name and content are required')
    
    try:
        moodle = get_moodle_service()
        result = moodle.add_page_to_course(
            courseid=course_id_int,
            section=data.get('section', 0),
            name=data['name'],
            content=data['content'],
            intro=data.get('intro', '')
        )
        
        log.info(f"Page added to course {course_id}: {data['name']}")
        return normalize_moodle_response(result)
    except Exception as e:
        handle_moodle_error(e)

# Utility endpoints
@view_config(route_name='moodle_validate_file', request_method='POST', renderer='json')
def validate_file(request):
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    filename = data.get('filename', '')
    filesize = data.get('filesize', 0)
    
    if not filename:
        raise HTTPBadRequest('Filename is required')
    
    try:
        filesize = int(filesize)
    except (ValueError, TypeError):
        raise HTTPBadRequest('Invalid file size')
    
    try:
        moodle = get_moodle_service()
        validation_result = moodle.validate_file_upload(filesize, filename)
        return normalize_moodle_response(validation_result)
    except Exception as e:
        handle_moodle_error(e)

@view_config(route_name='moodle_categories', request_method='GET', renderer='json')
def get_categories(request):
    try:
        moodle = get_moodle_service()
        categories = moodle.get_course_categories()
        return normalize_moodle_response(categories)
    except Exception as e:
        handle_moodle_error(e)

@view_config(route_name='moodle_siteinfo', request_method='GET', renderer='json')
def get_site_info(request):
    try:
        moodle = get_moodle_service()
        site_info = moodle.get_site_info()
        
        filtered_info = {
            'sitename': site_info.get('sitename'),
            'release': site_info.get('release'),
            'version': site_info.get('version'),
            'functions': [{'name': f.get('name', ''), 'version': f.get('version', '')} for f in site_info.get('functions', [])]
        }
        
        return normalize_moodle_response(filtered_info)
    except Exception as e:
        handle_moodle_error(e)