import os
import sys
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_babel import Babel
from flask_caching import Cache
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
babel = Babel()
cache = Cache()

# Configure SocketIO with eventlet
try:
    import eventlet
    eventlet.monkey_patch()
    print("Using eventlet for SocketIO")
    async_mode = 'eventlet'
except ImportError:
    print("Warning: eventlet is not available. Using threading mode")
    async_mode = 'threading'

# Initialize SocketIO with proper WebSocket configuration
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode=async_mode,
    engineio_logger=True,
    logger=True,
    ping_timeout=60,
    ping_interval=25,
    manage_session=False,  # Let Flask handle the session
    allow_upgrades=True,
    http_compression=True,
    max_http_buffer_size=1e8,  # 100MB max message size
    message_queue='redis://' if os.environ.get('REDIS_URL') else None,
    async_handlers=True,
    always_connect=True
)

# Initialize CSRF protection
csrf = CSRFProtect()
