import jwt
import os
from datetime import datetime, timedelta
from pyramid.httpexceptions import HTTPUnauthorized
from functools import wraps
from .models.user import User
from .models import DBSession


class AuthService:
    @staticmethod
    def generate_token(user_id, username):
        """Generate JWT token"""
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }
        secret = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
        return jwt.encode(payload, secret, algorithm='HS256')
    
    @staticmethod
    def decode_token(token):
        """Decode and validate JWT token"""
        try:
            secret = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
            payload = jwt.decode(token, secret, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def get_current_user(request):
        """Get current user from request"""
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
        
        try:
            token = auth_header.split(' ')[1]  # Bearer <token>
            payload = AuthService.decode_token(token)
            if not payload:
                return None
            
            user = DBSession.query(User).filter_by(id=payload['user_id']).first()
            return user
        except (IndexError, KeyError):
            return None


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def wrapper(request):
        user = AuthService.get_current_user(request)
        if not user:
            raise HTTPUnauthorized('Authentication required')
        request.user = user
        return f(request)
    return wrapper