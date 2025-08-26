from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPForbidden
from sqlalchemy import or_, and_
from ..models import DBSession
from ..models.course import Course
from ..auth import require_auth
from ..services.lms_integration import LMSIntegrationService
from ..exceptions import ErrorHandler, handle_errors, DatabaseTransaction, ValidationError, ResourceNotFoundError, LMSIntegrationError
import logging
import os

log = logging.getLogger(__name__)


# OPTIONS handler removed - now handled by global OPTIONS handler in __init__.py



@view_config(route_name='courses', request_method='GET', renderer='json')
@handle_errors
def get_courses(request):
    """Get all courses with optional filtering"""
    query = DBSession.query(Course)
    
    # Search functionality
    search = request.params.get('search')
    if search:
        query = query.filter(
            or_(
                Course.name.ilike(f'%{search}%'),
                Course.short_name.ilike(f'%{search}%'),
                Course.description.ilike(f'%{search}%')
            )
        )
    
    # Category filter
    category = request.params.get('category')
    if category:
        query = query.filter(Course.category == category)
    
    # LMS filter
    lms = request.params.get('lms')
    if lms:
        query = query.filter(Course.lms == lms)
    
    # Active filter
    active = request.params.get('active')
    if active is not None:
        query = query.filter(Course.active == (active.lower() == 'true'))
    
    # Pagination
    page = int(request.params.get('page', 1))
    limit = int(request.params.get('limit', 20))
    offset = (page - 1) * limit
    
    total = query.count()
    courses = query.offset(offset).limit(limit).all()
    
    return {
        'courses': [course.to_dict() for course in courses],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit
        }
    }


@view_config(route_name='courses', request_method='POST', renderer='json')
def create_course(request):
    """Create a new course"""
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    # Validation
    required_fields = ['course_id', 'name', 'short_name']
    for field in required_fields:
        if not data.get(field):
            raise HTTPBadRequest(f'{field} is required')
    
    # Check if course_id already exists
    existing = DBSession.query(Course).filter_by(course_id=data['course_id']).first()
    if existing:
        raise HTTPBadRequest('Course ID already exists')
    
    try:
        course = Course.from_dict(data)
        
        # If course specifies an LMS, try to create it in the external system
        lms_type = data.get('lms', 'local')
        external_id = None
        
        if lms_type != 'local':
            try:
                integration_service = LMSIntegrationService()
                external_id = _create_course_in_external_lms(integration_service, lms_type, data)
                if external_id:
                    course.external_id = str(external_id)
                    log.info(f"Course created in external LMS ({lms_type}) with ID: {external_id}")
            except Exception as ext_error:
                log.warning(f"Failed to create course in external LMS ({lms_type}): {str(ext_error)}")
                # Continue with local creation even if external creation fails
        
        DBSession.add(course)
        DBSession.commit()
        
        log.info(f"Course created: {course.course_id}")
        
        return course.to_dict()
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error creating course: {str(e)}")
        raise HTTPBadRequest(f'Error creating course: {str(e)}')


@view_config(route_name='course', request_method='GET', renderer='json')
def get_course(request):
    """Get a specific course"""
    course_id = request.matchdict['course_id']
    
    course = DBSession.query(Course).filter_by(course_id=course_id).first()
    if not course:
        raise HTTPNotFound('Course not found')
    
    return course.to_dict()


@view_config(route_name='course', request_method='PUT', renderer='json')
def update_course(request):
    """Update a course"""
    course_id = request.matchdict['course_id']
    
    course = DBSession.query(Course).filter_by(course_id=course_id).first()
    if not course:
        raise HTTPNotFound('Course not found')
    
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    try:
        # Update fields
        updateable_fields = ['name', 'short_name', 'description', 'category', 'lms', 'active', 'visibility', 'access_level']
        for field in updateable_fields:
            if field in data:
                setattr(course, field, data[field])
        
        # Try to update in external LMS if it has an external_id
        if course.external_id:
            try:
                integration_service = LMSIntegrationService()
                _update_course_in_external_lms(integration_service, course, data)
                log.info(f"Course updated in external LMS ({course.lms}) with ID: {course.external_id}")
            except Exception as ext_error:
                log.warning(f"Failed to update course in external LMS ({course.lms}): {str(ext_error)}")
                # Continue with local update even if external update fails
        
        DBSession.commit()
        
        log.info(f"Course updated: {course.course_id}")
        
        return course.to_dict()
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error updating course: {str(e)}")
        raise HTTPBadRequest(f'Error updating course: {str(e)}')


@view_config(route_name='course', request_method='DELETE', renderer='json')
def delete_course(request):
    """Delete a course"""
    course_id = request.matchdict['course_id']
    
    course = DBSession.query(Course).filter_by(course_id=course_id).first()
    if not course:
        raise HTTPNotFound('Course not found')
    
    try:
        DBSession.delete(course)
        DBSession.commit()
        
        log.info(f"Course deleted: {course_id}")
        
        return {'message': 'Course deleted successfully'}
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error deleting course: {str(e)}")
        raise HTTPBadRequest(f'Error deleting course: {str(e)}')


@view_config(route_name='sync_courses', request_method='POST', renderer='json')
def sync_courses(request):
    """Sync courses from external LMS"""
    # Admin check removed - using configured token approach
    
    try:
        data = request.json_body or {}
    except ValueError:
        data = {}
    
    lms_type = data.get('lms_type', 'moodle')  # default to moodle
    
    try:
        integration_service = LMSIntegrationService()
        
        if lms_type == 'moodle':
            result = integration_service.sync_moodle_courses()
        elif lms_type == 'canvas':
            result = integration_service.sync_canvas_courses()
        elif lms_type == 'sakai':
            result = integration_service.sync_sakai_courses()
        elif lms_type == 'chamilo':
            result = integration_service.sync_chamilo_courses()
        else:
            raise HTTPBadRequest('Unsupported LMS type')
        
        log.info(f"Course sync completed for {lms_type}")
        
        return result
    except Exception as e:
        log.error(f"Error syncing courses from {lms_type}: {str(e)}")
        raise HTTPBadRequest(f'Error syncing courses: {str(e)}')


def _create_course_in_external_lms(integration_service, lms_type, course_data):
    """Helper function to create course in external LMS"""
    if lms_type == 'moodle':
        return integration_service.create_moodle_course(course_data)
    elif lms_type == 'canvas':
        return integration_service.create_canvas_course(course_data)
    elif lms_type == 'sakai':
        return integration_service.create_sakai_course(course_data)
    elif lms_type == 'chamilo':
        return integration_service.create_chamilo_course(course_data)
    else:
        raise Exception(f'Unsupported LMS type: {lms_type}')


def _update_course_in_external_lms(integration_service, course, course_data):
    """Helper function to update course in external LMS"""
    lms_type = course.lms
    if lms_type == 'local':
        return  # No external update needed
        
    if lms_type == 'moodle':
        return integration_service.update_moodle_course(course.external_id, course_data)
    elif lms_type == 'canvas':
        return integration_service.update_canvas_course(course.external_id, course_data)
    elif lms_type == 'sakai':
        return integration_service.update_sakai_course(course.external_id, course_data)
    elif lms_type == 'chamilo':
        return integration_service.update_chamilo_course(course.external_id, course_data)
    else:
        raise Exception(f'Unsupported LMS type: {lms_type}')


@view_config(route_name='sync_status', request_method='GET', renderer='json')
def get_sync_status(request):
    """Get sync service status"""
    from ..services.sync_service import get_sync_service
    
    # Admin check removed - using configured token approach
    
    sync_service = get_sync_service()
    return sync_service.get_sync_status()


@view_config(route_name='force_sync', request_method='POST', renderer='json')
def force_sync(request):
    """Force immediate sync for all LMS or specific LMS"""
    from ..services.sync_service import get_sync_service
    
    # Admin check removed - using configured token approach
    
    try:
        data = request.json_body if request.body else {}
        lms_type = data.get('lms_type')  # Optional, sync all if not specified
        
        sync_service = get_sync_service()
        result = sync_service.force_sync(lms_type)
        
        log.info(f"Force sync initiated for {lms_type or 'all LMS'}")
        
        return result
    except ValueError as e:
        raise HTTPBadRequest(str(e))
    except Exception as e:
        log.error(f"Error in force sync: {str(e)}")
        raise HTTPBadRequest(f'Sync failed: {str(e)}')


@view_config(route_name='sync_config', request_method='POST', renderer='json')
def update_sync_config(request):
    """Update sync service configuration"""
    from ..services.sync_service import get_sync_service
    
    # Admin check removed - using configured token approach
    
    try:
        data = request.json_body
        sync_interval = data.get('sync_interval')
        
        if sync_interval:
            sync_service = get_sync_service()
            sync_service.set_sync_interval(int(sync_interval))
            
        log.info(f"Sync configuration updated")
        
        return {"status": "success", "message": "Configuration updated"}
        
    except ValueError as e:
        raise HTTPBadRequest(str(e))
    except Exception as e:
        log.error(f"Error updating sync config: {str(e)}")
        raise HTTPBadRequest(f'Configuration update failed: {str(e)}')