from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPForbidden, HTTPRequestEntityTooLarge
from pyramid.response import FileResponse
from sqlalchemy import or_, and_
from ..models import DBSession
from ..models.course import Course
from ..models.content import CourseContent
from ..auth import require_auth
from ..services.file_service import FileService
from ..services.lms_integration import LMSIntegrationService
import logging
import json
import os
import cgi
import tempfile

log = logging.getLogger(__name__)

# Initialize file service
file_service = FileService()



@view_config(route_name='course_content', request_method='GET', renderer='json')
@require_auth
def get_course_content(request):
    """Get all content for a course"""
    course_id = request.matchdict['course_id']
    
    # Check if course exists
    course = DBSession.query(Course).filter_by(course_id=course_id).first()
    if not course:
        raise HTTPNotFound('Course not found')
    
    query = DBSession.query(CourseContent).filter_by(course_id=course_id, active=True)
    
    # Optional filtering by content type
    content_type = request.params.get('type')
    if content_type:
        query = query.filter(CourseContent.content_type == content_type)
    
    # Sorting
    sort_by = request.params.get('sort', 'upload_date')
    if sort_by == 'title':
        query = query.order_by(CourseContent.title)
    elif sort_by == 'size':
        query = query.order_by(CourseContent.file_size.desc())
    else:  # default: upload_date
        query = query.order_by(CourseContent.upload_date.desc())
    
    content_items = query.all()
    
    # Filter out items with missing files (optional cleanup)
    valid_items = []
    for item in content_items:
        if item.content_type == 'file' and item.file_path:
            if not os.path.exists(item.file_path):
                log.warning(f"File missing for content ID {item.id}: {item.file_path}")
                # Optionally mark as inactive or continue showing
                valid_items.append(item)  # Show anyway, error will be handled on access
            else:
                valid_items.append(item)
        else:
            valid_items.append(item)
    
    return {
        'content': [item.to_dict() for item in valid_items],
        'total': len(valid_items),
        'course_id': course_id
    }


@view_config(route_name='upload_content', request_method='POST', renderer='json')
@require_auth
def upload_content(request):
    """Upload content to a course"""
    course_id = request.matchdict['course_id']
    
    # Check if course exists
    course = DBSession.query(Course).filter_by(course_id=course_id).first()
    if not course:
        raise HTTPNotFound('Course not found')
    
    try:
        # Handle different content types
        content_type = request.params.get('content_type', 'file')
        title = request.params.get('title', '')
        
        if content_type == 'file':
            return _handle_file_upload(request, course_id, title)
        elif content_type == 'url':
            return _handle_url_upload(request, course_id, title)
        elif content_type == 'text':
            return _handle_text_upload(request, course_id, title)
        else:
            raise HTTPBadRequest('Invalid content type')
            
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error uploading content: {str(e)}")
        raise HTTPBadRequest(f'Upload failed: {str(e)}')


def _handle_file_upload(request, course_id, title):
    """Handle file upload"""
    # Get uploaded file
    if 'file' not in request.POST:
        raise HTTPBadRequest('No file provided')
    
    file_field = request.POST['file']
    
    # Read file data
    if hasattr(file_field, 'file'):
        file_data = file_field.file.read()
        filename = getattr(file_field, 'filename', 'unknown')
    else:
        raise HTTPBadRequest('Invalid file format')
    
    # Validate file
    file_size = len(file_data)
    is_valid, error_msg = file_service.validate_file(filename, file_size)
    if not is_valid:
        raise HTTPBadRequest(error_msg)
    
    # Save file
    success, result, file_info = file_service.save_file(file_data, filename, course_id)
    if not success:
        raise HTTPBadRequest(result)
    
    # Create content record
    content_data = CourseContent.from_dict({
        'course_id': course_id,
        'title': title or filename,
        'content_type': 'file',
        'file_path': file_info['file_path'],
        'file_name': file_info['file_name'],
        'file_size': file_info['file_size'],
        'mime_type': file_info['mime_type']
    }, request.user.id)
    
    DBSession.add(content_data)
    DBSession.commit()
    
    log.info(f"File uploaded successfully: {filename} to course {course_id} by user {request.user.username}")
    
    return content_data.to_dict()


def _handle_url_upload(request, course_id, title):
    """Handle URL upload"""
    url = request.params.get('url', '').strip()
    description = request.params.get('description', '')
    
    # Validate URL
    is_valid, error_msg = file_service.validate_url(url)
    if not is_valid:
        raise HTTPBadRequest(error_msg)
    
    # Create content record
    content_data = CourseContent.from_dict({
        'course_id': course_id,
        'title': title or f'Link: {url[:50]}...' if len(url) > 50 else f'Link: {url}',
        'content_type': 'url',
        'content_data': {'url': url, 'description': description}
    }, request.user.id)
    
    DBSession.add(content_data)
    DBSession.commit()
    
    log.info(f"URL uploaded successfully: {url} to course {course_id} by user {request.user.username}")
    
    return content_data.to_dict()


def _handle_text_upload(request, course_id, title):
    """Handle text content upload"""
    text_content = request.params.get('text_content', '').strip()
    
    # Validate text content
    is_valid, error_msg = file_service.validate_text_content(text_content)
    if not is_valid:
        raise HTTPBadRequest(error_msg)
    
    # Create content record
    content_data = CourseContent.from_dict({
        'course_id': course_id,
        'title': title or f'Text: {text_content[:50]}...' if len(text_content) > 50 else 'Text Content',
        'content_type': 'text',
        'content_data': {'text': text_content}
    }, request.user.id)
    
    DBSession.add(content_data)
    DBSession.commit()
    
    log.info(f"Text content uploaded successfully to course {course_id} by user {request.user.username}")
    
    return content_data.to_dict()


@view_config(route_name='content_item', request_method='GET', renderer='json')
@require_auth
def get_content_item(request):
    """Get a specific content item"""
    content_id = request.matchdict['content_id']
    
    content = DBSession.query(CourseContent).filter_by(id=content_id, active=True).first()
    if not content:
        raise HTTPNotFound('Content not found')
    
    return content.to_dict()


@view_config(route_name='content_item', request_method='PUT', renderer='json')
@require_auth
def update_content_item(request):
    """Update a content item"""
    content_id = request.matchdict['content_id']
    
    content = DBSession.query(CourseContent).filter_by(id=content_id, active=True).first()
    if not content:
        raise HTTPNotFound('Content not found')
    
    # Check if user can edit (owner or admin)
    if content.uploaded_by != request.user.id and not request.user.is_admin:
        raise HTTPForbidden('You can only edit your own content')
    
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    try:
        # Update allowed fields
        if 'title' in data:
            content.title = data['title']
        
        if 'content_data' in data and content.content_type != 'file':
            # Only allow content_data updates for non-file content
            if content.content_type == 'url':
                url = data['content_data'].get('url')
                if url:
                    is_valid, error_msg = file_service.validate_url(url)
                    if not is_valid:
                        raise HTTPBadRequest(error_msg)
            elif content.content_type == 'text':
                text = data['content_data'].get('text')
                if text:
                    is_valid, error_msg = file_service.validate_text_content(text)
                    if not is_valid:
                        raise HTTPBadRequest(error_msg)
            
            content.content_data = json.dumps(data['content_data'])
        
        DBSession.commit()
        
        log.info(f"Content updated: {content_id} by user {request.user.username}")
        
        return content.to_dict()
        
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error updating content: {str(e)}")
        raise HTTPBadRequest(f'Update failed: {str(e)}')


@view_config(route_name='content_item', request_method='DELETE', renderer='json')
@require_auth
def delete_content_item(request):
    """Delete a content item"""
    content_id = request.matchdict['content_id']
    
    content = DBSession.query(CourseContent).filter_by(id=content_id, active=True).first()
    if not content:
        raise HTTPNotFound('Content not found')
    
    # Check if user can delete (owner or admin)
    if content.uploaded_by != request.user.id and not request.user.is_admin:
        raise HTTPForbidden('You can only delete your own content')
    
    try:
        # Delete file from disk if it exists
        if content.file_path and os.path.exists(content.file_path):
            file_service.delete_file(content.file_path)
        
        # Mark as inactive (soft delete)
        content.active = False
        DBSession.commit()
        
        log.info(f"Content deleted: {content_id} by user {request.user.username}")
        
        return {'message': 'Content deleted successfully'}
        
    except Exception as e:
        DBSession.rollback()
        log.error(f"Error deleting content: {str(e)}")
        raise HTTPBadRequest(f'Delete failed: {str(e)}')


@view_config(route_name='content_file', request_method='GET')
@require_auth  
def serve_content_file(request):
    """Serve a content file"""
    content_id = request.matchdict['content_id']
    
    content = DBSession.query(CourseContent).filter_by(id=content_id, active=True).first()
    if not content:
        raise HTTPNotFound('Content not found')
    
    if content.content_type != 'file' or not content.file_path:
        raise HTTPNotFound('File not found')
    
    # Ensure file path is absolute and exists
    file_path = content.file_path
    if not os.path.isabs(file_path):
        # If relative path, make it absolute from current working directory
        file_path = os.path.abspath(file_path)
    
    log.info(f"Content ID: {content_id}, File: {content.file_name}")
    log.info(f"Database file path: {content.file_path}")
    log.info(f"Resolved file path: {file_path}")
    
    if not os.path.exists(file_path):
        log.error(f"File not found on disk: {file_path}")
        log.error(f"Current working directory: {os.getcwd()}")
        
        # Check if directory exists
        file_dir = os.path.dirname(file_path)
        if os.path.exists(file_dir):
            log.error(f"Directory exists but file missing. Files in directory: {os.listdir(file_dir)}")
        else:
            log.error(f"Directory does not exist: {file_dir}")
            
        raise HTTPNotFound(f'File not found on disk: {os.path.basename(file_path)}')
    
    # Check if this is a download request
    download = request.params.get('download', '').lower() == 'true'
    
    try:
        # Determine content type - fix HTML files
        content_type = content.mime_type or 'application/octet-stream'
        
        # Special handling for HTML files
        if content.file_name and content.file_name.lower().endswith('.html'):
            content_type = 'text/html; charset=utf-8'
        
        # Return file response
        response = FileResponse(
            file_path,
            request=request,
            content_type=content_type
        )
        
        # Set appropriate headers based on request type
        if download:
            # Force download
            safe_filename = content.file_name.replace('"', '\\"') if content.file_name else 'download'
            response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        else:
            # Display inline
            if content.file_name:
                safe_filename = content.file_name.replace('"', '\\"')
                response.headers['Content-Disposition'] = f'inline; filename="{safe_filename}"'
        
        # Add content length
        file_size = os.path.getsize(file_path)
        response.headers['Content-Length'] = str(file_size)
        
        # Add security headers for HTML files
        if content_type.startswith('text/html'):
            # Allow iframe embedding from same origin
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        
        # Ensure proper CORS headers are set
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        
        log.info(f"File served successfully: {content.file_name} ({file_size} bytes) - Content-Type: {content_type}")
        return response
        
    except Exception as e:
        log.error(f"Error serving file {file_path}: {str(e)}")
        log.exception("Full exception details:")
        raise HTTPNotFound('Error serving file')