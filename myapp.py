from flask import Flask, send_from_directory, request
from flask_cors import CORS
from waitress import serve
from pyramid.paster import get_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from dotenv import load_dotenv
import os
import sys

load_dotenv()

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(BASE_DIR, "build")
STATIC_DIR = os.path.join(BUILD_DIR, "static")

# Disable Flask's built-in static route so it doesn't steal /static/*
app = Flask(__name__, static_folder=None)
CORS(app,
     origins=os.getenv('CORS_ALLOW_ORIGIN', 'http://localhost:6543').split(','),
     supports_credentials=True)

print(f"Build dir: {BUILD_DIR}  exists={os.path.exists(BUILD_DIR)}")
print(f"Static dir: {STATIC_DIR} exists={os.path.exists(STATIC_DIR)}")
if os.path.exists(STATIC_DIR):
    print("Static subfolders:", os.listdir(STATIC_DIR))

@app.before_request
def log_request():
    print(f"Request: {request.method} {request.path}")

# Serve hashed assets (CRA/Vite) from build/static/*
@app.route('/static/<path:filename>')
def static_files(filename):
    try:
        return send_from_directory(STATIC_DIR, filename)
    except Exception as e:
        print(f"Error serving /static/{filename}: {e}")
        return '', 404

# Index
@app.route('/')
def index():
    return send_from_directory(BUILD_DIR, 'index.html')

# SPA fallback (only when there is no dot in the path)
@app.route('/<path:path>')
def catch_all(path):
    if '.' not in path:
        return send_from_directory(BUILD_DIR, 'index.html')
    return '', 404

def create_app():
    """Mount Pyramid under /api and keep Flask for SPA/static."""
    try:
        config_file = os.path.join(BASE_DIR, 'development.ini')
        if not os.path.exists(config_file):
            print(f"⚠️ Config file not found: {config_file}")
            return app
        
        pyramid_app = get_app(config_file, 'main')
        print("✅ Pyramid backend mounted successfully under /api")
        # Anything under /api is handled by Pyramid
        return DispatcherMiddleware(app, {'/api': pyramid_app})
    except Exception as e:
        print(f"⚠️ Could not mount Pyramid under /api: {e}")
        print("Running Flask-only mode (frontend only)")
        return app

if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.getenv('PORT', 6543))
    host = os.getenv('HOST', '0.0.0.0')
    
    print(f"🚀 Starting server on {host}:{port}")
    print(f"📁 Serving frontend from: {BUILD_DIR}")
    print(f"🔗 Frontend URL: http://localhost:{port}")
    print(f"🔗 Backend API URL: http://localhost:{port}/api")
    
    try:
        # Serve the composed app (so /api works)
        serve(create_app(), host=host, port=port, threads=6)
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)
