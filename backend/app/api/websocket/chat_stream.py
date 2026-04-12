import logging
from flask import request
from flask_socketio import emit, disconnect
from app.services.auth_service import AuthService

from app.websocket import socketio
from app.services.agent_orchestrator_service import OrchestratorService


logger = logging.getLogger(__name__)

# Basic dictionary to track connected active user (sid -> user_id)
# Note: In a production environment with multiple workers (e.g. gunicorn + eventlet),
# Redis-based session tracking is needed instead.
connected_users = {}

@socketio.on('connect')
def handle_connect(auth):
    """
    Handle new websocket connections. Requires JWT authentication.
    """
    if not auth or 'token' not in auth:
        logger.warning("Socket connect refused: No token provided")
        disconnect()
        return False

    try:
        token = auth['token']
        # Remove 'Bearer ' prefix if accidentally included
        if token.startswith("Bearer "):
            token = token[7:]
            
        decoded = AuthService.decode_token(token)
        if isinstance(decoded, str):
            raise Exception(decoded)
        user_identity = decoded.get('sub') # Should be UUID string
        
        # We can look up the user context here if needed
        # Just store the user ID against the socket session
        connected_users[request.sid] = user_identity
        logger.info(f"Socket connected: SID {request.sid} for user {user_identity}")
        
    except Exception as e:
        logger.warning(f"Socket connect refused: Invalid token - {str(e)}")
        disconnect()
        return False

@socketio.on('disconnect')
def handle_disconnect():
    user_id = connected_users.pop(request.sid, None)
    logger.info(f"Socket disconnected: SID {request.sid} for user {user_id}")

@socketio.on('chat_message')
def handle_chat_message(data):
    """
    Handle incoming chat message asking to stream the AI response.
    Expected data format:
      {
         "message": "Hello doc",
         "session_id": "optional-uuid"
      }
    """
    user_id = connected_users.get(request.sid)
    if not user_id:
        emit('error', {'detail': 'Not authenticated on socket'})
        return

    message = data.get('message', '').strip()
    session_id = data.get('session_id')

    if not message:
        emit('error', {'detail': 'Empty message'})
        return

    logger.info(f"Socket message received from {user_id} in session {session_id}")
    
    try:
        # Instead of `process_message`, we call the new `stream_process_message` generator
        for chunk in OrchestratorService.stream_process_message(
            message=message,
            patient_id=user_id,
            session_id=session_id
        ):
            # The generator yields dicts. We identify chunks versus the final payload.
            if chunk.get('type') == 'chunk':
                emit('chat_chunk', {'content': chunk['content']})
            elif chunk.get('type') == 'complete':
                emit('chat_complete', chunk['data'])
            elif chunk.get('type') == 'error':
                emit('error', {'detail': chunk['detail']})
                
    except Exception as e:
        logger.exception(f"Unhandled error in chat streaming: {e}")
        emit('error', {'detail': 'Internal Server Error during streaming'})
