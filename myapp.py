# backend/myapp.py
from lms_api import main
import os

# Create the WSGI application with the required global_config argument
def create_app():
    ini_path = os.path.join(os.path.dirname(__file__), 'development.ini')
    # The global_config is an empty dict for basic usage
    return main({}, __file__=ini_path)

# Create the application instance
application = create_app()

if __name__ == "__main__":
    # This is for development only
    from wsgiref.simple_server import make_server
    server = make_server('localhost', 6543, application)
    print("Serving on http://localhost:6543")
    server.serve_forever()