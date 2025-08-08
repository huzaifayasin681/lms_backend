from pyramid.config import Configurator
from pyramid.renderers import render_to_response
from sqlalchemy import engine_from_config
from .models import DBSession, Base
from .models.course import Course
from .models.user import User
from .models.content import CourseContent
import os
from dotenv import load_dotenv

load_dotenv()


def add_cors_headers_response_callback(event):
    def cors_headers(request, response):
        response.headers.update({
            'Access-Control-Allow-Origin': os.getenv('CORS_ALLOW_ORIGIN', '*'),
            'Access-Control-Allow-Methods': os.getenv('CORS_ALLOW_METHODS', 'POST,GET,DELETE,PUT,OPTIONS'),
            'Access-Control-Allow-Headers': os.getenv('CORS_ALLOW_HEADERS', 'Origin, Content-Type, Accept, Authorization'),
            'Access-Control-Allow-Credentials': os.getenv('CORS_ALLOW_CREDENTIALS', 'false'),
            'Access-Control-Max-Age': os.getenv('CORS_MAX_AGE', '1728000'),
        })
    event.request.add_response_callback(cors_headers)


def options_view(request):
    """Handle OPTIONS preflight requests"""
    response = request.response
    response.headers.update({
        'Access-Control-Allow-Origin': os.getenv('CORS_ALLOW_ORIGIN', '*'),
        'Access-Control-Allow-Methods': os.getenv('CORS_ALLOW_METHODS', 'POST,GET,DELETE,PUT,OPTIONS'),
        'Access-Control-Allow-Headers': os.getenv('CORS_ALLOW_HEADERS', 'Origin, Content-Type, Accept, Authorization'),
        'Access-Control-Allow-Credentials': os.getenv('CORS_ALLOW_CREDENTIALS', 'false'),
        'Access-Control-Max-Age': os.getenv('CORS_MAX_AGE', '1728000'),
    })
    return response


def cors_middleware(app):
    """WSGI middleware to handle CORS for all requests"""
    def middleware(environ, start_response):
        # Debug: Print the request method and path
        method = environ.get('REQUEST_METHOD')
        path = environ.get('PATH_INFO', '')
        print(f"CORS Middleware: {method} {path}")
        
        # Check if this is an OPTIONS request
        if method == 'OPTIONS':
            print("CORS Middleware: Handling OPTIONS request")
            # Return a 200 response with CORS headers for all OPTIONS requests
            headers = [
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'POST,GET,DELETE,PUT,OPTIONS'),
                ('Access-Control-Allow-Headers', 'Origin, Content-Type, Accept, Authorization'),
                ('Access-Control-Allow-Credentials', 'false'),
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
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'POST,GET,DELETE,PUT,OPTIONS'),
                ('Access-Control-Allow-Headers', 'Origin, Content-Type, Accept, Authorization'),
                ('Access-Control-Allow-Credentials', 'false'),
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
    response.headers.update({
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST,GET,DELETE,PUT,OPTIONS',
        'Access-Control-Allow-Headers': 'Origin, Content-Type, Accept, Authorization',
        'Access-Control-Allow-Credentials': 'false',
        'Access-Control-Max-Age': '1728000',
    })
    return response


def main(global_config, **settings):
    """This function returns a Pyramid WSGI application."""
    config = Configurator(settings=settings)
    
    # Add a catch-all OPTIONS view
    config.add_notfound_view(global_options_view, request_method='OPTIONS')
    
    # Database setup
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    
    # Routes
    config.add_route('health', '/api/health')
    config.add_route('login', '/api/auth/login')
    config.add_route('register', '/api/auth/register')
    
    # Course routes
    config.add_route('courses', '/api/courses')
    config.add_route('course', '/api/courses/{course_id}')
    config.add_route('sync_courses', '/api/courses/sync')
    
    # Content routes
    config.add_route('course_content', '/api/courses/{course_id}/content')
    config.add_route('content_item', '/api/content/{content_id}')
    config.add_route('content_file', '/api/content/{content_id}/file')
    config.add_route('upload_content', '/api/courses/{course_id}/content/upload')
    
    # Static files
    config.add_static_view('static', 'static', cache_max_age=3600)
    
    # Scan for view configurations
    config.scan()
    
    # Create the WSGI app and wrap with CORS middleware
    app = config.make_wsgi_app()
    return cors_middleware(app)