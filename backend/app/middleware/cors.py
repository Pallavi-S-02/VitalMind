from flask_cors import CORS
import os

def init_cors(app):
    """Initialize CORS with secure mapped origins"""
    # Parse comma-separated origins, default strictly to local frontend
    default_origins = "http://localhost:3000,http://127.0.0.1:3000"
    allowed_origins_str = os.environ.get("CORS_ALLOWED_ORIGINS", default_origins)
    allowed_origins = [obs.strip() for obs in allowed_origins_str.split(",") if obs.strip()]

    CORS(
        app, 
        resources={
            r"/api/*": {
                "origins": allowed_origins,
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
            }
        }, 
        supports_credentials=True
    )
