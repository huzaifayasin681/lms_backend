from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPForbidden
from sqlalchemy import or_, and_
from ..models import DBSession
from ..models.course import Course
from ..auth import require_auth
from ..services.lms_integration import LMSIntegrationService
import logging
import os

log = logging.getLogger(__name__)


# OPTIONS handler removed - now handled by global OPTIONS handler in __init__.py


@view_config(route_name='health', request_method='GET', renderer='json')
def health_check(request):
    """Health check endpoint"""
    return {'status': 'healthy', 'service': 'LMS API'}



@view_config(route_name='courses', request_method='GET', renderer='json')
@require_auth
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
@require_auth
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
        DBSession.add(course)
        DBSession.commit()
        
        log.info(f"Course created: {course.course_id} by user {request.user.username}")
        
        return course.to_dict()
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error creating course: {str(e)}")
        raise HTTPBadRequest(f'Error creating course: {str(e)}')


@view_config(route_name='course', request_method='GET', renderer='json')
@require_auth
def get_course(request):
    """Get a specific course"""
    course_id = request.matchdict['course_id']
    
    course = DBSession.query(Course).filter_by(course_id=course_id).first()
    if not course:
        raise HTTPNotFound('Course not found')
    
    return course.to_dict()


@view_config(route_name='course', request_method='PUT', renderer='json')
@require_auth
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
        updateable_fields = ['name', 'short_name', 'description', 'category', 'lms', 'active']
        for field in updateable_fields:
            if field in data:
                setattr(course, field, data[field])
        
        DBSession.commit()
        
        log.info(f"Course updated: {course.course_id} by user {request.user.username}")
        
        return course.to_dict()
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error updating course: {str(e)}")
        raise HTTPBadRequest(f'Error updating course: {str(e)}')


@view_config(route_name='course', request_method='DELETE', renderer='json')
@require_auth
def delete_course(request):
    """Delete a course"""
    course_id = request.matchdict['course_id']
    
    course = DBSession.query(Course).filter_by(course_id=course_id).first()
    if not course:
        raise HTTPNotFound('Course not found')
    
    try:
        DBSession.delete(course)
        DBSession.commit()
        
        log.info(f"Course deleted: {course_id} by user {request.user.username}")
        
        return {'message': 'Course deleted successfully'}
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error deleting course: {str(e)}")
        raise HTTPBadRequest(f'Error deleting course: {str(e)}')


@view_config(route_name='sync_courses', request_method='POST', renderer='json')
@require_auth
def sync_courses(request):
    """Sync courses from external LMS"""
    if not request.user.is_admin:
        raise HTTPForbidden('Admin access required')
    
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
        else:
            raise HTTPBadRequest('Unsupported LMS type')
        
        log.info(f"Course sync completed for {lms_type} by user {request.user.username}")
        
        return result
    except Exception as e:
        log.error(f"Error syncing courses from {lms_type}: {str(e)}")
        raise HTTPBadRequest(f'Error syncing courses: {str(e)}')