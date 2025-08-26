from pyramid.config import Configurator
from pyramid.renderers import render_to_response
from sqlalchemy import engine_from_config
from .models import DBSession, Base
from .models.course import Course
from .models.user import User
from .models.content import CourseContent
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Debug: Print environment variables
print(f"DEBUG: Python path: {sys.path}")
print(f"DEBUG: Current working directory: {os.getcwd()}")
print(f"DEBUG: CORS_ALLOW_ORIGIN from env: {os.getenv('CORS_ALLOW_ORIGIN', 'NOT_SET')}")
print(f"DEBUG: All CORS env vars:")
for key in os.environ:
    if 'CORS' in key:
        print(f"  {key}={os.environ[key]}")


def add_cors_headers_response_callback(event):
    def cors_headers(request, response):
        allowed_origins = os.getenv('CORS_ALLOW_ORIGIN', 'http://localhost:1234').split(',')
        request_origin = request.headers.get('Origin', '')
        cors_origin = request_origin if request_origin in allowed_origins else allowed_origins[0]
        
        print(f"DEBUG: CORS Origin from env: {cors_origin}")
        print(f"DEBUG: Request Origin: {request_origin}")
        print(f"DEBUG: Using CORS Origin: {cors_origin}")
        
        response.headers.update({
            'Access-Control-Allow-Origin': cors_origin,
            'Access-Control-Allow-Methods': os.getenv('CORS_ALLOW_METHODS', 'POST,GET,DELETE,PUT,OPTIONS'),
            'Access-Control-Allow-Headers': os.getenv('CORS_ALLOW_HEADERS', 'Origin, Content-Type, Accept, Authorization'),
            'Access-Control-Allow-Credentials': os.getenv('CORS_ALLOW_CREDENTIALS', 'true'),
            'Access-Control-Max-Age': os.getenv('CORS_MAX_AGE', '1728000'),
        })
    event.request.add_response_callback(cors_headers)


def options_view(request):
    """Handle OPTIONS preflight requests"""
    response = request.response
    allowed_origins = os.getenv('CORS_ALLOW_ORIGIN', 'http://localhost:1234').split(',')
    request_origin = request.headers.get('Origin', '')
    cors_origin = request_origin if request_origin in allowed_origins else allowed_origins[0]
    
    print(f"DEBUG: OPTIONS view - CORS Origin from env: {cors_origin}")
    print(f"DEBUG: OPTIONS view - Request Origin: {request_origin}")
    print(f"DEBUG: OPTIONS view - Using CORS Origin: {cors_origin}")
    
    response.headers.update({
        'Access-Control-Allow-Origin': cors_origin,
        'Access-Control-Allow-Methods': os.getenv('CORS_ALLOW_METHODS', 'POST,GET,DELETE,PUT,OPTIONS'),
        'Access-Control-Allow-Headers': os.getenv('CORS_ALLOW_HEADERS', 'Origin, Content-Type, Accept, Authorization'),
        'Access-Control-Allow-Credentials': os.getenv('CORS_ALLOW_CREDENTIALS', 'true'),
        'Access-Control-Max-Age': os.getenv('CORS_MAX_AGE', '1728000'),
    })
    return response


def cors_middleware(app):
    """WSGI middleware to handle CORS for all requests"""
    def middleware(environ, start_response):
        # Debug: Print the request method and path
        method = environ.get('REQUEST_METHOD')
        path = environ.get('PATH_INFO', '')
        origin = environ.get('HTTP_ORIGIN', 'No Origin')
        
        # Handle multiple CORS origins
        allowed_origins = os.getenv('CORS_ALLOW_ORIGIN', 'http://localhost:1234').split(',')
        cors_origin = origin if origin in allowed_origins else allowed_origins[0]
        
        print(f"CORS Middleware: {method} {path}")
        print(f"CORS Middleware: Request Origin: {origin}")
        print(f"CORS Middleware: Allowed Origins: {allowed_origins}")
        print(f"CORS Middleware: Using CORS Origin: {cors_origin}")
        
        # Check if this is an OPTIONS request
        if method == 'OPTIONS':
            print("CORS Middleware: Handling OPTIONS request")
            # Return a 200 response with CORS headers for all OPTIONS requests
            headers = [
                ('Access-Control-Allow-Origin', cors_origin),
                ('Access-Control-Allow-Methods', 'POST,GET,DELETE,PUT,OPTIONS'),
                ('Access-Control-Allow-Headers', 'Origin, Content-Type, Accept, Authorization'),
                ('Access-Control-Allow-Credentials', 'true'),
                ('Access-Control-Max-Age', '1728000'),
                ('Content-Type', 'text/plain'),
                ('Content-Length', '0'),
            ]
            start_response('200 OK', headers)
            return [b'']
        
        # For non-OPTIONS requests, add CORS headers to response
        def new_start_response(status, response_headers, exc_info=None):
            print(f"CORS Middleware: Adding CORS headers to {method} {path} response")
            # Add CORS headers to all responses
            cors_headers = [
                ('Access-Control-Allow-Origin', cors_origin),
                ('Access-Control-Allow-Methods', 'POST,GET,DELETE,PUT,OPTIONS'),
                ('Access-Control-Allow-Headers', 'Origin, Content-Type, Accept, Authorization'),
                ('Access-Control-Allow-Credentials', 'true'),
                ('Access-Control-Max-Age', '1728000'),
            ]
            # Combine existing headers with CORS headers
            all_headers = response_headers + cors_headers
            return start_response(status, all_headers, exc_info)
        
        # Pass through to the main app with modified start_response
        return app(environ, new_start_response)
    
    return middleware


def global_options_view(request):
    """Global OPTIONS handler for all API endpoints"""
    response = request.response
    response.status = 200
    allowed_origins = os.getenv('CORS_ALLOW_ORIGIN', 'http://localhost:1234').split(',')
    request_origin = request.headers.get('Origin', '')
    cors_origin = request_origin if request_origin in allowed_origins else allowed_origins[0]
    
    print(f"DEBUG: Global OPTIONS view - CORS Origin from env: {cors_origin}")
    print(f"DEBUG: Global OPTIONS view - Request Origin: {request_origin}")
    print(f"DEBUG: Global OPTIONS view - Using CORS Origin: {cors_origin}")
    
    response.headers.update({
        'Access-Control-Allow-Origin': cors_origin,
        'Access-Control-Allow-Methods': 'POST,GET,DELETE,PUT,OPTIONS',
        'Access-Control-Allow-Headers': 'Origin, Content-Type, Accept, Authorization',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Max-Age': '1728000',
    })
    return response


def main(global_config, **settings):
    """This function returns a Pyramid WSGI application."""
    config = Configurator(settings=settings)
    
    # Add a catch-all OPTIONS view
    config.add_notfound_view(global_options_view, request_method='OPTIONS')
    
    # Add route for OPTIONS on all auth routes
    config.add_view(global_options_view, route_name='login', request_method='OPTIONS', renderer='json')
    config.add_view(global_options_view, route_name='register', request_method='OPTIONS', renderer='json')
    
    # Add global error handling
    from .exceptions import ErrorHandler
    
    def error_view(request):
        """Global error handler for unhandled exceptions"""
        exc = getattr(request, 'exception', None)
        if exc:
            return ErrorHandler.create_error_response(request, exc)
        return {'error': True, 'message': 'An unexpected error occurred'}
    
    # Add error views for different HTTP status codes
    config.add_view(error_view, context=Exception, renderer='json')
    config.add_notfound_view(error_view, renderer='json')
    config.add_forbidden_view(error_view, renderer='json')
    
    # Database setup
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    
    # Routes (no /api prefix since app is mounted under /api)
    config.add_route('health', '/health')
    config.add_route('login', '/auth/login')
    config.add_route('register', '/auth/register')
    
    # Debug: Print registered routes
    print("DEBUG: Registered routes:")
    print(f"  health: /health")
    print(f"  login: /auth/login")
    print(f"  register: /auth/register")
    
    # Course routes
    config.add_route('courses', '/courses')
    config.add_route('course', '/courses/{course_id}')
    config.add_route('sync_courses', '/courses/sync')
    config.add_route('sync_status', '/sync/status')
    config.add_route('force_sync', '/sync/force')
    config.add_route('sync_config', '/sync/config')
    
    # Content routes
    config.add_route('course_content', '/courses/{course_id}/content')
    config.add_route('content_item', '/content/{content_id}')
    config.add_route('content_file', '/content/{content_id}/file')
    config.add_route('upload_content', '/courses/{course_id}/content/upload')
    config.add_route('search_content', '/content/search')
    
    # Moodle API routes
    config.add_route('moodle_siteinfo', '/moodle/siteinfo')
    config.add_route('moodle_courses', '/moodle/courses')
    config.add_route('moodle_course', '/moodle/courses/{course_id}')
    config.add_route('moodle_enrol', '/moodle/enrol')
    config.add_route('moodle_users_by_field', '/moodle/users/by-field')
    config.add_route('moodle_notifications', '/moodle/notifications')
    config.add_route('moodle_notifications_unread_count', '/moodle/notifications/unread-count')
    config.add_route('moodle_file_upload', '/moodle/files/upload')
    config.add_route('moodle_file_attach', '/moodle/files/attach')
    config.add_route('moodle_login', '/moodle/login')
    
    # Static files
    config.add_static_view('static', 'static', cache_max_age=3600)
    
    # Scan for view configurations
    config.scan('.views')
    
    # Create the WSGI app and wrap with CORS middleware
    app = config.make_wsgi_app()
    return cors_middleware(app)