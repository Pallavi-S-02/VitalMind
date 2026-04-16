from flask_socketio import SocketIO

# Create the SocketIO instance globally so we can emit from anywhere
# We enable cors_allowed_origins="*" for local development
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
