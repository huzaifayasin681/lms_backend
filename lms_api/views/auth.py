from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPUnauthorized
from ..models import DBSession
from ..models.user import User
from ..auth import AuthService
import json
import os


# OPTIONS handlers removed - now handled by global OPTIONS handler in __init__.py


@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    """User login endpoint"""
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        raise HTTPBadRequest('Username and password required')
    
    user = DBSession.query(User).filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        raise HTTPUnauthorized('Invalid credentials')
    
    if not user.active:
        raise HTTPUnauthorized('Account is deactivated')
    
    token = AuthService.generate_token(user.id, user.username)
    
    return {
        'token': token,
        'user': user.to_dict()
    }


@view_config(route_name='register', request_method='POST', renderer='json')
def register(request):
    """User registration endpoint"""
    import re
    
    try:
        data = request.json_body
        print(f"Registration request received: {data}")
    except ValueError as e:
        print(f"Invalid JSON in registration request: {e}")
        raise HTTPBadRequest('Invalid JSON format')
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    print(f"Registration data: username={username}, email={email}, password_length={len(password) if password else 0}")
    
    # Validate required fields
    if not username or not email or not password:
        missing_fields = []
        if not username: missing_fields.append('username')
        if not email: missing_fields.append('email')
        if not password: missing_fields.append('password')
        raise HTTPBadRequest(f'Missing required fields: {", ".join(missing_fields)}')
    
    # Validate username
    if len(username) < 3:
        raise HTTPBadRequest('Username must be at least 3 characters long')
    if len(username) > 50:
        raise HTTPBadRequest('Username must be less than 50 characters long')
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        raise HTTPBadRequest('Username can only contain letters, numbers, hyphens, and underscores')
    
    # Validate email
    if len(email) > 255:
        raise HTTPBadRequest('Email must be less than 255 characters long')
    email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_pattern, email):
        raise HTTPBadRequest('Please enter a valid email address')
    
    # Validate password
    if len(password) < 6:
        raise HTTPBadRequest('Password must be at least 6 characters long')
    if len(password) > 128:
        raise HTTPBadRequest('Password must be less than 128 characters long')
    if not re.search(r'(?=.*[a-z])(?=.*[A-Z])(?=.*\d)', password):
        raise HTTPBadRequest('Password must contain at least one uppercase letter, one lowercase letter, and one number')
    
    try:
        # Check if user already exists
        existing_user = DBSession.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                raise HTTPBadRequest('Username already exists')
            else:
                raise HTTPBadRequest('Email already exists')
        
        print(f"Creating new user: {username}")
        
        # Create new user (defaults to is_admin=False, active=True)
        user = User(username=username, email=email)
        user.set_password(password)
        
        DBSession.add(user)
        DBSession.flush()  # Flush to get the user ID
        
        print(f"User created with ID: {user.id}")
        
        # Generate token
        token = AuthService.generate_token(user.id, user.username)
        
        # Commit the transaction
        DBSession.commit()
        
        print(f"Registration successful for user: {username}")
        
        return {
            'token': token,
            'user': user.to_dict(),
            'message': 'Registration successful'
        }
        
    except Exception as e:
        print(f"Registration error: {str(e)}")
        DBSession.rollback()
        
        # Re-raise HTTP exceptions
        if hasattr(e, 'status_code'):
            raise e
        
        # Handle database errors
        if 'UNIQUE constraint failed' in str(e):
            if 'username' in str(e):
                raise HTTPBadRequest('Username already exists')
            elif 'email' in str(e):
                raise HTTPBadRequest('Email already exists')
            else:
                raise HTTPBadRequest('User already exists')
        
        # Generic error
        raise HTTPBadRequest('Registration failed. Please try again.')