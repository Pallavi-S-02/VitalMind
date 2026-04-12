from flask import Flask, jsonify
from flasgger import Swagger
from config import config

# Import the centralized db instance instead of creating a new one
from app.models import db

def create_app(config_name='development'):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load config
    app.config.from_object(config[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    
    from app.websocket import socketio
    socketio.init_app(app)
    
    # Setup Swagger for API documentation
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/docs",
        "title": "VitalMind API",
        "version": "1.0.0",
        "description": "API for VitalMind AI Healthcare Application",
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
            }
        }
    }
    Swagger(app, config=swagger_config)
    
    # Initialize middleware
    from app.middleware.cors import init_cors
    from app.middleware.rate_limiter import init_rate_limiter
    from app.middleware.request_logger import init_request_logger
    from app.middleware.error_handler import init_error_handler
    
    init_cors(app)
    init_rate_limiter(app)
    init_request_logger(app)
    init_error_handler(app)
    
    # Register blueprints
    from app.api.v1 import auth, patients, doctors, appointments, medications, reports
    from app.api.v1 import chat, messages
    from app.api.v1 import symptoms
    from app.api.v1 import devices, vitals
    from app.api.v1 import monitoring
    from app.api.v1 import triage
    from app.api.v1 import notifications
    from app.api.v1 import voice
    from app.api.v1 import voice_streaming
    from app.api.v1 import telemedicine
    from app.api.v1 import care_plans
    from app.api.v1 import analytics
    from app.api.v1 import search
    
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(patients.bp)
    app.register_blueprint(doctors.bp)
    app.register_blueprint(appointments.bp)
    app.register_blueprint(medications.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(chat.chat_bp)
    app.register_blueprint(messages.bp)
    app.register_blueprint(symptoms.symptoms_bp)
    app.register_blueprint(devices.bp)
    app.register_blueprint(vitals.bp)
    app.register_blueprint(monitoring.monitoring_bp)
    app.register_blueprint(triage.triage_bp)
    app.register_blueprint(notifications.notifications_bp)
    app.register_blueprint(voice.voice_bp)
    app.register_blueprint(voice_streaming.voice_stream_bp)
    app.register_blueprint(telemedicine.telemedicine_bp)
    app.register_blueprint(care_plans.care_plans_bp)
    app.register_blueprint(analytics.analytics_bp)
    app.register_blueprint(search.search_bp)


    # Register websocket handlers
    from app.api.websocket import chat_stream
    from app.api.websocket import vitals_stream
    from app.api.websocket import monitoring_events
    from app.api.websocket import notification_stream
    from app.api.websocket import voice_stream


    # Register specialist agents with the orchestrator
    try:
        from app.agents.symptom_analyst import SymptomAnalystAgent
        from app.services.agent_orchestrator_service import register_specialist
        register_specialist("symptom_check", SymptomAnalystAgent())
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not register SymptomAnalystAgent: %s", e)

    try:
        from app.agents.drug_interaction_agent import DrugInteractionAgent
        from app.services.agent_orchestrator_service import register_specialist
        register_specialist("drug_interaction", DrugInteractionAgent())
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not register DrugInteractionAgent: %s", e)

    try:
        from app.agents.monitoring_agent import MonitoringAgent
        from app.services.agent_orchestrator_service import register_specialist
        register_specialist("monitoring_query", MonitoringAgent(model="gemini-2.0-flash", temperature=0))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not register MonitoringAgent: %s", e)

    try:
        from app.agents.triage_agent import TriageAgent
        from app.services.agent_orchestrator_service import register_specialist
        register_specialist("triage", TriageAgent(model="gemini-2.0-flash", temperature=0))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not register TriageAgent: %s", e)

    try:
        from app.agents.voice_agent import VoiceAgent
        from app.services.agent_orchestrator_service import register_specialist
        register_specialist("voice_interaction", VoiceAgent(model="gemini-2.0-flash", temperature=0))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Could not register VoiceAgent: %s", e)
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({
            "status": "healthy",
            "environment": config_name
        }), 200
        
    return app
