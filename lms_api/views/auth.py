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
    try:
        data = request.json_body
    except ValueError:
        raise HTTPBadRequest('Invalid JSON')
    
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        raise HTTPBadRequest('Username, email, and password required')
    
    if len(password) < 6:
        raise HTTPBadRequest('Password must be at least 6 characters')
    
    # Check if user already exists
    existing_user = DBSession.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    
    if existing_user:
        raise HTTPBadRequest('Username or email already exists')
    
    # Create new user
    user = User(username=username, email=email)
    user.set_password(password)
    
    DBSession.add(user)
    DBSession.commit()
    
    token = AuthService.generate_token(user.id, user.username)
    
    return {
        'token': token,
        'user': user.to_dict()
    }