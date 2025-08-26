from flask import Flask, send_from_directory, request
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

# Create Flask app without CORS (as requested)
app = Flask(__name__, static_folder=None)

print(f"Build dir: {BUILD_DIR}  exists={os.path.exists(BUILD_DIR)}")
print(f"Static dir: {STATIC_DIR} exists={os.path.exists(STATIC_DIR)}")
if os.path.exists(STATIC_DIR):
    print("Static subfolders:", os.listdir(STATIC_DIR))

@app.before_request
def log_request():
    print(f"Request: {request.method} {request.path}")

# Serve static assets from build/static/*
@app.route('/static/<path:filename>')
def static_files(filename):
    try:
        return send_from_directory(STATIC_DIR, filename)
    except Exception as e:
        print(f"Error serving /static/{filename}: {e}")
        return '', 404

# Index route
@app.route('/')
def index():
    return send_from_directory(BUILD_DIR, 'index.html')

# SPA fallback for React Router
@app.route('/<path:path>')
def catch_all(path):
    if '.' not in path:
        return send_from_directory(BUILD_DIR, 'index.html')
    return '', 404

def create_app():
    """Mount Pyramid backend under /api and Flask for frontend."""
    try:
        config_file = os.path.join(BASE_DIR, 'development.ini')
        if not os.path.exists(config_file):
            print(f"⚠️ Config file not found: {config_file}")
            return app
        
        pyramid_app = get_app(config_file, 'main')
        print("✅ Pyramid backend mounted successfully under /api")
        
        # Mount Pyramid under /api, Flask handles everything else
        return DispatcherMiddleware(app, {'/api': pyramid_app})
    except Exception as e:
        print(f"⚠️ Could not mount Pyramid under /api: {e}")
        print("Running Flask-only mode (frontend only)")
        return app

if __name__ == '__main__':
    port = 6543
    host = '0.0.0.0'
    
    print(f"🚀 Starting server on {host}:{port}")
    print(f"📁 Serving frontend from: {BUILD_DIR}")
    print(f"🔗 External URL: http://jhbnet.ddns.net:46543/")
    print(f"🔗 Local URL: http://localhost:{port}")
    print(f"🔗 Backend API: http://jhbnet.ddns.net:46543/api")
    
    try:
        serve(create_app(), host=host, port=port, threads=6)
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)