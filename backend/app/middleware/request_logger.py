import logging
import time
from flask import request, g

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('med_assist_api')

def init_request_logger(app):
    """Initialize request logging for the app"""
    
    @app.before_request
    def log_request_info():
        # Start timer
        g.start_time = time.time()
        
        # Don't log health checks or static files
        if request.path == '/health' or request.path.startswith('/static'):
            return
            
        logger.info(f"Request: {request.method} {request.url}")
        # Log headers (excluding sensitive ones like Authorization)
        safe_headers = {k: v for k, v in request.headers.items() if k.lower() != 'authorization'}
        logger.debug(f"Headers: {safe_headers}")

    @app.after_request
    def log_response_info(response):
        # Don't log health checks or static files
        if request.path == '/health' or request.path.startswith('/static'):
            return response
            
        # Calculate duration
        duration = 0
        if hasattr(g, 'start_time'):
            duration = (time.time() - g.start_time) * 1000  # in ms
            
        logger.info(f"Response: {response.status_code} [{duration:.2f}ms]")
        return response
