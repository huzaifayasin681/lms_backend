"""
Custom exception classes for the LMS API with standardized error handling.
"""

import logging
from pyramid.httpexceptions import HTTPException
from datetime import datetime

log = logging.getLogger(__name__)


class LMSException(Exception):
    """Base exception for all LMS-related errors"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or 'LMS_ERROR'
        self.details = details or {}
        self.timestamp = datetime.now()
        
    def to_dict(self):
        """Convert exception to dictionary for API responses"""
        return {
            'error': True,
            'error_code': self.error_code,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }
    
    def log_error(self):
        """Log the error with appropriate level"""
        log.error(f"[{self.error_code}] {self.message}", extra=self.details)


class ValidationError(LMSException):
    """Validation error for input data"""
    
    def __init__(self, message: str, field: str = None, value=None):
        details = {}
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)
        super().__init__(message, 'VALIDATION_ERROR', details)


class AuthenticationError(LMSException):
    """Authentication-related errors"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 'AUTH_ERROR')


class AuthorizationError(LMSException):
    """Authorization-related errors"""
    
    def __init__(self, message: str = "Access denied", resource: str = None):
        details = {'resource': resource} if resource else {}
        super().__init__(message, 'ACCESS_DENIED', details)


class ResourceNotFoundError(LMSException):
    """Resource not found errors"""
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        details = {}
        if resource_type:
            details['resource_type'] = resource_type
        if resource_id:
            details['resource_id'] = resource_id
        super().__init__(message, 'RESOURCE_NOT_FOUND', details)


class DatabaseError(LMSException):
    """Database-related errors"""
    
    def __init__(self, message: str, operation: str = None, table: str = None):
        details = {}
        if operation:
            details['operation'] = operation
        if table:
            details['table'] = table
        super().__init__(message, 'DATABASE_ERROR', details)


class FileError(LMSException):
    """File operation errors"""
    
    def __init__(self, message: str, file_path: str = None, operation: str = None):
        details = {}
        if file_path:
            details['file_path'] = file_path
        if operation:
            details['operation'] = operation
        super().__init__(message, 'FILE_ERROR', details)


class LMSIntegrationError(LMSException):
    """LMS integration service errors"""
    
    def __init__(self, message: str, lms_type: str = None, operation: str = None):
        details = {}
        if lms_type:
            details['lms_type'] = lms_type
        if operation:
            details['operation'] = operation
        super().__init__(message, 'LMS_INTEGRATION_ERROR', details)


class ConfigurationError(LMSException):
    """Configuration-related errors"""
    
    def __init__(self, message: str, config_key: str = None):
        details = {'config_key': config_key} if config_key else {}
        super().__init__(message, 'CONFIG_ERROR', details)


class RateLimitError(LMSException):
    """Rate limiting errors"""
    
    def __init__(self, message: str = "Rate limit exceeded", limit: int = None, window: int = None):
        details = {}
        if limit:
            details['limit'] = limit
        if window:
            details['window'] = window
        super().__init__(message, 'RATE_LIMIT_ERROR', details)


class SyncError(LMSException):
    """Synchronization errors"""
    
    def __init__(self, message: str, sync_type: str = None, source: str = None):
        details = {}
        if sync_type:
            details['sync_type'] = sync_type
        if source:
            details['source'] = source
        super().__init__(message, 'SYNC_ERROR', details)


class ContentError(LMSException):
    """Content management errors"""
    
    def __init__(self, message: str, content_type: str = None, content_id: str = None):
        details = {}
        if content_type:
            details['content_type'] = content_type
        if content_id:
            details['content_id'] = content_id
        super().__init__(message, 'CONTENT_ERROR', details)


# Error code mapping for HTTP status codes
ERROR_CODE_HTTP_MAPPING = {
    'VALIDATION_ERROR': 400,
    'AUTH_ERROR': 401,
    'ACCESS_DENIED': 403,
    'RESOURCE_NOT_FOUND': 404,
    'RATE_LIMIT_ERROR': 429,
    'DATABASE_ERROR': 500,
    'FILE_ERROR': 500,
    'LMS_INTEGRATION_ERROR': 502,
    'CONFIG_ERROR': 500,
    'SYNC_ERROR': 500,
    'CONTENT_ERROR': 400,
    'LMS_ERROR': 500
}


def get_http_status_for_error(error_code: str) -> int:
    """Get appropriate HTTP status code for error code"""
    return ERROR_CODE_HTTP_MAPPING.get(error_code, 500)


class ErrorHandler:
    """Centralized error handler for the application"""
    
    @staticmethod
    def handle_exception(exc: Exception, request=None) -> dict:
        """Handle any exception and return standardized error response"""
        
        if isinstance(exc, LMSException):
            # Log the error
            exc.log_error()
            return exc.to_dict()
        
        elif isinstance(exc, HTTPException):
            # Handle Pyramid HTTP exceptions
            error_response = {
                'error': True,
                'error_code': f'HTTP_{exc.status_int}',
                'message': exc.detail or str(exc),
                'details': {},
                'timestamp': datetime.now().isoformat()
            }
            log.error(f"HTTP Exception {exc.status_int}: {exc.detail}")
            return error_response
        
        else:
            # Handle unexpected exceptions
            error_response = {
                'error': True,
                'error_code': 'INTERNAL_ERROR',
                'message': 'An unexpected error occurred',
                'details': {'exception_type': type(exc).__name__},
                'timestamp': datetime.now().isoformat()
            }
            log.exception(f"Unexpected error: {str(exc)}")
            return error_response
    
    @staticmethod
    def create_error_response(request, exc: Exception):
        """Create Pyramid response for exception"""
        error_dict = ErrorHandler.handle_exception(exc, request)
        
        # Determine HTTP status code
        if isinstance(exc, LMSException):
            status_code = get_http_status_for_error(exc.error_code)
        elif isinstance(exc, HTTPException):
            status_code = exc.status_int
        else:
            status_code = 500
        
        request.response.status = status_code
        return error_dict


# Decorator for automatic error handling in views
def handle_errors(func):
    """Decorator to automatically handle errors in view functions"""
    from functools import wraps
    
    @wraps(func)
    def wrapper(request):
        try:
            return func(request)
        except Exception as exc:
            return ErrorHandler.create_error_response(request, exc)
    
    return wrapper


# Context manager for database transactions with error handling
class DatabaseTransaction:
    """Context manager for database transactions with automatic rollback on error"""
    
    def __init__(self, session):
        self.session = session
        self.transaction_started = False
    
    def __enter__(self):
        self.session.begin()
        self.transaction_started = True
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Exception occurred, rollback transaction
            try:
                self.session.rollback()
                log.info("Database transaction rolled back due to error")
            except Exception as rollback_error:
                log.error(f"Error during rollback: {str(rollback_error)}")
            
            # If it's already an LMSException, don't wrap it
            if isinstance(exc_val, LMSException):
                return False
            
            # Convert to DatabaseError
            raise DatabaseError(
                f"Database transaction failed: {str(exc_val)}",
                operation="transaction"
            )
        else:
            # No exception, commit transaction
            try:
                self.session.commit()
                log.debug("Database transaction committed successfully")
            except Exception as commit_error:
                self.session.rollback()
                log.error(f"Error during commit: {str(commit_error)}")
                raise DatabaseError(
                    f"Failed to commit transaction: {str(commit_error)}",
                    operation="commit"
                )
        
        return False