

from app import create_app
from app.websocket import socketio
from app.models import db
from flask_migrate import Migrate
import os

app = create_app(os.getenv('FLASK_ENV', 'development'))
migrate = Migrate(app, db)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
