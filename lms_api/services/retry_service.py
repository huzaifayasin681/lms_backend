import time
import logging
import asyncio
from typing import Callable, Any, Optional, Dict
from functools import wraps
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)


class RetryService:
    """Enhanced retry service with exponential backoff and circuit breaker pattern"""
    
    def __init__(self):
        self.circuit_breakers = {}  # Track circuit breakers for different services
        
    def with_retry(self, 
                   max_attempts: int = 3,
                   backoff_factor: float = 1.0,
                   max_delay: int = 300,
                   exceptions: tuple = (Exception,),
                   exponential: bool = True):
        """Decorator for adding retry logic to functions"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                delay = backoff_factor
                
                for attempt in range(max_attempts):
                    try:
                        result = func(*args, **kwargs)
                        if attempt > 0:
                            log.info(f"Function {func.__name__} succeeded after {attempt + 1} attempts")
                        return result
                    except exceptions as e:
                        last_exception = e
                        
                        if attempt < max_attempts - 1:  # Don't delay on last attempt
                            if exponential:
                                delay = min(backoff_factor * (2 ** attempt), max_delay)
                            else:
                                delay = min(backoff_factor * (attempt + 1), max_delay)
                            
                            log.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. "
                                       f"Retrying in {delay} seconds...")
                            time.sleep(delay)
                        else:
                            log.error(f"All {max_attempts} attempts failed for {func.__name__}: {str(e)}")
                
                raise last_exception
            return wrapper
        return decorator
    
    def circuit_breaker(self,
                       failure_threshold: int = 5,
                       recovery_timeout: int = 60,
                       expected_exception: type = Exception):
        """Circuit breaker pattern to prevent cascading failures"""
        def decorator(func: Callable) -> Callable:
            func_name = func.__name__
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                circuit_state = self.circuit_breakers.get(func_name, {
                    'failures': 0,
                    'last_failure_time': None,
                    'state': 'closed'  # closed, open, half_open
                })
                
                current_time = datetime.now()
                
                # Check if circuit should be half-open (recovery attempt)
                if (circuit_state['state'] == 'open' and 
                    circuit_state['last_failure_time'] and
                    (current_time - circuit_state['last_failure_time']).seconds >= recovery_timeout):
                    circuit_state['state'] = 'half_open'
                    log.info(f"Circuit breaker for {func_name} moving to half-open state")
                
                # If circuit is open, fail fast
                if circuit_state['state'] == 'open':
                    raise Exception(f"Circuit breaker is open for {func_name}. "
                                   f"Service is temporarily unavailable.")
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Success - reset circuit breaker
                    if circuit_state['state'] == 'half_open':
                        log.info(f"Circuit breaker for {func_name} moving to closed state")
                    circuit_state.update({
                        'failures': 0,
                        'last_failure_time': None,
                        'state': 'closed'
                    })
                    self.circuit_breakers[func_name] = circuit_state
                    
                    return result
                    
                except expected_exception as e:
                    circuit_state['failures'] += 1
                    circuit_state['last_failure_time'] = current_time
                    
                    # Open circuit if threshold reached
                    if circuit_state['failures'] >= failure_threshold:
                        circuit_state['state'] = 'open'
                        log.error(f"Circuit breaker for {func_name} moving to open state "
                                 f"after {failure_threshold} failures")
                    
                    self.circuit_breakers[func_name] = circuit_state
                    raise
                    
            return wrapper
        return decorator
    
    def get_circuit_status(self) -> Dict[str, Dict]:
        """Get status of all circuit breakers"""
        status = {}
        current_time = datetime.now()
        
        for func_name, circuit_state in self.circuit_breakers.items():
            time_since_failure = None
            if circuit_state['last_failure_time']:
                time_since_failure = (current_time - circuit_state['last_failure_time']).seconds
            
            status[func_name] = {
                'state': circuit_state['state'],
                'failures': circuit_state['failures'],
                'time_since_failure': time_since_failure
            }
        
        return status


class TokenManager:
    """Manages API tokens with automatic refresh and validation"""
    
    def __init__(self):
        self.tokens = {}
        self.token_expiry = {}
        
    def store_token(self, service: str, token: str, expires_in: Optional[int] = None):
        """Store token with optional expiry"""
        self.tokens[service] = token
        if expires_in:
            self.token_expiry[service] = datetime.now() + timedelta(seconds=expires_in)
        log.info(f"Token stored for service: {service}")
    
    def get_valid_token(self, service: str) -> Optional[str]:
        """Get valid token, refreshing if necessary"""
        token = self.tokens.get(service)
        if not token:
            return None
        
        # Check if token is expired
        expiry = self.token_expiry.get(service)
        if expiry and datetime.now() >= expiry:
            log.warning(f"Token expired for service: {service}")
            try:
                # Attempt to refresh token
                self._refresh_token(service)
                return self.tokens.get(service)
            except Exception as e:
                log.error(f"Failed to refresh token for {service}: {str(e)}")
                return None
        
        return token
    
    def _refresh_token(self, service: str):
        """Refresh token for service (service-specific implementation needed)"""
        # This would be implemented for each service
        # For now, just remove expired token
        if service in self.tokens:
            del self.tokens[service]
        if service in self.token_expiry:
            del self.token_expiry[service]
        log.warning(f"Token removed for service {service} - manual refresh required")


class RobustHTTPClient:
    """HTTP client with built-in retry logic and error handling"""
    
    def __init__(self, 
                 max_retries: int = 3,
                 backoff_factor: float = 0.3,
                 timeout: int = 30):
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT"],
            backoff_factor=backoff_factor,
            raise_on_redirect=False,
            raise_on_status=False
        )
        
        # Create adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        
        # Create session
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Default timeout
        self.timeout = timeout
        
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic"""
        # Set default timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Check for HTTP errors
            if response.status_code >= 400:
                error_msg = f"HTTP {response.status_code} error for {method} {url}"
                if response.text:
                    error_msg += f": {response.text[:200]}"
                
                if response.status_code == 401:
                    raise TokenExpiredError(error_msg)
                elif response.status_code == 429:
                    raise RateLimitError(error_msg)
                elif response.status_code >= 500:
                    raise ServiceUnavailableError(error_msg)
                else:
                    raise HTTPError(error_msg)
            
            return response
            
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Request timeout for {method} {url}: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Connection error for {method} {url}: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise RequestError(f"Request error for {method} {url}: {str(e)}")
    
    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request('POST', url, **kwargs)
    
    def put(self, url: str, **kwargs) -> requests.Response:
        return self.request('PUT', url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> requests.Response:
        return self.request('DELETE', url, **kwargs)


# Custom Exception Classes
class HTTPError(Exception):
    """General HTTP error"""
    pass

class TokenExpiredError(HTTPError):
    """Token expired or invalid"""
    pass

class RateLimitError(HTTPError):
    """Rate limit exceeded"""
    pass

class ServiceUnavailableError(HTTPError):
    """Service temporarily unavailable"""
    pass

class RequestError(Exception):
    """Request-level error"""
    pass

class TimeoutError(RequestError):
    """Request timeout"""
    pass

class ConnectionError(RequestError):
    """Connection error"""
    pass


# Global instances
retry_service = RetryService()
token_manager = TokenManager()
http_client = RobustHTTPClient()


def get_retry_service():
    """Get global retry service instance"""
    return retry_service


def get_token_manager():
    """Get global token manager instance"""
    return token_manager


def get_http_client():
    """Get global HTTP client instance"""
    return http_client