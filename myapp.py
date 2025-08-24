from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import os
import sys
import logging
from waitress import serve
from pyramid.paster import get_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the backend directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Debug: Print environment variables
print(f"DEBUG myapp.py: CORS_ALLOW_ORIGIN from env: {os.getenv('CORS_ALLOW_ORIGIN', 'NOT_SET')}")

# Create Flask app for serving React frontend
frontend_app = Flask(__name__)

# Enable CORS for all routes - use environment variable for dynamic configuration
cors_origin = os.getenv('CORS_ALLOW_ORIGIN', 'http://localhost:3000')
cors_origins = ['http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:6543', 'http://127.0.0.1:6543']
if cors_origin not in cors_origins:
    cors_origins.append(cors_origin)

print(f"DEBUG myapp.py: Flask CORS origins: {cors_origins}")
CORS(frontend_app, origins=cors_origins)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Determine the correct static folder path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
frontend_build_path = os.path.join(project_root, 'frontend', 'build')

# Fallback paths to try
possible_paths = [
    frontend_build_path,
    '/home/meena/lms-integration/lms_client/lms-frontend/build',
    os.path.join(current_dir, '..', 'frontend', 'build'),
    os.path.join(current_dir, 'frontend', 'build')
]

static_folder = None
for path in possible_paths:
    if os.path.exists(path):
        static_folder = path
        break

if not static_folder:
    logger.warning("Frontend build folder not found. Checked paths:")
    for path in possible_paths:
        logger.warning(f"  - {path}")
    static_folder = frontend_build_path  # Use default even if it doesn't exist

logger.info(f"Using static folder: {static_folder}")
logger.info(f"Static folder exists: {os.path.exists(static_folder)}")

# Update Flask app static folder
frontend_app.static_folder = static_folder

@frontend_app.before_request
def log_request():
    logger.info(f"Frontend request: {request.method} {request.path}")

@frontend_app.route('/')
def serve_react_app():
    """Serve the main React app"""
    try:
        return send_from_directory(static_folder, 'index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return jsonify({
            "error": "Frontend not found",
            "message": "React build files not found. Please run 'npm run build' in the frontend directory.",
            "static_folder": static_folder,
            "exists": os.path.exists(static_folder)
        }), 404

@frontend_app.route('/<path:filename>')
def serve_static_files(filename):
    """Serve static files (CSS, JS, images, etc.)"""
    try:
        return send_from_directory(static_folder, filename)
    except Exception as e:
        # If it's not a static file, serve the React app (for client-side routing)
        if not filename.startswith('static/') and not '.' in filename:
            return serve_react_app()
        logger.error(f"Error serving static file {filename}: {e}")
        return jsonify({"error": "File not found"}), 404

def create_pyramid_app():
    """Create and configure the Pyramid API app"""
    try:
        # Try to find the development.ini file
        ini_paths = [
            os.path.join(current_dir, 'development.ini'),
            os.path.join(current_dir, 'production.ini'),
        ]
        
        ini_file = None
        for path in ini_paths:
            if os.path.exists(path):
                ini_file = path
                break
        
        if not ini_file:
            logger.error("No configuration file found (development.ini or production.ini)")
            return None
            
        logger.info(f"Loading Pyramid app from: {ini_file}")
        pyramid_app = get_app(ini_file, 'main')
        logger.info("Pyramid app loaded successfully")
        return pyramid_app
        
    except Exception as e:
        logger.error(f"Failed to create Pyramid app: {e}")
        logger.exception("Full exception details:")
        return None

def create_combined_app():
    """Create a combined WSGI app with both Pyramid API and Flask frontend"""
    pyramid_app = create_pyramid_app()
    
    if pyramid_app is None:
        logger.warning("Pyramid app not available, serving only frontend")
        return frontend_app
    
    # Create dispatcher middleware to route requests
    # API requests go to Pyramid, everything else goes to Flask
    combined_app = DispatcherMiddleware(
        frontend_app,  # Default app (serves React frontend)
        {
            '/api': pyramid_app  # API requests go to Pyramid
        }
    )
    
    logger.info("Combined app created successfully")
    return combined_app

if __name__ == '__main__':
    logger.info("Starting LMS application...")
    logger.info(f"Current directory: {current_dir}")
    logger.info(f"Project root: {project_root}")
    logger.info(f"Frontend build path: {frontend_build_path}")
    
    # Create the combined application
    app = create_combined_app()
    
    # Start the server
    logger.info("Starting server on http://0.0.0.0:6543")
    logger.info("Frontend will be served at: http://localhost:6543")
    logger.info("API will be available at: http://localhost:6543/api")
    
    serve(app, host='0.0.0.0', port=6543)