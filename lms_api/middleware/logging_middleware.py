"""
Logging middleware for comprehensive request/response logging and error tracking.
"""

import time
import logging
import json
from datetime import datetime
from pyramid.response import Response

log = logging.getLogger(__name__)

class LoggingMiddleware:
    """WSGI middleware for comprehensive request/response logging"""
    
    def __init__(self, app, config=None):
        self.app = app
        self.config = config or {}
        self.log_requests = self.config.get('log_requests', True)
        self.log_responses = self.config.get('log_responses', True)
        self.log_errors = self.config.get('log_errors', True)
        self.log_performance = self.config.get('log_performance', True)
        self.sensitive_headers = {'authorization', 'cookie', 'x-api-key', 'x-auth-token'}
        
    def __call__(self, environ, start_response):
        request_start_time = time.time()
        request_id = self._generate_request_id()
        
        # Add request ID to environ for tracking
        environ['REQUEST_ID'] = request_id
        
        # Log request
        if self.log_requests:
            self._log_request(environ, request_id)
        
        # Capture response data
        response_data = {'status': None, 'headers': None, 'body_size': 0}
        
        def new_start_response(status, response_headers, exc_info=None):
            response_data['status'] = status
            response_data['headers'] = dict(response_headers)
            return start_response(status, response_headers, exc_info)
        
        try:
            # Call the application
            app_iter = self.app(environ, new_start_response)
            
            # Calculate response body size
            if hasattr(app_iter, '__iter__'):
                body_parts = list(app_iter)
                response_data['body_size'] = sum(len(part) for part in body_parts)
                
                # Log response
                request_duration = time.time() - request_start_time
                if self.log_responses:
                    self._log_response(environ, response_data, request_duration, request_id)
                
                if self.log_performance:
                    self._log_performance(environ, request_duration, request_id)
                
                return iter(body_parts)
            else:
                return app_iter
                
        except Exception as e:
            request_duration = time.time() - request_start_time
            
            if self.log_errors:
                self._log_error(environ, e, request_duration, request_id)
            
            raise
    
    def _generate_request_id(self):
        """Generate unique request ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _log_request(self, environ, request_id):
        """Log incoming request details"""
        request_data = {
            'request_id': request_id,
            'method': environ.get('REQUEST_METHOD', 'UNKNOWN'),
            'path': environ.get('PATH_INFO', '/'),
            'query_string': environ.get('QUERY_STRING', ''),
            'remote_addr': environ.get('REMOTE_ADDR', 'unknown'),
            'user_agent': environ.get('HTTP_USER_AGENT', 'unknown'),
            'content_type': environ.get('CONTENT_TYPE', ''),
            'content_length': environ.get('CONTENT_LENGTH', '0'),
            'timestamp': datetime.now().isoformat()
        }
        
        # Log headers (excluding sensitive ones)
        headers = {}
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].lower().replace('_', '-')
                if header_name not in self.sensitive_headers:
                    headers[header_name] = value
                else:
                    headers[header_name] = '[REDACTED]'
        
        request_data['headers'] = headers
        
        log.info(f"REQUEST [{request_id}] {request_data['method']} {request_data['path']}", 
                extra={'request_data': request_data})
    
    def _log_response(self, environ, response_data, duration, request_id):
        """Log response details"""
        status_code = response_data['status'].split()[0] if response_data['status'] else '000'
        
        response_log_data = {
            'request_id': request_id,
            'status': status_code,
            'body_size': response_data['body_size'],
            'duration_ms': round(duration * 1000, 2),
            'timestamp': datetime.now().isoformat()
        }
        
        # Log non-sensitive response headers
        if response_data['headers']:
            safe_headers = {}
            for key, value in response_data['headers'].items():
                if key.lower() not in self.sensitive_headers:
                    safe_headers[key] = value
            response_log_data['headers'] = safe_headers
        
        log.info(f"RESPONSE [{request_id}] {status_code} ({duration*1000:.2f}ms)", 
                extra={'response_data': response_log_data})
    
    def _log_performance(self, environ, duration, request_id):
        """Log performance metrics"""
        method = environ.get('REQUEST_METHOD', 'UNKNOWN')
        path = environ.get('PATH_INFO', '/')
        
        performance_data = {
            'request_id': request_id,
            'method': method,
            'path': path,
            'duration_ms': round(duration * 1000, 2),
            'timestamp': datetime.now().isoformat()
        }
        
        # Flag slow requests
        if duration > 2.0:  # More than 2 seconds
            log.warning(f"SLOW REQUEST [{request_id}] {method} {path} took {duration:.2f}s", 
                       extra={'performance_data': performance_data})
        elif duration > 5.0:  # More than 5 seconds  
            log.error(f"VERY SLOW REQUEST [{request_id}] {method} {path} took {duration:.2f}s", 
                     extra={'performance_data': performance_data})
        else:
            log.debug(f"PERFORMANCE [{request_id}] {method} {path} ({duration*1000:.2f}ms)", 
                     extra={'performance_data': performance_data})
    
    def _log_error(self, environ, error, duration, request_id):
        """Log error details"""
        method = environ.get('REQUEST_METHOD', 'UNKNOWN')
        path = environ.get('PATH_INFO', '/')
        
        error_data = {
            'request_id': request_id,
            'method': method,
            'path': path,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'duration_ms': round(duration * 1000, 2),
            'timestamp': datetime.now().isoformat()
        }
        
        log.error(f"ERROR [{request_id}] {method} {path} - {type(error).__name__}: {str(error)}", 
                 extra={'error_data': error_data}, exc_info=True)


def create_logging_middleware(app, global_config=None, **local_config):
    """Factory function for creating logging middleware"""
    config = {}
    if global_config:
        config.update(global_config)
    config.update(local_config)
    
    return LoggingMiddleware(app, config)