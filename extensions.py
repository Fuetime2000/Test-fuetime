from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_babel import Babel
from flask_caching import Cache
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
import sys

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
babel = Babel()
cache = Cache()

# Configure SocketIO with gevent
try:
    import gevent
    from gevent import monkey
    monkey.patch_all()
    print("Using gevent for SocketIO")
    async_mode = 'gevent'
except ImportError:
    print("Warning: gevent is not available. Using threading mode")
    async_mode = 'threading'

# Initialize SocketIO
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode=async_mode,
    engineio_logger=True,
    logger=True,
    ping_timeout=60,
    manage_session=False  # Let Flask handle the session
)

# Initialize CSRF protection
csrf = CSRFProtect()
