from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize without app, app will be passed in init_app
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["50000 per day", "5000 per hour"],
    storage_uri="memory://" # Default to memory, can be overridden with Redis in production
)

def init_rate_limiter(app):
    """Initialize rate limiter for the app"""
    # In production, use Redis for rate limiting
    # redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
    # limiter.storage_uri = redis_url
    limiter.init_app(app)
