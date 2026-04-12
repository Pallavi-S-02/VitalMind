from flask import Blueprint

# Import blueprints
from .auth import auth_bp

def register_blueprints(app):
    """Register all API blueprints"""
    app.register_blueprint(auth_bp)
