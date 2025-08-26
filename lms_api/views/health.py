from pyramid.view import view_config


@view_config(route_name='health', request_method='GET', renderer='json')
def health_check(request):
    """Enhanced health check endpoint that tests database connectivity"""
    try:
        # Test database connectivity
        from ..models import DBSession
        from sqlalchemy import text
        
        # Try to execute a simple query to test the connection
        result = DBSession.execute(text("SELECT 1")).fetchone()
        
        # If we get here, the database connection is working
        db_status = "connected"
        db_message = "Database connection successful"
        
    except Exception as e:
        # Database connection failed
        db_status = "disconnected"
        db_message = f"Database connection failed: {str(e)}"
    
    # Return health status with database info
    return {
        'status': 'healthy' if db_status == 'connected' else 'unhealthy',
        'service': 'LMS API',
        'version': '1.0.0',
        'database': {
            'status': db_status,
            'message': db_message
        }
    }