import logging
from logging.handlers import RotatingFileHandler
import os
import secrets
import uuid
from datetime import datetime
import time
import traceback
import smtplib
from itertools import groupby
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify, make_response, send_from_directory, Response, g, send_file, current_app
from werkzeug.utils import secure_filename
from blueprints.main import bp as main_bp
from flask_login import UserMixin, login_user, login_required, logout_user, current_user
from functools import wraps
from flask_socketio import emit, join_room, leave_room
from flask_babel import gettext as _


# Import models
from models.user import User
from models.transaction import Transaction

# Import Socket.IO event handlers
import events

# Initialize Flask app
app = Flask(__name__)
app.config.from_pyfile('config.py')

# Initialize Flask-Migrate
from extensions import db
from flask_migrate import Migrate
migrate = Migrate(app, db)

# Import SocketIO
try:
    from extensions import socketio
except ImportError:
    print("Error: Could not import socketio from extensions")
    socketio = None

def init_socketio_handlers():
    """Initialize and register all Socket.IO event handlers."""
    if socketio is None:
        print("Error: socketio is not initialized")
        return
        
    try:
        # Import and register socket handlers
        from blueprints.messages import register_socket_events
        from events import register_socketio_events
        
        # Register message handlers
        register_socket_events()
        
        # Register other socket events
        register_socketio_events()
        
        print("Socket.IO event handlers registered")
    except Exception as e:
        print(f"Error initializing Socket.IO handlers: {e}")

# Configure upload folders
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['PROFILE_PICS_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics')

# Configure app
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fuetime.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'o3#7n4@43y0ry5j4@2me+nn@vbu32rr=w7mz)1yzz7egy^)qn*'

# Email configuration - Using SSL on port 465
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465  # SSL port
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'dipendra998405@gmail.com'  # Your Gmail address
app.config['MAIL_PASSWORD'] = 'qrjz depb zcsz zcba'  # Your App Password
app.config['MAIL_DEFAULT_SENDER'] = 'dipendra998405@gmail.com'  # Your Gmail address
app.config['MAIL_DEBUG'] = True  # Enable debug output

# Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Flask-Login configuration
app.config['REMEMBER_COOKIE_DURATION'] = 86400  # 24 hours
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'

# Import and initialize extensions
from extensions import db, login_manager, babel, socketio, cache, csrf

# Configure upload folder for project images
def configure_upload_folders():
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    app.config['PROFILE_PICS_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics')
    
    # Debug output for upload configuration
    print("\n=== UPLOAD CONFIGURATION ===")
    print(f"UPLOAD_FOLDER: {app.config['UPLOAD_FOLDER']}")
    print(f"PROFILE_PICS_FOLDER: {app.config['PROFILE_PICS_FOLDER']}")
    print("==========================\n")
    
    # Create upload directories if they don't exist
    for folder in [app.config['UPLOAD_FOLDER'], app.config['PROFILE_PICS_FOLDER']]:
        try:
            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
                print(f"Created directory: {folder}")
            else:
                print(f"Directory exists: {folder}")
            # Verify directory is writable
            test_file = os.path.join(folder, '.test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"Directory is writable: {folder}")
        except Exception as e:
            print(f"Error with directory {folder}: {str(e)}")

# Initialize upload folders
configure_upload_folders()

# Route to serve profile pictures
@app.route('/profile_pic/<filename>')
def serve_profile_pic(filename):
    try:
        if not filename or filename == 'None':
            return send_from_directory('static', 'img/default-avatar.png')
            
        # Security check to prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            return send_from_directory('static', 'img/default-avatar.png')
        
        # Check if file exists in profile_pics folder
        profile_pics_path = os.path.join(current_app.config['PROFILE_PICS_FOLDER'], filename)
        if os.path.isfile(profile_pics_path):
            return send_from_directory(current_app.config['PROFILE_PICS_FOLDER'], filename)
            
        # If not found in profile_pics, check the root uploads folder
        uploads_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(uploads_path):
            return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
            
        # If not found anywhere, return default avatar
        return send_from_directory('static', 'img/default-avatar.png')
        
    except Exception as e:
        current_app.logger.error(f"Error serving profile picture {filename}: {str(e)}")
        return send_from_directory('static', 'img/default-avatar.png')

# Initialize upload folders on first request
_upload_folders_configured = False

@app.before_request
def ensure_upload_folders():
    global _upload_folders_configured
    if not _upload_folders_configured:
        configure_upload_folders()
        _upload_folders_configured = True

db.init_app(app)
login_manager.init_app(app)
babel.init_app(app)
cache.init_app(app)

# Blueprints are registered in blueprints/__init__.py
csrf.init_app(app)
socketio.init_app(app)

# Import all models after app and db initialization
from models.user import User
from models.review import Review
from models.project import Project, Technology
# Create tables after all models are imported
with app.app_context():
    try:
        # Create all database tables
        db.create_all()
        app.logger.info("Database tables created successfully")
        
        # Verify that all required tables exist
        inspector = db.inspect(db.engine)
        required_tables = ['user', 'call', 'transaction']
        for table in required_tables:
            if not inspector.has_table(table):
                app.logger.error(f"Required table '{table}' was not created!")
    except Exception as e:
        app.logger.error(f"Error creating database tables: {str(e)}")
        raise

# Import and register blueprints
# All blueprints are now registered through blueprints/__init__.py


@app.route('/test/profile-pic')
def test_profile_pic():
    """Test route to check profile picture functionality"""
    if not current_user.is_authenticated:
        return "Please log in to test profile picture functionality."
    
    user = User.query.get(current_user.id)
    if not user:
        return "User not found."
    
    result = {
        'user_id': user.id,
        'email': user.email,
        'has_photo': bool(user.photo),
        'photo_path': user.photo,
        'full_path': os.path.join(app.config['PROFILE_PICS_FOLDER'], user.photo) if user.photo else None,
        'file_exists': os.path.exists(os.path.join(app.config['PROFILE_PICS_FOLDER'], user.photo)) if user.photo else False,
        'upload_dir': app.config['PROFILE_PICS_FOLDER'],
        'files_in_upload_dir': os.listdir(app.config['PROFILE_PICS_FOLDER']) if os.path.exists(app.config['PROFILE_PICS_FOLDER']) else 'Directory does not exist'
    }
    
    return jsonify(result)

@login_manager.user_loader
def load_user(user_id):
    try:
        # Try to get the user from the database
        user = User.query.get(int(user_id))
        if user:
            # Update the user's last seen timestamp
            user.update_last_seen()
            db.session.commit()
        return user
    except Exception as e:
        app.logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

# Configure logging
if not os.path.exists('logs'):
    os.mkdir('logs')

# Create a file handler for logging using WatchedFileHandler
from logging.handlers import WatchedFileHandler
log_file = 'logs/fuetime.log'

# Create a file handler for logging
file_handler = WatchedFileHandler(log_file)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)

# Create a console handler for logging to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure the root logger
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Avoid duplicate handlers
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
from flask_caching import Cache
from flask_compress import Compress
from flask_wtf.csrf import generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
from PIL import Image
from math import radians, sin, cos, sqrt, atan2
from routes import main_bp, portfolio_bp, review_bp
from models.message import Message
from models.behavior_tracking import UserBehavior, FraudAlert
from filters import avg
import os
import json
import uuid
import re
import io
import base64
import secrets
import time
from sqlalchemy import text, inspect
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import re
import razorpay
import hmac
import hashlib
import json
from flask_wtf.csrf import CSRFProtect, CSRFError
from functools import wraps
from itsdangerous import URLSafeTimedSerializer
from flask_babel import gettext as _
from sqlalchemy import text, inspect
import time
from urllib.parse import urlparse, urljoin

from extensions import db, login_manager, migrate, babel, cache, socketio, csrf
# Import models
from models import (
    User, ContactRequest, Review, Message, HelpRequest, 
    UserInteraction, Transaction, UserBehavior, FraudAlert, 
    Donation, Call, Project, Technology, PortfolioRating
)
from routes import main_bp, portfolio_bp, review_bp # Updated blueprint imports

# Import Socket.IO event handlers
from events import *  # This imports all Socket.IO event handlers

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Set max content length to 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Set upload folder
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')

# Import and initialize blueprints
from blueprints import init_app as register_blueprints

# Register all blueprints through the init_app function
register_blueprints(app)

# Set database URI and other configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.abspath(os.path.join(os.path.dirname(__file__), 'fuetime.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True

@app.template_filter('timeago')
def timeago_filter(dt):
    if not dt:
        return ''
    
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days} day{"s" if days != 1 else ""} ago'
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f'{weeks} week{"s" if weeks != 1 else ""} ago'
    else:
        return dt.strftime('%Y-%m-%d')
app.config['SECRET_KEY'] = 'o3#7n4@43y0ry5j4@2me+nn@vbu32rr=w7mz)1yzz7egy^)qn*'
app.config['CACHE_TYPE'] = 'simple'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 30,
    'max_overflow': 40,
    'pool_timeout': 30,
    'connect_args': {'check_same_thread': False}
}

# Configure upload folder for portfolio images
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.user_type != 'client':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Premium dashboard route
@app.route('/premium-dashboard')
@login_required
def premium_dashboard():
    # Check if user is a client
    if current_user.user_type != 'client':
        flash('Access denied. This area is for business clients only.', 'danger')
        return redirect(url_for('dashboard'))
        
    # Get statistics
    stats = {
        'viewed_workers': UserInteraction.query.filter_by(
            viewer_id=current_user.id,
            interaction_type='view'
        ).count(),
        'contact_requests': ContactRequest.query.filter_by(
            requester_id=current_user.id
        ).count(),
        'active_chats': Message.query.filter_by(
            sender_id=current_user.id
        ).distinct(Message.receiver_id).count()
    }
    
    # Get recent activities
    recent_activities = []
    
    # Add view interactions
    views = UserInteraction.query.filter_by(
        viewer_id=current_user.id,
        interaction_type='view'
    ).order_by(UserInteraction.created_at.desc()).limit(5).all()
    
    for view in views:
        recent_activities.append({
            'timestamp': view.created_at,
            'description': 'Viewed profile',
            'worker': User.query.get(view.viewed_id),
            'status': 'Viewed',
            'status_color': 'info'
        })
    
    # Add contact requests
    requests = ContactRequest.query.filter_by(
        requester_id=current_user.id
    ).order_by(ContactRequest.created_at.desc()).limit(5).all()
    
    for req in requests:
        recent_activities.append({
            'timestamp': req.created_at,
            'description': 'Contact request',
            'worker': User.query.get(req.requested_id),
            'status': req.status.capitalize(),
            'status_color': 'success' if req.status == 'accepted' else 'warning'
        })
    
    # Sort activities by timestamp
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Get saved workers (implement this feature later)
    saved_workers = []
    
    # Get recent chats
    recent_chats = []
    recent_messages = Message.query.filter(
        ((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.desc()).limit(10).all()
    
    chat_workers = set()
    for message in recent_messages:
        worker_id = message.receiver_id if message.sender_id == current_user.id else message.sender_id
        if worker_id not in chat_workers and len(chat_workers) < 6:
            worker = User.query.get(worker_id)
            if worker and worker.user_type == 'worker':
                chat_workers.add(worker_id)
                recent_chats.append({
                    'worker': worker,
                    'last_message': message
                })
    
    # Get the latest user data with wallet balance
    user = User.query.get(current_user.id)
    
    return render_template('premium_dashboard.html',
                           stats=stats,
                           recent_activities=recent_activities,
                           saved_workers=saved_workers,
                           recent_chats=recent_chats,
                           wallet_balance=user.wallet_balance)

# Enable compression
Compress(app)

# Configure static file caching
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year
app.static_folder = 'static'

# Initialize extensions
# Ensure this is done after app configuration and before app.run()

# Ensure extensions are only initialized once
if not hasattr(app, 'extensions') or 'sqlalchemy' not in app.extensions:
    # Initialize database and auth
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app)
    cache.init_app(app)
    csrf.init_app(app)

# Configure WebSocket settings
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = True
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

# Initialize Socket.IO
socketio.init_app(app, 
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    cors_allowed_origins='*',
    max_http_buffer_size=16 * 1024 * 1024,  # 16MB for file uploads
    message_queue=None,
    logger=True,
    engineio_logger=True,
    manage_session=True)

@app.route('/health')
def health_check():
    return "OK", 200

# Serve static files with optimized caching and compression
@app.route('/static/<path:filename>')
def serve_static(filename):
    response = send_from_directory(app.static_folder, filename)
    response.cache_control.max_age = 31536000  # 1 year
    response.cache_control.public = True
    response.cache_control.immutable = True
    
    # Add ETag for caching
    if request.if_none_match and request.if_none_match.contains(response.get_etag()[0]):
        return '', 304
    
    # Enable compression for text-based files
    if filename.endswith(('.js', '.css', '.html', '.txt', '.svg')):
        response.headers['Content-Encoding'] = 'gzip'
        response.direct_passthrough = False
    
    return response

# Serve uploaded files from the uploads directory
@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    try:
        if not filename or filename == 'None':
            return send_from_directory('static', 'img/default-avatar.png')
            
        # Security check to prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            return send_from_directory('static', 'img/default-avatar.png')
            
        # First try profile_pics directory
        profile_pics_path = os.path.join(current_app.config['PROFILE_PICS_FOLDER'], filename)
        if os.path.isfile(profile_pics_path):
            return send_from_directory(current_app.config['PROFILE_PICS_FOLDER'], filename)
            
        # Then try the root uploads directory
        uploads_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(uploads_path):
            return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
            
        # If file not found, return default avatar
        return send_from_directory('static', 'img/default-avatar.png')
    except Exception as e:
        current_app.logger.error(f"Error serving uploaded file {filename}: {str(e)}")
        return send_from_directory('static', 'img/default-avatar.png')

# Configure database connection pooling
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 30,
    'max_overflow': 40,
    'pool_timeout': 30,
    'echo': False,
    'connect_args': {'check_same_thread': False},  # For SQLite concurrent access
    'execution_options': {'isolation_level': 'SERIALIZABLE'}
}

# Set secret key
app.config['SECRET_KEY'] = 'o3#7n4@43y0ry5j4@2me+nn@vbu32rr=w7mz)1yzz7egy^)qn*'  # Secret key for secure sessions

# Initialize Fraud Detection Service will be done after models are defined

# Initialize CSRF protection
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = app.config['SECRET_KEY']
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour CSRF token expiry
csrf = CSRFProtect(app)

# Session configuration
# Session configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, 'flask_session')
app.config['SESSION_FILE_THRESHOLD'] = 500  # Maximum number of sessions stored on disk
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Create session directory if it doesn't exist
if not os.path.exists(app.config['SESSION_FILE_DIR']):
    os.makedirs(app.config['SESSION_FILE_DIR'])

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'dipendra998405@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'qrjz depb zcsz zcba'  # Replace with your app password
app.config['MAIL_DEFAULT_SENDER'] = 'dipendra998405@gmail.com'  # Replace with your email

# Initialize CSRF protection
csrf = CSRFProtect(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fuetime.db'  # Database URI with absolute path
print(f"Database path: {app.config['SQLALCHEMY_DATABASE_URI']}")  # Debug print
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable SQLALCHEMY_TRACK_MODIFICATIONS

# Performance optimizations
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 20,
    'max_overflow': 30,
    'pool_timeout': 10
}

# Configure caching
cache = Cache(app, config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300
})

# Initialize database with optimized session options
# Database configuration was moved to extensions.py

with app.app_context():
    db.session.configure(expire_on_commit=False)

# Initialize login manager
# LoginManager initialization moved to extensions.py
# Set login view
login_manager.login_view = 'login'

# Configure SocketIO
socketio.cors_allowed_origins = "*"
socketio.async_mode = 'threading'
socketio.ping_timeout = 5
socketio.ping_interval = 25
socketio.max_http_buffer_size = 10e6

# Enable debug mode and detailed error reporting
app.debug = True
app.config['PROPAGATE_EXCEPTIONS'] = True

# Additional configuration
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')  # Upload folder path
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit for CSRF tokens
app.config['WTF_CSRF_SSL_STRICT'] = False  # Disable SSL-only for CSRF tokens
# Initialize Flask-Session
from flask_session import Session as FlaskSession
FlaskSession(app)

# Cache already configured above

# Configure upload settings
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

# File upload settings
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folders exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
chat_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'chat')
if not os.path.exists(chat_upload_dir):
    os.makedirs(chat_upload_dir)

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465  # Use SSL port
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = 'dipendra998405@gmail.com'  # App email
app.config['MAIL_PASSWORD'] = 'qrjz depb zcsz zcba'  # App-specific password
app.config['MAIL_DEFAULT_SENDER'] = 'dipendra998405@gmail.com'

# Initialize extensions
csrf = CSRFProtect(app)
# Babel initialization moved to extensions.py

# Initialize serializer for password reset tokens
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Admin routes for fraud detection
@app.route('/admin/fraud-alerts')
@login_required
@admin_required
@cache.cached(timeout=60)  # Cache for 1 minute
def admin_fraud_alerts():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Use a single query with joins to get all data
    alerts = db.session.query(
        FraudAlert,
        User
    ).join(
        User, FraudAlert.user_id == User.id
    ).filter(
        FraudAlert.is_resolved == False
    ).order_by(
        FraudAlert.created_at.desc()
    ).all()
    
    # Count risks from the fetched data
    high_risk = sum(1 for alert, _ in alerts if alert.severity == 'high')
    medium_risk = sum(1 for alert, _ in alerts if alert.severity == 'medium')
    low_risk = sum(1 for alert, _ in alerts if alert.severity == 'low')
    
    return render_template('admin/fraud_alerts.html',
                           high_risk=high_risk,
                           medium_risk=medium_risk,
                           low_risk=low_risk,
                           alerts=[alert for alert, _ in alerts])

@app.route('/admin/fraud-alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def admin_resolve_alert(alert_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    alert = FraudAlert.query.get_or_404(alert_id)
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    
    flash('Alert has been marked as resolved.', 'success')
    return redirect(url_for('admin_fraud_alerts'))



# Razorpay configuration
RAZORPAY_KEY_ID = 'rzp_live_NJ0w2ONEt4sOwV'
RAZORPAY_KEY_SECRET = 't8s0UF9M35FPHMCJob2G9mwH'

# Import required modules
import razorpay
import requests
from requests.adapters import HTTPAdapter

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
from urllib3.util.retry import Retry
import ssl
from functools import partial

# Custom SSL context factory to prevent recursion with gevent
def create_custom_ssl_context():
    context = ssl.create_default_context()
    # Set minimum protocol version to TLS 1.2
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    return context

# Custom HTTP adapter with our SSL context
class CustomSSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        # Create a custom SSL context for the pool manager
        context = create_custom_ssl_context()
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        # Create a custom SSL context for the proxy manager
        context = create_custom_ssl_context()
        kwargs['ssl_context'] = context
        return super().proxy_manager_for(*args, **kwargs)

# Initialize Razorpay client with custom session
def create_razorpay_client():
    print("\n=== Creating Razorpay client with custom session ===")
    print(f"Using Key ID: {RAZORPAY_KEY_ID}")
    print(f"Key Secret: {'*' * len(RAZORPAY_KEY_SECRET) if RAZORPAY_KEY_SECRET else 'Not set'}")
    
    try:
        # Create a custom session with retry logic
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        # Mount our custom SSL adapter
        adapter = CustomSSLAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        
        # Initialize Razorpay client with the custom session
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        client.session = session  # Override the default session
        
        print("Razorpay client with custom session and SSL context created successfully")
        return client
        
    except Exception as e:
        print(f"ERROR: Failed to create Razorpay client: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

# Initialize the client
razorpay_client = create_razorpay_client()

# Configure supported languages
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_LANGUAGES'] = ['en', 'hi', 'mr', 'gu', 'ta', 'te']

def get_locale():
    # Try to get the language from the session
    if 'language' in session:
        return session['language']
    # Otherwise, try to guess the language from the user accept header
    return request.accept_languages.best_match(app.config['BABEL_LANGUAGES'])

babel.init_app(app, locale_selector=get_locale)

# Custom Jinja2 filters
def mask_email(email):
    if not email:
        return ''
    parts = email.split('@')
    if len(parts) != 2:
        return email
    username, domain = parts
    if len(username) <= 3:
        masked_username = '*' * len(username)
    else:
        masked_username = '***' + username[3:]
    return f'{masked_username}@{domain}'

def mask_phone(phone):
    if not phone:
        return ''
    if len(phone) <= 3:
        return '*' * len(phone)
    return '***' + phone[3:]

def format_experience(exp):
    if not exp:
        return 'Not specified'
    if exp == '10+':
        return '10+ years'
    return f'{exp} years'

# Register custom filters
from filters import avg
app.jinja_env.filters['mask_email'] = mask_email
app.jinja_env.filters['mask_phone'] = mask_phone
app.jinja_env.filters['format_experience'] = format_experience
app.jinja_env.filters['avg'] = avg
app.jinja_env.filters['avg'] = avg

# Make sure the translation function is available in templates
app.jinja_env.globals['_'] = _

def csrf_exempt(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs)
    return csrf.exempt(wrapped)

# Initialize Fraud Detection Service
from services.fraud_detection import FraudDetectionService
fraud_detection = FraudDetectionService()

# Models have been moved to the models/ directory
# - HelpRequest: models/help_request.py
# - UserInteraction: models/user_interaction.py
# - Message: models/message.py
# - ContactRequest: models/contact_request.py
# - Transaction: models/transaction.py

# Helper Functions
def generate_username(full_name):
    # Convert full name to lowercase and replace spaces with underscores
    base_username = full_name.lower().replace(' ', '_')
    
    # Remove any special characters
    base_username = re.sub(r'[^a-z0-9_]', '', base_username)
    
    # If username exists, add a random number
    username = base_username
    from models.user import User

    while User.query.filter_by(username=username).first():
        username = f"{base_username}_{random.randint(1, 9999)}"
    
    return username

def generate_otp():
    # Generate a 6-digit OTP
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(user_email, otp):
    # Email configuration
    sender_email = app.config.get('MAIL_USERNAME')
    sender_password = app.config.get('MAIL_PASSWORD')
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = 'Your OTP for Fuetime Registration'
    
    # Email body
    body = f'''Hello,

Your OTP for Fuetime registration is: {otp}

This OTP will expire in 10 minutes.

Best regards,
Fuetime Team'''
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Create SMTP session
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(sender_email, user_email, text)
        server.quit()
        return True
    except Exception as e:
        print(f'Error sending OTP email: {str(e)}')
        return False

def send_reset_email(user_email, reset_url):
    msg = MIMEMultipart()
    msg['From'] = app.config['MAIL_DEFAULT_SENDER']
    msg['To'] = user_email
    msg['Subject'] = 'Password Reset Request - Fuetime'
    
    body = f'''Hello,

You have requested to reset your password for your Fuetime account.

To reset your password, please click on the following link:
{reset_url}

This link will expire in 1 hour for security reasons.

If you did not make this request, please ignore this email and your password will remain unchanged.

Best regards,
The Fuetime Team
'''
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Create server connection with SSL
        server = smtplib.SMTP_SSL(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.ehlo()  # Identify ourselves to the server
        
        # Attempt login
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        
        # Send email
        text = msg.as_string()
        server.sendmail(app.config['MAIL_DEFAULT_SENDER'], user_email, text)
        
        # Log success
        app.logger.info(f'Password reset email sent successfully to {user_email}')
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        app.logger.error(f'SMTP Authentication Error: {str(e)}. Please check email credentials.')
        return False
    except smtplib.SMTPException as e:
        app.logger.error(f'SMTP Error: {str(e)}')
        return False
    except Exception as e:
        app.logger.error(f'Unexpected error sending email to {user_email}: {str(e)}')
        return False
    finally:
        try:
            server.quit()
        except:
            pass

# Wallet Routes
@app.route('/wallet', methods=['GET', 'POST'])
@login_required
def wallet():
    try:
        # Initialize transactions as an empty list in case of any errors
        transactions = []
        
        try:
            # Get user's wallet transactions in descending order (newest first)
            transactions = Transaction.query.filter_by(
                user_id=current_user.id
            ).order_by(Transaction.created_at.desc()).limit(50).all()
            
            # Log successful transaction retrieval
            app.logger.info(f'Successfully retrieved {len(transactions)} transactions for user {current_user.id}')
            
        except Exception as db_error:
            app.logger.error(f'Error fetching transactions: {str(db_error)}')
            flash('Error loading transaction history. Please try again.', 'warning')
        
        # Ensure we have a valid wallet balance
        wallet_balance = getattr(current_user, 'wallet_balance', 0.0)
        
        return render_template('wallet.html', 
                           transactions=transactions,
                           wallet_balance=wallet_balance)
    except Exception as e:
        app.logger.error(f'Error in wallet route: {str(e)}')
        flash('An error occurred while accessing your wallet. Please try again.', 'error')
        return render_template('wallet.html', 
                           transactions=[],
                           wallet_balance=getattr(current_user, 'wallet_balance', 0.0))
        return redirect(url_for('account'))

@app.route('/create-recharge-order', methods=['POST'])
@login_required
@csrf_exempt
def create_recharge_order():
    print("\n=== DEBUG: Entering create_recharge_order ===")
    
    # Check if Razorpay client is initialized
    if not razorpay_client:
        error_msg = "Payment service is currently unavailable. Please try again later."
        print(f"ERROR: {error_msg}")
        return jsonify({
            'success': False,
            'message': error_msg,
            'error': 'Razorpay client not initialized'
        }), 503
    
    # Simple order data without complex options that might cause issues
    try:
        print(f"DEBUG: Request form data: {request.form}")
        amount = float(request.form.get('amount', 0))
        print(f"DEBUG: Amount received: {amount}")
        
        if amount < 20 or amount > 500:
            print("DEBUG: Amount validation failed")
            return jsonify({
                'success': False, 
                'message': 'Amount must be between ₹20 and ₹500',
                'error': 'invalid_amount'
            })

        # Amount should be in paise
        amount_in_paise = int(amount * 100)
        print(f"DEBUG: Amount in paise: {amount_in_paise}")
        
        receipt_id = f'recharge_{current_user.id}_{int(datetime.now().timestamp())}'
        print(f"DEBUG: Creating order with receipt ID: {receipt_id}")
        
        # Simplified order data
        order_data = {
            'amount': amount_in_paise,
            'currency': 'INR',
            'receipt': receipt_id,
            'payment_capture': 1  # Auto-capture payment
        }
        
        print(f"DEBUG: Order data: {order_data}")
        
        # Create the order
        try:
            print("DEBUG: Creating Razorpay order...")
            razorpay_order = razorpay_client.order.create(data=order_data)
            print(f"DEBUG: Order created successfully")
            
            response = {
                'success': True,
                'order_id': razorpay_order['id'],
                'amount': amount_in_paise,
                'currency': 'INR',
                'key_id': RAZORPAY_KEY_ID,
                'user_email': current_user.email,
                'user_phone': current_user.phone,
                'user_name': current_user.full_name
            }
            
            print(f"DEBUG: Order creation successful")
            return jsonify(response)
            
        except Exception as order_error:
            import traceback
            error_trace = traceback.format_exc()
            error_msg = str(order_error)
            
            # Extract more details if available
            if hasattr(order_error, 'error') and isinstance(order_error.error, dict):
                error_msg = order_error.error.get('description', error_msg)
                
            print(f"ERROR in order creation: {error_msg}")
            print(f"Traceback: {error_trace}")
                
            return jsonify({
                'success': False,
                'message': 'Failed to create payment order',
                'error': error_msg,
                'error_type': 'order_creation_failed'
            })
        
    except ValueError as ve:
        error_msg = f"Invalid amount value: {str(ve)}"
        print(f"ERROR: {error_msg}")
        return jsonify({
            'success': False,
            'message': 'Invalid amount specified',
            'error': str(ve),
            'error_type': 'invalid_amount'
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = f"Unexpected error: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"Traceback: {error_trace}")
        
        return jsonify({
            'success': False,
            
            'message': 'An unexpected error occurred',
            'error': str(e),
            'error_type': 'unexpected_error'
        })

@app.route('/verify-recharge-payment', methods=['POST'])
@login_required
@csrf_exempt
def verify_recharge_payment():
    db_session = db.session
    try:
        # Get payment verification data
        payment_id = request.form.get('razorpay_payment_id')
        order_id = request.form.get('razorpay_order_id')
        signature = request.form.get('razorpay_signature')
        
        if not all([payment_id, order_id, signature]):
            app.logger.error('Missing payment verification data')
            return jsonify({
                'success': False,
                'message': 'Missing payment verification data'
            }), 400
        
        # Verify payment signature
        params_dict = {
            'razorpay_payment_id': payment_id,
            'razorpay_order_id': order_id,
            'razorpay_signature': signature
        }
        
        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            app.logger.error(f'Payment signature verification failed: {str(e)}')
            return jsonify({
                'success': False,
                'message': 'Invalid payment signature'
            }), 400
        
        # Get payment details
        try:
            payment = razorpay_client.payment.fetch(payment_id)
            amount = float(payment['amount']) / 100  # Convert paise to rupees
        except Exception as e:
            app.logger.error(f'Failed to fetch payment details: {str(e)}')
            return jsonify({
                'success': False,
                'message': 'Failed to fetch payment details'
            }), 400

        # Start a new transaction
        db_session.begin_nested()
        
        try:
            # Get user with row-level lock to prevent race conditions
            user = User.query.with_for_update().get(current_user.id)
            if not user:
                raise ValueError('User not found')
                
            # Get current balance
            old_balance = float(user.wallet_balance or 0)
            
            # Calculate new balance with proper float handling
            amount = round(float(amount), 2)
            new_balance = round(old_balance + amount, 2)
            
            # Update user's balance
            user.wallet_balance = new_balance
            
            # Create transaction record
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                description=f'Wallet recharge via Razorpay (ID: {payment_id})'
            )
            
            # Add transaction to session
            db_session.add(transaction)
            db_session.add(user)
            
            # Commit the transaction
            db_session.commit()
            
            # Update the current_user object with the latest balance
            current_user.wallet_balance = new_balance
            
            # Log the successful transaction
            app.logger.info(f'Successfully updated wallet balance. User: {user.id}, Amount: {amount}, New Balance: {new_balance}')
            
            # Return success response with balance information
            return jsonify({
                'success': True,
                'message': 'Payment successful',
                'amount': amount,
                'old_balance': old_balance,
                'new_balance': new_balance,
                'transaction_id': str(transaction.id),
                'timestamp': transaction.created_at.isoformat() if transaction.created_at else datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            db_session.rollback()
            app.logger.error(f'Error processing payment: {str(e)}', exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Failed to process payment: {str(e)}'
            }), 500
            
    except Exception as e:
        db_session.rollback()
        app.logger.error(f'Unexpected error in verify_recharge_payment: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred. Please try again.'
        }), 500
        
    finally:
        # Make sure to close the session
        db_session.close()

@app.route('/add-wallet-balance', methods=['POST'])
@login_required
def add_wallet_balance():
    db_session = db.session
    try:
        # Start a new transaction
        db_session.rollback()
        
        # Validate amount
        try:
            amount = float(request.form.get('amount', 0))
        except (TypeError, ValueError) as e:
            app.logger.error(f'Invalid amount format: {str(e)}')
            return jsonify({
                'success': False,
                'message': 'Invalid amount format'
            })
            
        if amount < 20 or amount > 500:
            app.logger.warning(f'Invalid amount value: {amount}')
            return jsonify({
                'success': False,
                'message': 'Amount must be between ₹20 and ₹500'
            })

        # Start a new transaction with fresh session
        with db_session.begin_nested():
            # Get fresh user object with row-level lock to prevent race conditions
            user = User.query.with_for_update().get(current_user.id)
            if not user:
                app.logger.error(f'User not found: {current_user.id}')
                return jsonify({
                    'success': False,
                    'message': 'User not found'
                })

            # Handle None wallet_balance case and ensure it's a valid number
            current_balance = float(user.wallet_balance) if user.wallet_balance is not None else 0.0
            new_balance = current_balance + amount
            
            # Update wallet balance
            user.wallet_balance = new_balance
            
            # Create transaction record
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                description=f'Wallet recharge of ₹{amount:.2f}',
                timestamp=datetime.utcnow()
            )
            
            # Add transaction to session
            db_session.add(transaction)
            
            # Commit the nested transaction
            db_session.commit()
        
        # Refresh the user object to get the latest state
        db_session.refresh(user)
        
        # Update the current_user object in the session
        current_user.wallet_balance = float(user.wallet_balance) if user.wallet_balance is not None else 0.0
        
        # Force update the user session to ensure the wallet balance is persisted
        login_user(user, remember=True)
        
        # Log the successful update with detailed information
        app.logger.info(f'''
            Wallet Update - User: {user.id}
            Added: ₹{amount:.2f}
            New Balance (DB): ₹{user.wallet_balance:.2f}
            Session Balance: ₹{current_user.wallet_balance:.2f}
            Is Authenticated: {current_user.is_authenticated}
            User ID in session: {current_user.get_id()}
        ''')
        
        return jsonify({
            'success': True,
            'message': f'Successfully added ₹{amount:.2f} to your wallet',
            'new_balance': float(user.wallet_balance) if user.wallet_balance is not None else 0.0
        })
            
    except Exception as e:
        if 'db_session' in locals():
            db_session.rollback()
        app.logger.error(f'Unexpected error in add_wallet_balance: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred. Please try again later.'
        })
    finally:
        # Ensure session is closed
        if 'db_session' in locals():
            db_session.close()

# Routes
@app.route('/search')
def search():
    query = request.args.get('query', '').strip()
    category = request.args.get('category', '').strip()
    location = request.args.get('location', '').strip()

    app.logger.info(f'Search request - query: {query}, category: {category}, location: {location}')

    if not any([query, category, location]):
        app.logger.info('No search parameters provided')
        return render_template('search.html', users=[])

    # First find all matching users regardless of active status
    users_query = User.query

    if query:
        users_query = users_query.filter(
            db.or_(
                User.full_name.ilike(f'%{query}%'),
                User.skills.ilike(f'%{query}%'),
                User.work.ilike(f'%{query}%')
            )
        )
        app.logger.info(f'Added query filter: {query}')
    
    if category:
        users_query = users_query.filter(User.categories.ilike(f'%{category}%'))
        app.logger.info(f'Added category filter: {category}')
    
    if location:
        users_query = users_query.filter(User.current_location.ilike(f'%{location}%'))
        app.logger.info(f'Added location filter: {location}')

    # Log the SQL query being executed
    app.logger.info(f'SQL Query: {users_query}')

    # Get all matching users
    all_matching_users = users_query.all()
    app.logger.info(f'Found {len(all_matching_users)} total matching users')

    # Filter active users
    active_users = [user for user in all_matching_users if user.active]
    inactive_users = [user for user in all_matching_users if not user.active]

    app.logger.info(f'Active users: {len(active_users)}, Inactive users: {len(inactive_users)}')

    return render_template('search_results.html', 
                         users=active_users, 
                         inactive_users=inactive_users,
                         query=query)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Worker registration route"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    current_date = datetime.utcnow().date()
    
    if request.method == 'POST':
        try:
            # Force user_type to 'worker' for this route
            user_type = 'worker'
            
            # Debug logging
            print("\n--- Registration Request ---")
            print("Form Data:")
            for key, value in request.form.items():
                print(f"{key}: {value}")
            print(f"User type from form: {user_type}")
            
            # Initialize form data
            form_data = request.form.to_dict()
            error_msg = None
            
            # Debug: Print raw form data
            print("\nRaw form data:", dict(request.form))
        
            # Collect form data with error handling
            required_fields = ['email', 'phone', 'password', 'full_name', 'live_location']
            
            # Process required fields
            for field in required_fields:
                value = request.form.get(field, '').strip()
                if not value:
                    error_msg = f'{field.replace("_", " ").title()} is required'
                    print(f"Validation error: {error_msg}")
                    return render_template('register.html', 
                                       form_data=form_data, 
                                       error=error_msg,
                                       current_date=current_date.strftime('%Y-%m-%d'))
                form_data[field] = value
            
            # Additional validation for worker registration
            if user_type == 'worker':
                if not request.form.get('date_of_birth'):
                    error_msg = 'Date of birth is required for worker registration'
                    print(f"Validation error: {error_msg}")
                    return render_template('register.html', 
                                       form_data=form_data, 
                                       error=error_msg,
                                       current_date=current_date.strftime('%Y-%m-%d'))
                # Add date_of_birth to form_data for workers
                form_data['date_of_birth'] = request.form['date_of_birth'].strip()
            else:
                # Clear date_of_birth for clients
                form_data['date_of_birth'] = ''
                
            print("Form data after validation:", form_data)
            
            # Additional form data collection
            optional_fields = [
                'work', 'experience', 'education', 'live_location', 
                'current_location', 'payment_type', 'payment_charge', 
                'skills', 'work_experience'
            ]
            for field in optional_fields:
                form_data[field] = request.form.get(field, '').strip()
            
            # If there's an error with required fields, return early
            if error_msg:
                print(f"Validation Error: {error_msg}")
                return render_template('register.html', 
                                   form_data=form_data, 
                                   error=error_msg,
                                   current_date=current_date.strftime('%Y-%m-%d'))
            
            # Debug prints
            print("\n--- Registration Validation Complete ---")
            print(f"User type: {user_type}")
            print(f"Form data: {form_data}")
            print(f"Date of birth: {form_data.get('date_of_birth', 'Not provided')}")
            
            # Debug: Print session info
            print("\nSession info:")
            print(f"User authenticated: {current_user.is_authenticated}")
            if current_user.is_authenticated:
                print(f"Current user: {current_user.email}")

            # Initialize worker-specific fields
            dob = None
            age = None
            live_location = None

            # Validate required fields based on user type
            required_fields = ['email', 'phone', 'password', 'full_name']
            
            # Only require date_of_birth and live_location for workers
            if user_type == 'worker':
                required_fields.extend(['date_of_birth', 'live_location'])
            
            # Check required fields
            for field in required_fields:
                if field not in form_data or not form_data[field]:
                    print(f"Missing required field: {field}")
                    error_msg = f'{field.replace("_", " ").title()} is required'
                    if field == 'date_of_birth':
                        error_msg = 'Date of birth is required for worker registration'
                    return render_template('register.html', 
                                       form_data=form_data, 
                                       error=error_msg,
                                       current_date=current_date.strftime('%Y-%m-%d'))
            
            # Validate email format
            if not re.match(r"[^@]+@[^@]+\.[^@]+", form_data['email']):
                print("Invalid email format")
                error_msg = 'Invalid email format'
                return render_template('register.html', form_data=form_data, error=error_msg)
            
            # Validate phone format (assuming 10 digits)
            if not re.match(r'^\d{10}$', form_data['phone']):
                print("Invalid phone format")
                error_msg = 'Invalid phone number format (must be 10 digits)'
                return render_template('register.html', form_data=form_data, error=error_msg)
            
            # Process worker-specific fields
            try:
                # Process date of birth (required for workers)
                if not form_data.get('date_of_birth'):
                    error_msg = 'Date of birth is required for worker registration'
                    return render_template('register.html', 
                                       form_data=form_data, 
                                       error=error_msg,
                                       current_date=current_date.strftime('%Y-%m-%d'))
                
                dob = datetime.strptime(form_data['date_of_birth'], '%Y-%m-%d').date()
                age = int((datetime.now().date() - dob).days / 365.25)
                
                # Validate age
                if age < 18:
                    error_msg = 'You must be at least 18 years old to register as a worker'
                    return render_template('register.html', 
                                       form_data=form_data, 
                                       error=error_msg,
                                       current_date=current_date.strftime('%Y-%m-%d'))
                
                # Set live location
                live_location = form_data.get('live_location')
                if not live_location:
                    error_msg = 'Live location is required for worker registration'
                    return render_template('register.html',
                                       form_data=form_data,
                                       error=error_msg,
                                       current_date=current_date.strftime('%Y-%m-%d'))
            except ValueError as e:
                print(f"Error parsing date: {e}")
                error_msg = 'Invalid date of birth format. Please use YYYY-MM-DD'
                return render_template('register.html', 
                                   form_data=form_data, 
                                   error=error_msg,
                                   current_date=current_date.strftime('%Y-%m-%d'))
            
            # Generate username from full name
            username = generate_username(form_data['full_name'])
            print(f"Generated username: {username}")

            # Generate OTP
            email_otp = generate_otp()

            # Check if user already exists
            if User.query.filter_by(email=form_data['email']).first():
                print(f"User with email {form_data['email']} already exists")
                flash('Email already registered', 'danger')
                return redirect(url_for('register'))
            
            if User.query.filter_by(phone=form_data['phone']).first():
                print(f"User with phone {form_data['phone']} already exists")
                flash('Phone number already registered', 'danger')
                return redirect(url_for('register'))
            
            # Handle profile photo upload
            if 'photo' not in request.files or not request.files['photo'].filename:
                error_msg = 'Profile picture is required'
                return render_template('register.html', form_data=form_data, error=error_msg)

            file = request.files['photo']
            try:
                # Check file size (max 5MB)
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                if file_size > 5 * 1024 * 1024:
                    error_msg = 'File is too large. Maximum file size is 5MB.'
                    return render_template('register.html', form_data=form_data, error=error_msg)

                # Check file type
                if not allowed_file(file.filename):
                    error_msg = 'Invalid file type. Please upload a JPEG, PNG, or GIF image.'
                    return render_template('register.html', form_data=form_data, error=error_msg)

                # Secure the filename and save it
                filename = secure_filename(file.filename)
                # Add timestamp to filename to prevent caching issues
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                
                # Ensure the uploads directory exists
                uploads_dir = os.path.join(app.static_folder, 'uploads')
                if not os.path.exists(uploads_dir):
                    os.makedirs(uploads_dir)
                
                # Save the file
                file_path = os.path.join(uploads_dir, filename)
                file.save(file_path)
                
                # Extensive logging
                print("\n--- Photo Upload Details ---")
                print(f"Filename: {filename}")
                print(f"Full Path: {file_path}")
                print(f"File Size: {file_size} bytes")
                print(f"Photo Exists: {os.path.exists(file_path)}")
                
            except Exception as photo_err:
                print(f"Error processing photo: {photo_err}")
                error_msg = 'An error occurred while uploading the photo'
                return render_template('register.html', form_data=form_data, error=error_msg)
            
            # Generate username
            username = generate_username(form_data['full_name'])
            print(f"Generated username: {username}")
            
            # Create new user with unverified status
            try:
                dob = datetime.strptime(form_data['date_of_birth'], '%Y-%m-%d').date()
                age = int((datetime.now().date() - dob).days / 365.25)
                
                # Generate OTP
                email_otp = generate_otp()
                
                try:
                    # Create user object with common fields
                    user_data = {
                        'user_type': 'client' if user_type == 'client' else 'worker',  # Ensure correct user type
                        'email': form_data['email'],
                        'phone': form_data['phone'],
                        'full_name': form_data['full_name'],
                        'username': username,
                        'current_location': form_data['current_location'],
                        'photo': filename,
                        'active': False,  # User starts as inactive until verified
                        'authenticated': False,  # User starts as unauthenticated until verified
                        'email_verified': False,
                        'email_otp': email_otp,
                        'otp_expiry': datetime.utcnow() + timedelta(minutes=10),  # OTP expires in 10 minutes
                        'date_of_birth': dob,  # dob is None for business clients
                        'age': age,  # age is None for business clients
                        'live_location': live_location,  # live_location is None for business clients
                        'payment_type': form_data.get('payment_type', ''),  # Add payment_type
                        'payment_charge': float(form_data.get('payment_charge', 0)) if form_data.get('payment_charge') else None  # Add payment_charge
                    }

                    # Create user instance
                    user = User(**user_data)
                    
                    # Add worker-specific fields only if user type is worker
                    if user_type == 'worker':
                        worker_fields = [
                            'work', 'experience', 'skills', 'mother_name', 
                            'father_name', 'education', 'categories', 'bio',
                            'work_experience'
                        ]
                        for field in worker_fields:
                            if field in form_data and form_data[field]:
                                setattr(user, field, form_data[field].strip())
                                print(f"Set {field} to: {form_data[field].strip()}")
                        
                        # Debug: Print work_experience value
                        print(f"Work experience being saved: {form_data.get('work_experience', 'Not provided')}")
                    
                    # Set password
                    print("Setting password")
                    if 'password' not in form_data or not form_data['password']:
                        raise ValueError("Password is required")
                    user.set_password(form_data['password'])
                    
                    print("Adding user to database")
                    db.session.add(user)
                    db.session.commit()
                    print("User added successfully")
                except Exception as e:
                    print(f"Error in user creation: {str(e)}")
                    db.session.rollback()
                    error_msg = 'Error creating user. Please try again.'
                    return render_template('register.html', form_data=form_data, error=error_msg)
                
                # Send OTP email
                if send_otp_email(user.email, email_otp):
                    # Store user_id and user_type in session for verification
                    session['pending_verification_id'] = user.id
                    session['user_type'] = user_type  # Store user_type in session
                    flash('Please check your email for the OTP to complete registration.', 'info')
                    return redirect(url_for('verify_otp'))
                else:
                    # If email fails, delete the user and show error
                    db.session.delete(user)
                    db.session.commit()
                    flash('Error sending verification email. Please try again.', 'danger')
                    return redirect(url_for('register'))
                
            except Exception as e:
                print(f"Error creating user: {str(e)}")
                print(f"Error type: {type(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                db.session.rollback()
                flash('Error creating account. Please try again.', 'danger')
                return redirect(url_for('register'))
                
        except Exception as e:
            print(f"Error in registration: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()  # Print full traceback to console
            
            # Log more details about the form data
            print("Form Data:")
            for key, value in form_data.items():
                print(f"{key}: {value}")
            
            flash(f'Error during registration: {str(e)}', 'danger')
            return render_template('register.html', form_data=form_data, error=str(e))
    
    return render_template('register.html', form_data={})


@app.route('/check-email', methods=['POST'])
def check_email():
    """Check if email is already registered"""
    email = request.form.get('email')
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'Email already registered'}), 409
    
    return jsonify({'message': 'Email available'}), 200

@app.route('/register/client', methods=['GET', 'POST'])
def register_client():
    """Client registration route"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        form_data = request.form.to_dict()
        print("\n--- Client Registration Attempt ---")
        print(f"Form data: {form_data}")
        
        try:
            # Required fields for client registration
            required_fields = ['email', 'phone', 'password', 'full_name', 'current_location']
            
            # Validate required fields
            for field in required_fields:
                field_value = form_data.get(field, '').strip()
                if not field_value:
                    error_msg = f'{field.replace("_", " ").title()} is required'
                    print(f"Validation error: {error_msg}")
                    return render_template('register_client.html', 
                                       form_data=form_data, 
                                       error=error_msg)
            
            # Validate email format
            email = form_data['email'].strip()
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                error_msg = 'Invalid email format'
                print(f"Validation error: {error_msg}")
                return render_template('register_client.html', 
                                   form_data=form_data, 
                                   error=error_msg)

            # Validate phone number (Indian format)
            phone = form_data['phone'].strip()
            # Remove any leading zeros
            phone = phone.lstrip('0')
            if not re.match(r"^[6-9][0-9]{9}$", phone):
                error_msg = 'Please enter a valid 10-digit Indian mobile number starting with 6-9'
                print(f"Validation error: {error_msg}")
                return render_template('register_client.html',
                                   form_data=form_data,
                                   error=error_msg)
            # Update the phone number in form_data after removing leading zeros
            form_data['phone'] = phone
            
            # Validate password strength
            password = form_data['password']
            if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$", password):
                error_msg = 'Password must be at least 8 characters long and contain uppercase, lowercase, number and special character'
                print(f"Validation error: {error_msg}")
                return render_template('register_client.html',
                                   form_data=form_data,
                                   error=error_msg)
            
            # Check if passwords match
            if password != request.form.get('confirm_password', ''):
                error_msg = 'Passwords do not match'
                print(f"Validation error: {error_msg}")
                return render_template('register_client.html', 
                                   form_data=form_data, 
                                   error=error_msg)
            
            # Check if email already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                error_msg = 'Email already registered. Please use a different email or login.'
                print(f"Registration error: {error_msg}")
                return render_template('register_client.html', 
                                   form_data=form_data, 
                                   error=error_msg)

            # Check if phone already exists
            existing_phone = User.query.filter_by(phone=phone).first()
            if existing_phone:
                error_msg = 'Phone number already registered. Please use a different number.'
                print(f"Registration error: {error_msg}")
                return render_template('register_client.html',
                                   form_data=form_data,
                                   error=error_msg)
            
            # Ensure upload folders are configured
            if 'UPLOAD_FOLDER' not in app.config or 'PROFILE_PICS_FOLDER' not in app.config:
                configure_upload_folders()
                
            # Debug: Print current upload configuration
            print("\n=== DEBUG: UPLOAD CONFIG ===")
            print(f"UPLOAD_FOLDER: {app.config.get('UPLOAD_FOLDER')}")
            print(f"PROFILE_PICS_FOLDER: {app.config.get('PROFILE_PICS_FOLDER')}")
            print(f"Files in request: {list(request.files.keys())}")
            
            # No profile picture for client registration
            photo_filename = None

            try:
                # Create new user with unverified status
                user = User(
                    user_type='client',
                    email=email,
                    phone=phone,
                    full_name=form_data['full_name'],
                    username=generate_username(form_data['full_name']),
                    current_location=form_data['current_location'],
                    active=False,
                    authenticated=False,
                    email_verified=False,
                    photo=photo_filename
                )

                # Set password
                user.set_password(password)

                # Generate OTP
                otp = generate_otp()
                user.email_otp = otp
                user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)

                # Add user to database
                db.session.add(user)
                db.session.commit()

                # Store user ID in session for verification
                session['pending_verification_id'] = user.id
                session['user_type'] = 'client'

                # Send OTP email
                send_otp_email(email, otp)
                flash('Please check your email for the verification code.', 'info')
                return redirect(url_for('verify_business_otp'))

            except Exception as e:
                db.session.rollback()
                print(f"Error in registration: {str(e)}")
                print(f"Error type: {type(e)}")
                print(f"Traceback: {traceback.format_exc()}")
                error_msg = 'Error during registration. Please try again.'
                return render_template('register_client.html',
                                   form_data=form_data,
                                   error=error_msg)
            

                
        except Exception as e:
            db.session.rollback()
            print(f"\n--- Registration Error ---")
            print(f"Error type: {type(e).__name__}")
            print(f"Error details: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            
            error_msg = 'An error occurred during registration. Please try again.'
            return render_template('register_client.html',
                               form_data=form_data,
                               error=error_msg)
    
    # For GET requests
    return render_template('register_client.html', form_data={})

@app.route('/debug/session')
def debug_session():
    """Debug endpoint to check session and authentication status"""
    debug_info = {
        'is_authenticated': current_user.is_authenticated,
        'user_id': current_user.get_id(),
        'session': dict(session),
        'cookies': dict(request.cookies),
        'user_agent': request.user_agent.string,
        'remote_addr': request.remote_addr,
    }
    return jsonify(debug_info), 200, {'Content-Type': 'application/json'}

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with enhanced session management"""
    print("\n" + "="*50)
    print(f"[LOGIN] Route accessed. Method: {request.method}")
    print(f"[LOGIN] Current user authenticated: {current_user.is_authenticated}")
    print(f"[LOGIN] Session ID: {session.sid if 'sid' in dir(session) else 'N/A'}")
    print(f"[LOGIN] Session data: {dict(session)}")
    print(f"[LOGIN] Request cookies: {request.cookies}")
    
    # Check if already logged in
    if current_user.is_authenticated:
        print("[LOGIN] User already authenticated, redirecting to index")
        return redirect(url_for('main.index'))
    
    # Get next page from query parameters or form
    next_page = request.args.get('next') or request.form.get('next') or url_for('main.index')
    print(f"[LOGIN] Next page: {next_page}")
    
    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            remember = request.form.get('remember', 'false').lower() == 'true'
            
            print(f"[LOGIN] Attempting login for email: {email}")
            print(f"[LOGIN] Remember me: {remember}")
            
            user = User.query.filter_by(email=email).first()
            print(f"[LOGIN] User found: {user is not None}")
            
            if user:
                print(f"[LOGIN] Checking password for user: {user.email}")
                if user.check_password(password):
                    print("[LOGIN] Password check successful")
                    
                    # Check if email is verified (skip for admin users)
                    if not user.email_verified:
                        if not user.is_admin:  # Skip OTP verification for admin users
                            print("[LOGIN] User email not verified")
                            session['pending_verification_id'] = user.id
                            session['next_page'] = next_page
                            flash('Please verify your email to continue.', 'warning')
                            return redirect(url_for('verify_otp'))
                        else:
                            # Mark admin email as verified automatically
                            user.email_verified = True
                            db.session.commit()
                    
                    # Update user status
                    user.authenticated = True
                    user.is_online = True
                    user.update_last_seen()
                    
                    try:
                        print("[LOGIN] Committing user status update")
                        db.session.commit()
                        print("[LOGIN] User status update committed")
                    except Exception as e:
                        print(f"[ERROR] Updating user status: {str(e)}")
                        db.session.rollback()
                        raise
                    
                    # Log the user in with Flask-Login
                    print("[LOGIN] Logging in user with Flask-Login")
                    login_successful = login_user(user, remember=remember, force=True)
                    print(f"[LOGIN] Flask-Login login result: {login_successful}")
                    
                    # Set session variables
                    session.permanent = True
                    session['user_id'] = user.id
                    session['_fresh'] = True
                    session.modified = True
                    
                    # Commit session changes
                    try:
                        db.session.commit()
                        print("[LOGIN] Session changes committed")
                    except Exception as e:
                        print(f"[ERROR] Committing session: {str(e)}")
                        db.session.rollback()
                    
                    print(f"[LOGIN] User {user.id} logged in successfully")
                    print(f"[LOGIN] Session after login: {dict(session)}")
                    
                    # Create response with secure cookie settings
                    response = redirect(next_page)
                    response.set_cookie(
                        'session',
                        value=session.sid,
                        httponly=True,
                        secure=app.config.get('SESSION_COOKIE_SECURE', False),
                        samesite='Lax',
                        max_age=86400 if remember else None,  # 24 hours if remember me is checked
                        path=app.config.get('SESSION_COOKIE_PATH', '/'),
                        domain=app.config.get('SESSION_COOKIE_DOMAIN')
                    )
                    
                    # Add cache control headers
                    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                    response.headers['Pragma'] = 'no-cache'
                    response.headers['Expires'] = '0'
                    
                    print(f"[LOGIN] Login successful, redirecting to: {next_page}")
                    print("="*50 + "\n")
                    return response
                else:
                    print("Password check failed")  # Debug print
                    flash('Invalid email or password', 'danger')
                    return redirect(url_for('login'))
            else:
                print(f"No user found with email: {email}")  # Debug print
                flash('Invalid email or password', 'danger')
                return redirect(url_for('login'))
                
        except Exception as e:
            print(f"Error in login: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            flash('Error during login. Please try again.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    try:
        user_id = current_user.id
        
        # Immediately clear user session and cookies
        logout_user()
        
        # Clear all session data
        session.clear()
        session.modified = True
        
        # Prepare response with cleared cookies
        response = redirect(url_for('login'))
        
        # Clear all cookies with proper flags
        cookies_to_clear = ['session', 'io', 'remember_token', 'session_id']
        for cookie in cookies_to_clear:
            response.set_cookie(
                cookie,
                value='',
                expires=0,
                path='/',
                secure=app.config.get('SESSION_COOKIE_SECURE', False),
                httponly=True,
                samesite='Lax'
            )
        
        # Add cache control headers
        response.headers.update({
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0'
        })
        
        # Update user status in database asynchronously
        def update_user_status():
            try:
                with app.app_context():
                    user = User.query.get(user_id)
                    if user:
                        user.authenticated = False
                        user.is_online = False
                        user.update_last_seen()
                        db.session.commit()
            except Exception as e:
                app.logger.error(f'Error updating user status: {str(e)}')
        
        # Clean up socket connections in background
        def cleanup_sockets():
            try:
                with app.app_context():
                    socketio.emit('force_disconnect', {'reason': 'user_logged_out'}, room=f'user_{user_id}')
                    if socketio.server.manager.rooms.get(f'user_{user_id}'):
                        socketio.close_room(f'user_{user_id}')
            except Exception as e:
                app.logger.error(f'Socket cleanup error: {str(e)}')
        
        # Start background threads
        from threading import Thread
        Thread(target=update_user_status, daemon=True).start()
        Thread(target=cleanup_sockets, daemon=True).start()
        
        flash('You have been logged out.', 'info')
        return response
        
    except Exception as e:
        app.logger.error(f'Error during logout: {str(e)}')
        flash('Error during logout.', 'danger')
        return redirect(url_for('login'))

profile_cache = {}

def get_cached_profile(user_id, max_age=300):  # 5 minutes cache
    cache_key = f'profile_{user_id}'
    cached = profile_cache.get(cache_key)
    if cached and (time.time() - cached['timestamp']) < max_age:
        return cached['content']
    
    # If not in cache, fetch from database with portfolio
    user = User.query.get(user_id)
    if user:
        # Calculate additional profile attributes
        user.total_reviews = Review.query.filter_by(worker_id=user_id).count()
        user.average_rating = db.session.query(db.func.avg(Review.rating)).filter_by(worker_id=user_id).scalar() or 0
        user.profile_views = user.profile_views or 0
        
        # Ensure portfolio is loaded
        if user.portfolio is None:
            from models.portfolio import Portfolio
            portfolio = Portfolio.query.filter_by(user_id=user_id).first()
            if portfolio:
                user.portfolio = portfolio
        
        # Cache the profile
        profile_cache[cache_key] = {
            'content': user,
            'timestamp': time.time()
        }
        return user
    return None

@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    app.logger.info(f"Starting profile route for user_id: {user_id}")
    # Initialize variables with safe defaults outside try block
    reviews = []
    total_reviews = 0
    average_rating = 0.0
    portfolio = None
    user = None
    
    try:
        # Always get fresh data from database
        app.logger.info("Querying user from database")
        user = User.query.get(user_id)
        if not user:
            app.logger.error(f"User {user_id} not found")
            return render_template('404.html', average_rating=0.0), 404
        
        app.logger.info(f"Found user: {user.username} (ID: {user.id})")
        
        # Initialize user stats if they are None
        if user.total_reviews is None:
            user.total_reviews = 0
        if user.average_rating is None:
            user.average_rating = 0.0
        if user.profile_views is None:
            user.profile_views = 0
        
        # Get user reviews and calculate stats
        app.logger.info("=== DEBUG: Starting reviews query ===")
        try:
            # First, verify the user ID we're querying for
            app.logger.info(f"Querying reviews for user ID: {user.id}")
            
            # Import required modules
            from sqlalchemy.orm import joinedload
            from sqlalchemy.sql import text
            from models.review import Review
            
            # Get reviews with reviewer information using explicit join and eager loading
            reviews = db.session.query(Review).options(joinedload(Review.reviewer))\
                                        .filter(Review.worker_id == user.id)\
                                        .order_by(Review.created_at.desc())\
                                        .all()
            
            app.logger.info(f"Found {len(reviews)} reviews in database for user {user.id}")
            
            # Log all reviews found
            for i, review in enumerate(reviews, 1):
                reviewer_name = review.reviewer.full_name if hasattr(review, 'reviewer') and review.reviewer else 'Unknown'
                app.logger.info(f"Review {i}: ID={review.id}, Rating={review.rating}, "
                              f"Reviewer={reviewer_name}, Comment={review.comment[:50] if review.comment else ''}")
            
            # Calculate total reviews and average rating
            total_reviews = len(reviews)
            
            if total_reviews > 0:
                total_rating = sum(review.rating for review in reviews if review.rating is not None)
                average_rating = round(total_rating / total_reviews, 1) if total_reviews > 0 else 0
                app.logger.info(f"Calculated average rating: {average_rating} from {total_reviews} reviews")
                
                # Update user's review stats
                user.total_reviews = total_reviews
                user.average_rating = average_rating
                
                # Convert reviews to the format expected by the template
                reviews_data = []
                for r in reviews:
                    reviewer = r.reviewer if hasattr(r, 'reviewer') and r.reviewer else None
                    review_dict = {
                        'id': r.id,
                        'rating': r.rating,
                        'comment': r.comment,
                        'created_at': r.created_at.isoformat() if r.created_at else None,
                        'reviewer_name': reviewer.full_name if reviewer else 'Unknown',
                        'reviewer_id': r.reviewer_id,
                        'reviewer_photo': reviewer.photo if reviewer and hasattr(reviewer, 'photo') and reviewer.photo else None
                    }
                    reviews_data.append(review_dict)
                    app.logger.info(f"Review data: {review_dict}")
                
                reviews = reviews_data
            else:
                app.logger.warning(f"No reviews found for user ID: {user.id}")
                reviews = []
                user.total_reviews = 0
                user.average_rating = 0.0
            
            # Track profile view if viewer is logged in and viewing someone else's profile
            if current_user.is_authenticated and user.id != current_user.id:
                user.profile_views += 1
                app.logger.info(f"Incremented profile views to {user.profile_views}")
        except Exception as e:
            app.logger.error(f"Error processing reviews: {str(e)}")
            # Keep default values if any error occurs
            
        # Get portfolio data
        try:
            app.logger.info("Getting portfolio data")
            portfolio = user.portfolio
        except Exception as e:
            app.logger.error(f"Error getting portfolio: {str(e)}")
            portfolio = None
        
        # Commit all changes in one transaction
        try:
            db.session.commit()
            app.logger.info("Database changes committed successfully")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Database error in profile route: {str(e)}", exc_info=True)
        
        # Ensure reviews is a list
        reviews_data = reviews if isinstance(reviews, list) else []
        
        # Get related users (workers with similar skills/location)
        related_users = []
        try:
            if user.user_type == 'worker':
                # Get up to 6 related users (increased from 4)
                related_users = user.get_related_users(limit=6)
                app.logger.info(f"Found {len(related_users)} related users for {user.username}")
        except Exception as e:
            app.logger.error(f"Error getting related users: {str(e)}", exc_info=True)
        
        # Prepare template context
        context = {
            'user': user,
            'reviews': reviews_data,  # Now using serializable data
            'portfolio': portfolio,
            'total_reviews': total_reviews,
            'average_rating': average_rating,
            'related_users': related_users,
            'debug_mode': True  # Add debug mode flag
        }
        
        # Log template context
        app.logger.info("=== TEMPLATE CONTEXT ===")
        for key, value in context.items():
            if key == 'reviews':
                app.logger.info("Context[%s] = %s items", key, len(value) if hasattr(value, '__len__') else 'N/A')
            else:
                app.logger.info("Context[%s] = %s", key, value)
        
        # Render template with context
        response = make_response(render_template('profile.html', **context))
        
        # Add debug headers
        response.headers['X-Debug-Reviews-Count'] = str(len(reviews_data))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        app.logger.error(f"Unhandled error in profile route: {str(e)}", exc_info=True)
        db.session.rollback()
        return render_template('500.html', average_rating=average_rating), 500

@app.route('/handle-contact-request/<int:request_id>/<string:action>')
@login_required
def handle_contact_request(request_id, action):
    contact_request = ContactRequest.query.get_or_404(request_id)
    
    # Verify the current user is the one who received the request
    if contact_request.requested_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('index'))
    
    if action == 'accept':
        contact_request.status = 'accepted'
        flash('Contact request accepted!', 'success')
    elif action == 'reject':
        contact_request.status = 'rejected'
        flash('Contact request rejected.', 'info')
    
    db.session.commit()
    return redirect(url_for('profile', user_id=contact_request.requester_id))

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        try:
            print("Form data received:", request.form)
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            # Get the existing user with the same email (excluding current user)
            email = request.form.get('email')
            if email:
                existing_email_user = User.query.filter(User.email == email, User.id != current_user.id).first()
                if existing_email_user:
                    if is_ajax:
                        return jsonify({'error': 'Email already exists.'}), 400
                    flash('Email already exists.', 'danger')
                    return redirect(url_for('edit_profile'))

            # Get the existing user with the same phone (excluding current user)
            phone = request.form.get('phone')
            if phone:
                existing_phone_user = User.query.filter(User.phone == phone, User.id != current_user.id).first()
                if existing_phone_user:
                    if is_ajax:
                        return jsonify({'error': 'Phone number already exists.'}), 400
                    flash('Phone number already exists.', 'danger')
                    return redirect(url_for('edit_profile'))

            # Update user fields with validation
            if request.form.get('full_name'):
                current_user.full_name = request.form.get('full_name')
            if email:
                current_user.email = email
            if phone:
                current_user.phone = phone
            
            current_user.education = request.form.get('education', '')
            current_user.experience = request.form.get('experience', '')
            current_user.current_location = request.form.get('current_location', '')
            current_user.live_location = request.form.get('live_location', '')
            current_user.work = request.form.get('work', '')
            current_user.mother_name = request.form.get('mother_name', '')
            current_user.father_name = request.form.get('father_name', '')
            current_user.bio = request.form.get('bio', '')
            current_user.skills = request.form.get('skills', '')
            current_user.categories = request.form.get('categories', '')
            current_user.availability = request.form.get('availability', 'available')
            
            # Handle profile picture upload
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Generate a secure filename with user's email as prefix
                    file_ext = os.path.splitext(file.filename)[1].lower()
                    safe_email = current_user.email.split('@')[0].lower().replace('.', '_')
                    photo_filename = f"{safe_email}_{int(time.time())}{file_ext}"
                    file_path = os.path.join(app.config['PROFILE_PICS_FOLDER'], photo_filename)
                    
                    # Ensure the upload directory exists
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    try:
                        # Remove old profile picture if it exists
                        if current_user.photo:
                            old_photo_path = os.path.join(app.config['PROFILE_PICS_FOLDER'], current_user.photo)
                            if os.path.exists(old_photo_path):
                                os.remove(old_photo_path)
                        
                        # Save new profile picture
                        file.save(file_path)
                        current_user.photo = photo_filename
                        print(f"Updated profile picture to: {file_path}")
                    except Exception as e:
                        app.logger.error(f"Error updating profile picture: {str(e)}")
                        app.logger.error(traceback.format_exc())
                        # Don't fail the entire update if image save fails
            
            # Handle date of birth
            dob = request.form.get('date_of_birth')
            try:
                if dob and dob.strip():
                    current_user.date_of_birth = datetime.strptime(dob, '%Y-%m-%d')
                else:
                    current_user.date_of_birth = None
            except ValueError as e:
                print(f"Date parsing error: {e}")
                if is_ajax:
                    return jsonify({'error': 'Invalid date format for date of birth.'}), 400
                flash('Invalid date format for date of birth.', 'danger')
                return redirect(url_for('edit_profile'))

            # Handle payment information
            current_user.payment_type = request.form.get('payment_type')
            payment_charge = request.form.get('payment_charge')
            try:
                if payment_charge and payment_charge.strip():
                    current_user.payment_charge = float(payment_charge)
                else:
                    current_user.payment_charge = None
            except ValueError as e:
                print(f"Payment charge parsing error: {e}")
                if is_ajax:
                    return jsonify({'error': 'Invalid payment charge value.'}), 400
                flash('Invalid payment charge value.', 'danger')
                return redirect(url_for('edit_profile'))

            print("About to commit changes...")
            db.session.commit()
            print("Changes committed successfully")

            # Clear caches
            try:
                cache_key = f'profile_{current_user.id}'
                if cache_key in profile_cache:
                    del profile_cache[cache_key]
                cache.delete_memoized(profile, current_user.id)
                cache.delete_memoized(get_cached_profile, current_user.id)
                print("Cache cleared successfully")
            except Exception as cache_error:
                print(f"Cache clearing error (non-critical): {cache_error}")

            # Emit WebSocket event to notify profile update
            try:
                print(f"Emitting profile_updated event for user {current_user.id}")
                socketio.emit('profile_updated', {
                    'user_id': current_user.id,
                    'success': True,
                    'message': 'Profile updated successfully',
                    'timestamp': datetime.now().isoformat(),
                    'photo': current_user.photo,
                    'full_name': current_user.full_name,
                    'username': current_user.username
                }, room='user_' + str(current_user.id))
                print("Profile update event emitted successfully")
            except Exception as e:
                print(f"Error emitting profile_updated event: {str(e)}")

            if is_ajax:
                return jsonify({
                    'success': True,
                    'message': 'Profile updated successfully!',
                    'redirect': url_for('profile', user_id=current_user.id)
                })
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile', user_id=current_user.id))

        except Exception as e:
            db.session.rollback()
            error_msg = f"Error updating profile: {str(e)}"
            error_type = type(e).__name__
            error_details = str(e.__dict__) if hasattr(e, '__dict__') else 'No additional details'
            
            print(f"{error_msg} - Type: {error_type}")
            print(f"Error details: {error_details}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response = jsonify({
                    'success': False,
                    'error': error_msg,
                    'type': error_type,
                    'details': error_details
                })
                return response, 500
                
            flash(error_msg, 'danger')
            return redirect(url_for('edit_profile'))
    
    return render_template('edit_profile.html', user=current_user)

@app.route('/review/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def review(worker_id):
    # Refresh user session
    session.permanent = True
    
    # Start a database session
    db.session.begin()
    
    try:
        worker = User.query.get_or_404(worker_id)
        
        if current_user.id == worker_id:
            db.session.rollback()
            if request.is_json:
                return jsonify({'success': False, 'error': 'You cannot review yourself.'}), 400
            flash('You cannot review yourself.', 'error')
            return redirect(url_for('profile', user_id=worker_id))
        
        # Check if user has already reviewed this worker
        existing_review = Review.query.filter_by(
            worker_id=worker_id,
            reviewer_id=current_user.id
        ).first()
        
        if existing_review:
            db.session.rollback()
            if request.is_json:
                return jsonify({'success': False, 'error': 'You have already reviewed this user.'}), 400
            flash('You have already reviewed this user.', 'error')
            return redirect(url_for('profile', user_id=worker_id))
        
        if request.method == 'POST':
            # Handle both form and JSON data
            if request.is_json:
                data = request.get_json()
                rating = data.get('rating')
                comment = data.get('comment', '').strip()
            else:
                rating = request.form.get('rating', type=int)
                comment = request.form.get('comment', '').strip()
            
            if not rating or rating < 1 or rating > 5:
                error_msg = 'Please provide a valid rating between 1 and 5 stars.'
                db.session.rollback()
                if request.is_json:
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('review', worker_id=worker_id))
            
            if not comment:
                error_msg = 'Please provide a review comment.'
                db.session.rollback()
                if request.is_json:
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'error')
                return redirect(url_for('review', worker_id=worker_id))
            
            # Create new review
            review = Review(
                worker_id=worker_id,
                reviewer_id=current_user.id,
                rating=rating,
                comment=comment
            )
            db.session.add(review)

            try:
                # Calculate new average rating and total reviews
                
                db.session.add(review)
                
                # Update worker's review stats
                worker.update_rating()
                
                # Commit all changes
                db.session.commit()
                
                # Prepare response data
                response_data = {
                    'success': True,
                    'message': 'Review submitted successfully!',
                    'review': {
                        'id': review.id,
                        'reviewer_name': current_user.full_name,
                        'reviewer_photo': url_for('serve_profile_pic', filename=current_user.photo) if current_user.photo else url_for('static', filename='img/default-avatar.png'),
                        'rating': review.rating,
                        'comment': review.comment,
                        'created_at': review.created_at.strftime('%B %d, %Y')
                    },
                    'stats': {
                        'average_rating': worker.average_rating,
                        'total_reviews': worker.total_reviews
                    }
                }
                
                if request.is_json:
                    return jsonify(response_data)
                
                flash('Your review has been submitted successfully!', 'success')
                return redirect(url_for('profile', user_id=worker_id))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error creating review: {str(e)}")
                if request.is_json:
                    return jsonify({'success': False, 'error': 'An error occurred while saving your review.'}), 500
                flash('An error occurred while saving your review. Please try again.', 'error')
                return redirect(url_for('profile', user_id=worker_id))
        
        # GET request - show review form
        current_date = datetime.now()
        return render_template('review.html', 
            form_data={},
            current_date=current_date.strftime('%Y-%m-%d'),
            worker=worker, 
            existing_review=existing_review)
    
    except Exception as e:
        app.logger.error(f'Unexpected error in review route: {str(e)}')
        error_msg = 'An unexpected error occurred. Please try again.'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        flash(error_msg, 'error')
        return redirect(url_for('index'))

def generate_csrf_token():
    import secrets
    return secrets.token_hex(16)

@app.route('/message/<int:user_id>', methods=['GET', 'POST'])
@login_required
def message(user_id):
    try:
        recipient = User.query.get_or_404(user_id)
        if recipient.id == current_user.id:
            flash('You cannot message yourself', 'danger')
            return redirect(url_for('profile', user_id=user_id))
        
        if request.method == 'POST':
            content = request.form.get('content')
            if content:
                try:
                    # Track message behavior
                    risk_score = fraud_detection.track_behavior(
                        user_id=current_user.id,
                        ip_address=request.remote_addr,
                        user_agent=request.user_agent.string,
                        action_type='message',
                        action_details={'recipient_id': user_id}
                    )
                    
                    if risk_score >= fraud_detection.RISK_THRESHOLD_HIGH:
                        flash(_('Message blocked due to suspicious activity.'), 'danger')
                        return render_template('chat.html', 
                                            sender=current_user, 
                                            receiver=recipient, 
                                            messages=[])
                    
                    message = Message(
                        sender_id=current_user.id,
                        receiver_id=recipient.id,
                        content=content
                    )
                    db.session.add(message)
                    db.session.commit()
                    flash('Message sent successfully', 'success')
                    
                    # Redirect to chat route instead of messages list
                    return redirect(url_for('chat', user_id=user_id))
                    
                except SQLAlchemyError as e:
                    app.logger.error(f"Database error saving message: {str(e)}")
                    db.session.rollback()
                    flash('Error saving message. Please try again.', 'error')
                    return render_template('chat.html', 
                                        sender=current_user, 
                                        receiver=recipient, 
                                        messages=[])
        
        try:
            # Get chat history
            messages = Message.query.filter(
                db.or_(
                    db.and_(Message.sender_id == current_user.id, Message.receiver_id == recipient.id),
                    db.and_(Message.sender_id == recipient.id, Message.receiver_id == current_user.id)
                )
            ).order_by(Message.created_at.asc()).all()
            
            # Mark messages as read
            unread_messages = Message.query.filter_by(
                sender_id=recipient.id,
                receiver_id=current_user.id,
                is_read=False
            ).all()
            
            for msg in unread_messages:
                msg.is_read = True
            db.session.commit()
            
            return render_template('chat.html', 
                                sender=current_user, 
                                receiver=recipient, 
                                messages=messages)
            
        except SQLAlchemyError as e:
            app.logger.error(f"Database error loading chat: {str(e)}")
            db.session.rollback()
            flash('Unable to load chat messages. Please try refreshing the page.', 'error')
            return render_template('chat.html',
                                sender=current_user,
                                receiver=recipient,
                                messages=[])
            
    except Exception as e:
        app.logger.error(f"Unexpected error in message route: {str(e)}")
        app.logger.error(traceback.format_exc())
        flash('An error occurred. Please try again.', 'error')
        return render_template('chat.html',
                            sender=current_user if 'current_user' in locals() else None,
                            receiver=recipient if 'recipient' in locals() else None,
                            messages=[])

@app.route('/messages')
@login_required
def messages():
    messages_received = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.created_at.desc()).all()
    messages_sent = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_at.desc()).all()
    return render_template('message_list.html', messages_received=messages_received, messages_sent=messages_sent)

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    # Prepare user settings
    user_settings = {
        'email_notifications': getattr(current_user, 'email_notifications', True),
        'message_notifications': getattr(current_user, 'message_notifications', True),
        'review_notifications': getattr(current_user, 'review_notifications', True)
    }
    
    if request.method == 'POST':
        try:
            # Handle password change
            if 'current_password' in request.form:
                current_password = request.form.get('current_password')
                new_password = request.form.get('new_password')
                confirm_password = request.form.get('confirm_password')
                
                if not current_user.check_password(current_password):
                    flash('Current password is incorrect.', 'error')
                    return render_template('account.html', 
                                        user=current_user, 
                                        settings=user_settings,
                                        title='Account Settings')
                
                if new_password != confirm_password:
                    flash('New passwords do not match.', 'error')
                    return render_template('account.html',
                                        user=current_user, 
                                        settings=user_settings,
                                        title='Account Settings')
                
                current_user.set_password(new_password)
                db.session.commit()
                flash('Password has been updated successfully.', 'success')
                return redirect(url_for('account'))
            
            # Handle photo upload
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename:
                    if file.filename.split('.')[-1].lower() in {'png', 'jpg', 'jpeg', 'gif'}:
                        filename = secure_filename(f"{current_user.id}_{int(time.time())}_{file.filename}")
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        
                        # Save the file and update user's profile picture
                        try:
                            # Delete old photo if exists
                            if current_user.photo and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], current_user.photo)):
                                try:
                                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], current_user.photo))
                                except Exception as e:
                                    print(f"Error removing old profile picture: {str(e)}")
                            
                            file.save(file_path)
                            current_user.photo = filename
                            db.session.commit()
                            flash('Profile picture updated successfully!', 'success')
                        except Exception as e:
                            db.session.rollback()
                            flash('Error updating profile picture. Please try again.', 'error')
                            print(f"Error saving profile picture: {str(e)}")
                    else:
                        flash('Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF).', 'error')
                    
                    return render_template('account.html', 
                                        user=current_user, 
                                        settings=user_settings,
                                        title='Account Settings')
            
            # Handle other form fields
            updated_fields = []
            
            # Helper function to update fields with extensive logging
            def update_field(attr, form_key, display_name=None):
                form_value = request.form.get(form_key, '').strip()
                current_value = str(getattr(current_user, attr, '')).strip()
                display_name = display_name or form_key.replace('_', ' ').title()
                
                if form_value and str(form_value) != str(current_value):
                    try:
                        setattr(current_user, attr, form_value)
                        updated_fields.append(display_name)
                        return True
                    except Exception as update_err:
                        print(f"Error updating {display_name}: {update_err}")
                return False
            
            # Update various fields
            fields_to_update = [
                ('full_name', 'Full Name'),
                ('mother_name', 'Mother\'s Name'),
                ('father_name', 'Father\'s Name'),
                ('live_location', 'Live Location'),
                ('current_location', 'Current Location'),
                ('work', 'Work'),
                ('experience', 'Experience'),
                ('education', 'Education'),
                ('bio', 'Bio'),
                ('payment_type', 'Payment Type'),
                ('skills', 'Skills'),
                ('categories', 'Categories')
            ]
            
            # Update all fields
            for attr, display_name in fields_to_update:
                update_field(attr, attr, display_name)
            
            # Handle numeric fields separately
            try:
                age = request.form.get('age')
                if age and int(age) != current_user.age:
                    current_user.age = int(age)
                    updated_fields.append('Age')
            except (TypeError, ValueError):
                pass
            
            try:
                payment_charge = request.form.get('payment_charge')
                if payment_charge and float(payment_charge) != current_user.payment_charge:
                    current_user.payment_charge = float(payment_charge)
                    updated_fields.append('Payment Charge')
            except (TypeError, ValueError):
                pass
            
            # Handle notification settings
            email_notifications = request.form.get('email_notifications') == 'on'
            message_notifications = request.form.get('message_notifications') == 'on'
            review_notifications = request.form.get('review_notifications') == 'on'
            
            if hasattr(current_user, 'email_notifications') and current_user.email_notifications != email_notifications:
                current_user.email_notifications = email_notifications
                updated_fields.append('Email Notifications')
            if hasattr(current_user, 'message_notifications') and current_user.message_notifications != message_notifications:
                current_user.message_notifications = message_notifications
                updated_fields.append('Message Notifications')
            if hasattr(current_user, 'review_notifications') and current_user.review_notifications != review_notifications:
                current_user.review_notifications = review_notifications
                updated_fields.append('Review Notifications')
            
            # Commit changes
            db.session.commit()
            
            # Provide feedback
            if updated_fields:
                flash(f"Updated: {', '.join(updated_fields)}", 'success')
            else:
                flash("No changes were made.", 'info')
            
            return redirect(url_for('account'))
        
        except Exception as e:
            db.session.rollback()
            print(f"Error updating account: {e}")
            flash(f"An error occurred: {e}", 'error')
            return redirect(url_for('account'))
    
    return render_template('account.html', 
                         title='Account Settings', 
                         user=current_user,
                         settings=user_settings)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('forgot_password.html')

        user = User.query.filter_by(email=email).first()
        
        if user:
            try:
                # Generate token
                token = serializer.dumps(user.email, salt='password-reset-salt')
                
                # Create reset URL
                reset_url = url_for('reset_password', token=token, _external=True)
                
                # Send email
                if send_reset_email(user.email, reset_url):
                    flash('Password reset instructions have been sent to your email.', 'success')
                else:
                    flash('Error sending reset email. Please try again later.', 'danger')
            except Exception as e:
                app.logger.error(f"Password reset error for {email}: {str(e)}")
                flash('An error occurred. Please try again later.', 'danger')
        else:
            # Don't reveal if email exists or not for security
            flash('If an account exists with that email, you will receive password reset instructions.', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Invalid reset link. Please try again.', 'danger')
            return redirect(url_for('forgot_password'))
        
        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if not password or not confirm_password:
                flash('Please fill in all fields.', 'danger')
                return render_template('reset_password.html')
            
            if password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return render_template('reset_password.html')
            
            if len(password) < 8:
                flash('Password must be at least 8 characters long.', 'danger')
                return render_template('reset_password.html')
            
            user.set_password(password)
            user.reset_token = None
            user.reset_token_expiry = None
            db.session.commit()
            
            flash('Your password has been reset successfully. You can now log in with your new password.', 'success')
            return redirect(url_for('login'))
        
        return render_template('reset_password.html')
        
    except:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    try:
        # Get the current user
        user = User.query.get(current_user.id)
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('account'))

        # Delete all messages
        Message.query.filter((Message.sender_id == user.id) | (Message.receiver_id == user.id)).delete()
        
        # Delete all reviews
        Review.query.filter((Review.worker_id == user.id) | (Review.reviewer_id == user.id)).delete()
        
        # Delete all contact requests
        ContactRequest.query.filter((ContactRequest.requester_id == user.id) | (ContactRequest.requested_id == user.id)).delete()
        
        # Delete all transactions
        Transaction.query.filter_by(user_id=user.id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        # Log the user out
        logout_user()
        flash('Your account has been successfully deleted.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting account: {e}")

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html', average_rating=0.0, total_reviews=0, portfolio=None, reviews=[]), 404

@app.errorhandler(500)
def internal_error(error):
    import traceback
    print("\n--- 500 Internal Server Error ---")
    print(f"Error: {error}")
    traceback.print_exc()
    
    db.session.rollback()
    app.logger.error('Server Error: %s', error)
    return render_template('500.html', average_rating=0.0, total_reviews=0, portfolio=None, reviews=[]), 500

@app.errorhandler(400)
def bad_request_error(error):
    if 'csrf_token' in str(error):
        return jsonify({
            'success': False,
            'message': 'Invalid CSRF token. Please refresh the page and try again.'
        }), 400
    return jsonify({
        'success': False,
        'message': 'Bad request. Please try again.'
    }), 400

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.is_json:
        return jsonify({
            'success': False,
            'message': 'Invalid CSRF token. Please refresh the page and try again.'
        }), 400
    flash('Session expired. Please refresh the page and try again.', 'danger')
    return redirect(url_for('track_help_request'))

# Admin Routes


    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    
    flash(_('Alert marked as resolved.'), 'success')
    return redirect(url_for('admin_fraud_alerts'))

@app.route('/admin/user/<username>/risk-profile')
@login_required
@admin_required
def admin_user_risk_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    risk_profile = fraud_detection.get_user_risk_profile(user.id)
    
    recent_alerts = FraudAlert.query.filter_by(user_id=user.id)\
        .order_by(FraudAlert.created_at.desc())\
        .limit(10).all()
        
    recent_behaviors = UserBehavior.query.filter_by(user_id=user.id)\
        .order_by(UserBehavior.timestamp.desc())\
        .limit(50).all()
        
    return render_template('admin/user_risk_profile.html',
                         user=user,
                         risk_profile=risk_profile,
                         recent_alerts=recent_alerts,
                         recent_behaviors=recent_behaviors)
@app.route('/admin/interactions')
@login_required
@admin_required
def admin_interactions():
    # Get all interactions with user details
    interactions = UserInteraction.query.order_by(UserInteraction.created_at.desc()).all()
    
    # Organize interactions by type
    interaction_stats = {
        'profile_views': [],
        'messages': [],
        'calls': []
    }
    
    # Process each interaction
    for interaction in interactions:
        viewer = User.query.get(interaction.viewer_id)
        viewed = User.query.get(interaction.viewed_id)
        
        if interaction.interaction_type == 'profile_view':
            interaction_stats['profile_views'].append({
                'viewer': viewer,
                'viewed': viewed,
                'timestamp': interaction.created_at
            })
        elif interaction.interaction_type == 'message':
            interaction_stats['messages'].append({
                'sender': viewer,
                'receiver': viewed,
                'timestamp': interaction.created_at
            })
        elif interaction.interaction_type == 'call':
            interaction_stats['calls'].append({
                'caller': viewer,
                'callee': viewed,
                'timestamp': interaction.created_at
            })
    
    # Prepare stats for the template
    stats = {
        'profile_views': interaction_stats['profile_views'],
        'total_views': len(interaction_stats['profile_views']),
        'unique_viewers': len({view['viewer'].id for view in interaction_stats['profile_views']}),
        'top_viewed': sorted(
            [(k, len(list(g))) for k, g in groupby(
                sorted(interaction_stats['profile_views'], key=lambda x: x['viewed'].id),
                key=lambda x: x['viewed']
            )],
            key=lambda x: x[1],
            reverse=True
        )[:5],  # Top 5 most viewed profiles
        'total_messages': len(interaction_stats['messages']),
        'unique_senders': len({msg['sender'].id for msg in interaction_stats['messages']}),
        'top_senders': sorted(
            [(k, len(list(g))) for k, g in groupby(
                sorted(interaction_stats['messages'], key=lambda x: x['sender'].id),
                key=lambda x: x['sender']
            )],
            key=lambda x: x[1],
            reverse=True
        )[:5],  # Top 5 most active senders
        'total_calls': len(interaction_stats['calls']),
        'unique_callers': len({call['caller'].id for call in interaction_stats['calls']}),
        'top_callers': sorted(
            [(k, len(list(g))) for k, g in groupby(
                sorted(interaction_stats['calls'], key=lambda x: x['caller'].id),
                key=lambda x: x['caller']
            )],
            key=lambda x: x[1],
            reverse=True
        )[:5]  # Top 5 most active callers
    }
    
    return render_template('admin/interactions.html', 
                         interaction_stats=interaction_stats,
                         interactions=interactions,
                         stats=stats)

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_transactions = Transaction.query.count()
    total_contact_requests = ContactRequest.query.count()
    total_reviews = Review.query.count()
    total_help_requests = HelpRequest.query.count()
    pending_help_requests = HelpRequest.query.filter_by(status='pending').count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_transactions = Transaction.query.join(User).order_by(Transaction.created_at.desc()).limit(5).all()
    recent_help_requests = HelpRequest.query.order_by(HelpRequest.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_transactions=total_transactions,
                         total_contact_requests=total_contact_requests,
                         total_reviews=total_reviews,
                         total_help_requests=total_help_requests,
                         pending_help_requests=pending_help_requests,
                         recent_users=recent_users,
                         recent_transactions=recent_transactions,
                         recent_help_requests=recent_help_requests)

@app.route('/admin/users')
@login_required
@admin_required
@cache.cached(timeout=60)  # Cache for 1 minute
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<username>')
@app.route('/admin/user/<username>/risk-profile')
@login_required
@admin_required
def admin_user_detail(username):
    user = User.query.filter_by(username=username).first_or_404()
    if 'risk-profile' in request.path:
        risk_profile = fraud_detection.get_user_risk_profile(user.id)
        recent_alerts = FraudAlert.query.filter_by(user_id=user.id)\
            .order_by(FraudAlert.created_at.desc())\
            .limit(10).all()
        recent_behaviors = UserBehavior.query.filter_by(user_id=user.id)\
            .order_by(UserBehavior.timestamp.desc())\
            .limit(50).all()
        return render_template('admin/user_risk_profile.html',
                             user=user,
                             risk_profile=risk_profile,
                             recent_alerts=recent_alerts,
                             recent_behaviors=recent_behaviors)
    else:
        if request.method == 'POST':
            user.is_admin = 'is_admin' in request.form
            user.availability = request.form.get('availability')
            db.session.commit()
            flash(_('User updated successfully'), 'success')
        return render_template('admin/user_detail.html', user=user)

@app.route('/admin/transactions')
@login_required
@admin_required
def admin_transactions():
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
    return render_template('admin/transactions.html', transactions=transactions)

@app.route('/admin/contact-requests')
@login_required
@admin_required
def admin_contact_requests():
    requests = ContactRequest.query.order_by(ContactRequest.created_at.desc()).all()
    return render_template('admin/contact_requests.html', requests=requests)

@app.route('/admin/reviews')
@login_required
@admin_required
def admin_reviews():
    reviews = Review.query.options(db.joinedload(Review.reviewer), db.joinedload(Review.worker)).order_by(Review.created_at.desc()).all()
    datatable_translations = {
        'search': _('Search'),
        'lengthMenu': _('Show _MENU_ entries'),
        'info': _('Showing _START_ to _END_ of _TOTAL_ entries'),
        'infoEmpty': _('Showing 0 to 0 of 0 entries'),
        'infoFiltered': _('(filtered from _MAX_ total entries)'),
        'emptyTable': _('No data available in table'),
        'zeroRecords': _('No matching records found'),
        'first': _('First'),
        'last': _('Last'),
        'next': _('Next'),
        'previous': _('Previous')
    }
    return render_template('admin/reviews.html', reviews=reviews, translations=datatable_translations)

@app.route('/admin/review/<int:review_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    worker = User.query.get(review.worker_id)
    db.session.delete(review)
    worker.update_rating()
    db.session.commit()
    flash(_('Review deleted successfully'), 'success')
    return redirect(url_for('admin_reviews'))

# Donation routes
@app.route('/donate')
def donate():
    return render_template('donation.html', razorpay_key_id=RAZORPAY_KEY_ID)

@app.route('/create-donation', methods=['POST'])
def create_donation():
    if not request.form.get('amount'):
        flash('Please enter a valid donation amount', 'error')
        return redirect(url_for('donate'))

    try:
        amount = float(request.form.get('amount'))
        if amount < 10:
            flash('Minimum donation amount is ₹10', 'error')
            return redirect(url_for('donate'))

        order_amount = int(amount * 100)  # Convert to paise
        order_currency = 'INR'
        
        # Create Razorpay Order
        order_data = {
            'amount': order_amount,
            'currency': order_currency,
            'payment_capture': '1'
        }
        order = razorpay_client.order.create(data=order_data)
        
        # Create donation record
        donation = Donation(
            amount=amount,
            donor_name=request.form.get('name') if not current_user.is_authenticated else current_user.full_name,
            donor_email=request.form.get('email') if not current_user.is_authenticated else current_user.email,
            message=request.form.get('message'),
            is_anonymous=bool(request.form.get('anonymous')),
            user_id=current_user.id if current_user.is_authenticated else None,
            transaction_id=order['id']
        )
        db.session.add(donation)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order_id': order['id'],
            'amount': order_amount
        })
    except Exception as e:
        app.logger.error(f'Error creating donation: {str(e)}')
        flash('An error occurred while processing your donation. Please try again.', 'error')
        return redirect(url_for('donate'))
    except Exception as e:
        app.logger.error(f'Error creating donation: {str(e)}')
        return jsonify({'error': 'An error occurred'}), 500

@app.route('/verify-donation')
def verify_donation():
    try:
        order_id = request.args.get('order_id')
        payment_id = request.args.get('payment_id')
        signature = request.args.get('signature')
        
        # Verify signature
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Update donation status
        donation = Donation.query.filter_by(transaction_id=order_id).first()
        if donation:
            donation.status = 'completed'
            db.session.commit()
            flash('Thank you for your generous donation!', 'success')
        
        return redirect(url_for('donate'))
    except Exception as e:
        app.logger.error(f'Error verifying donation: {str(e)}')
        flash('Payment verification failed. Please contact support if amount was deducted.', 'error')
        return redirect(url_for('donate'))

@app.route('/recent-donations')
def recent_donations():
    donations = (Donation.query
                .filter_by(status='completed')
                .order_by(Donation.created_at.desc())
                .limit(5)
                .all())
    
    return jsonify([{
        'donor_name': d.donor_name,
        'amount': d.amount,
        'message': d.message,
        'anonymous': d.is_anonymous
    } for d in donations])

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    if not current_user.is_authenticated:
        # Reject connection if user is not authenticated
        return False
    
    join_room(f'user_{current_user.id}')
    current_user.is_online = True
    current_user.last_active = datetime.utcnow()
    db.session.commit()

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')
        current_user.is_online = False
        current_user.last_active = datetime.utcnow()
        db.session.commit()

@socketio.on('join')
def on_join(data):
    room = data.get('room')
    if room and current_user.is_authenticated:
        join_room(room)

@socketio.on('leave')
def on_leave(data):
    room = data.get('room')
    if room and current_user.is_authenticated:
        leave_room(room)

@app.route('/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):
    try:
        receiver = User.query.get_or_404(user_id)
        if request.method == 'POST':
            content = request.form.get('content', '').strip()
            file = request.files.get('attachment')
            attachment_url = None
            
            if file and file.filename and allowed_file(file.filename):
                try:
                    # Create upload directory if it doesn't exist
                    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'chat'), exist_ok=True)
                    
                    # Secure the filename
                    filename = secure_filename(datetime.now().strftime('%Y%m%d_%H%M%S_') + file.filename)
                    name, ext = os.path.splitext(filename)
                    filename = f"{name}_{int(datetime.utcnow().timestamp())}{ext}"
                    
                    # Save the file
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'chat', filename)
                    file.save(file_path)
                    attachment_url = url_for('static', filename=f'uploads/chat/{filename}')
                except (OSError, IOError) as e:
                    app.logger.error(f"Error saving attachment: {str(e)}")
                    return jsonify({'status': 'error', 'message': 'Error uploading file. Please try again.'}), 400
            
            if content or attachment_url:
                try:
                    message = Message(
                        sender_id=current_user.id,
                        receiver_id=user_id,
                        content=content,
                        attachment=attachment_url
                    )
                    db.session.add(message)
                    
                    # Track message interaction
                    interaction = UserInteraction(
                        viewer_id=current_user.id,
                        viewed_id=user_id,
                        interaction_type='message'
                    )
                    db.session.add(interaction)
                    db.session.commit()
                    
                    # Prepare message data
                    message_data = {
                        'status': 'success',
                        'content': content,
                        'attachment_url': attachment_url,
                        'sender_id': current_user.id,
                        'sender_photo': current_user.photo,
                        'sender_name': current_user.full_name,
                        'timestamp': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Emit to both sender and receiver
                    socketio.emit('receive_message', message_data, room=f'user_{current_user.id}')
                    socketio.emit('receive_message', message_data, room=f'user_{user_id}')
                    
                    # Return success response
                    return jsonify(message_data)
                except SQLAlchemyError as e:
                    app.logger.error(f"Database error saving message: {str(e)}")
                    db.session.rollback()
                    return jsonify({'status': 'error', 'message': 'Error saving message. Please try again.'}), 500
                except SocketIOError as e:
                    app.logger.error(f"SocketIO error: {str(e)}")
                    # Don't return error here since message is saved, client will get it on reconnect
                    return jsonify(message_data)
            
            return jsonify({'status': 'error', 'message': 'Please enter a message or attach a file.'}), 400
        
        try:
            # Get chat history and mark unread messages as read in a single query
            messages = Message.query.filter(
                db.or_(
                    db.and_(Message.sender_id == current_user.id, Message.receiver_id == user_id),
                    db.and_(Message.sender_id == user_id, Message.receiver_id == current_user.id)
                )
            ).order_by(Message.created_at.asc()).all()
            
            # Update unread messages in a single query
            Message.query.filter_by(
                sender_id=user_id,
                receiver_id=current_user.id,
                is_read=False
            ).update({Message.is_read: True})
            
            # Clear the unread count cache
            if hasattr(current_user, '_unread_count'):
                delattr(current_user, '_unread_count')
                
            db.session.commit()
            
            return render_template('chat.html', 
                                receiver=receiver, 
                                messages=messages,
                                current_userid=current_user.id,
                                receiverid=user_id)
        
        except SQLAlchemyError as e:
            app.logger.error(f"Database error loading chat: {str(e)}")
            db.session.rollback()
            flash('Unable to load chat messages. Please try refreshing the page.', 'error')
            return render_template('chat.html',
                                receiver=receiver,
                                messages=[],
                                current_userid=current_user.id,
                                receiverid=user_id)
            
    except Exception as e:
        app.logger.error(f"Unexpected error in chat route: {str(e)}")
        app.logger.error(traceback.format_exc())
        flash('An error occurred. Please try again.', 'error')
        # Return to chat page instead of redirecting
        return render_template('chat.html',
                            receiver=receiver if 'receiver' in locals() else None,
                            messages=[],
                            current_userid=current_user.id,
                            receiverid=user_id)

@login_manager.user_loader
@cache.memoize(timeout=300)
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.after_request
def after_request(response):
    # Enable CORS
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Add caching headers for better performance
    if request.endpoint == 'static' or request.path.startswith('/static/'):
        response.cache_control.public = True
        response.cache_control.max_age = 31536000  # 1 year
        response.expires = int(time.time() + 31536000)
    elif request.method == 'GET':
        response.cache_control.public = True
        response.cache_control.max_age = 300  # 5 minutes for other GET requests
        response.expires = int(time.time() + 300)
    
    return response

@app.before_request
def before_request():
    # Check if user is authenticated but not active or authenticated flag is False
    if current_user.is_authenticated:
        if not current_user.active or not current_user.authenticated:
            logout_user()
            session.clear()
            db.session.remove()
            return redirect(url_for('login'))
        current_user.update_last_seen()
    
    # Set language code for SEO
    g.lang_code = str(get_locale())

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

@cache.memoize(timeout=300)
def get_user_profile(user_id):
    return User.query.get_or_404(user_id)

@cache.memoize(timeout=300)
def get_user_reviews(user_id):
    return Review.query.filter_by(worker_id=user_id).order_by(Review.created_at.desc()).all()

@app.route('/api/check_contact_payment/<int:user_id>/<contact_type>')
def check_contact_payment(user_id, contact_type):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    
    target_user = User.query.get_or_404(user_id)
    
    # All contact types are free
    payment_required = False
    amount = 0
    
    return jsonify({
        'payment_required': payment_required,
        'amount': amount,
        'email': target_user.email,
        'phone': target_user.phone
    })

@app.route('/get_unread_count', methods=['GET'])
@login_required
def get_unread_count():
    if not current_user.is_authenticated:
        return jsonify({'count': 0})
    
    if not hasattr(current_user, '_unread_count'):
        current_user._unread_count = Message.query.filter_by(
            receiver_id=current_user.id,
            is_read=False
        ).count()
    
    return jsonify({'count': current_user._unread_count})

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP to user's email"""
    if 'registration_data' not in session:
        return jsonify({
            'status': 'error',
            'message': 'No pending verification. Please register first.'
        }), 400

    reg_data = session['registration_data']
    
    # Check if we can resend (1 minute cooldown)
    current_time = datetime.utcnow().timestamp()
    last_sent = reg_data.get('last_resend', 0)
    if current_time - last_sent < 60:
        return jsonify({
            'status': 'error',
            'message': f'Please wait {60 - int(current_time - last_sent)} seconds before requesting a new code.'
        }), 429

    # Generate new OTP
    new_otp = generate_otp()
    reg_data['otp'] = new_otp
    reg_data['timestamp'] = current_time
    reg_data['last_resend'] = current_time
    reg_data['attempts'] = 0  # Reset attempts
    session['registration_data'] = reg_data

    try:
        send_otp_email(reg_data['email'], new_otp)
        return jsonify({
            'status': 'success',
            'message': 'Verification code has been resent to your email.'
        })
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to send verification code. Please try again.'
        }), 500

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Handle OTP verification for worker registration"""
    if 'pending_verification_id' not in session:
        flash('No pending verification. Please register first.', 'error')
        return redirect(url_for('register'))

    if request.method == 'POST':
        otp_attempt = request.form.get('otp')
        if not otp_attempt:
            flash('Please enter the verification code.', 'error')
            return redirect(url_for('verify_otp'))

        # Get the pending user from database
        user_id = session.get('pending_verification_id')
        user = User.query.get(user_id)
        
        if not user:
            session.pop('pending_verification_id', None)
            flash('User not found. Please try registering again.', 'error')
            return redirect(url_for('register'))

        # Check if OTP has expired (10 minutes)
        if datetime.utcnow() > user.otp_expiry:
            db.session.delete(user)
            db.session.commit()
            session.pop('pending_verification_id', None)
            flash('Verification code has expired. Please try registering again.', 'error')
            return redirect(url_for('register'))

        if otp_attempt != user.email_otp:
            flash('Invalid verification code. Please try again.', 'error')
            return redirect(url_for('verify_otp'))

        try:
            # Update user status
            user.email_verified = True
            user.active = True
            user.authenticated = True
            user.email_otp = None  # Clear OTP after successful verification

            # Save changes to database
            db.session.commit()
            print(f"User verified successfully: {user.email}")

            # Clear verification data from session
            session.pop('pending_verification_id', None)

            # Log the user in
            login_user(user)
            print(f"User logged in: {user.email}")

            # Show success message
            flash('Registration successful! Welcome to Fuetime!', 'success')
                
            # Redirect to main index for workers
            return redirect(url_for('main.index'))

        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'error')
            return redirect(url_for('register'))

    # For GET request, show OTP verification form
    return render_template('verify_otp.html')

@app.route('/verify-business-otp', methods=['GET', 'POST'])
def verify_business_otp():
    """Handle OTP verification for business client registration"""
    if 'pending_verification_id' not in session:
        flash('No pending verification. Please register first.', 'error')
        return redirect(url_for('register_client'))

    if request.method == 'POST':
        otp_attempt = request.form.get('otp')
        if not otp_attempt:
            flash('Please enter the verification code.', 'error')
            return redirect(url_for('verify_business_otp'))

        # Get the pending user from database
        user_id = session.get('pending_verification_id')
        user = User.query.get(user_id)
        
        if not user:
            session.pop('pending_verification_id', None)
            flash('User not found. Please try registering again.', 'error')
            return redirect(url_for('register_client'))

        # Check if OTP has expired (10 minutes)
        if datetime.utcnow() > user.otp_expiry:
            db.session.delete(user)
            db.session.commit()
            session.pop('pending_verification_id', None)
            flash('Verification code has expired. Please try registering again.', 'error')
            return redirect(url_for('register_client'))

        if otp_attempt != user.email_otp:
            flash('Invalid verification code. Please try again.', 'error')
            return redirect(url_for('verify_business_otp'))

        try:
            # Update user status
            user.email_verified = True
            user.active = True
            user.authenticated = True
            user.email_otp = None  # Clear OTP after successful verification

            # Save changes to database
            db.session.commit()
            print(f"Business client verified successfully: {user.email}")

            # Clear verification data from session
            session.pop('pending_verification_id', None)

            # Log the user in
            login_user(user)
            print(f"Business client logged in: {user.email}")

            # Show success message
            flash('Business registration successful! Welcome to Fuetime!', 'success')
                
            # Redirect to premium dashboard for business clients
            return redirect(url_for('premium_dashboard'))

        except Exception as e:
            db.session.rollback()
            print(f"Error creating business client: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'error')
            return redirect(url_for('register_client'))

    # For GET request, show business OTP verification form
    return render_template('verify_business_otp.html')

@app.route('/help')
def help():
    """Help page route"""
    return render_template('help.html')

@app.route('/sitemap.xml')
def sitemap():
    users = User.query.filter_by(active=True).all()
    template = render_template('sitemap.xml', 
                             users=users,
                             now=datetime.utcnow())
    response = make_response(template)
    response.headers['Content-Type'] = 'application/xml'
    return response

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/debug/reviews/<int:user_id>')
def debug_reviews(user_id):
    """Test endpoint to check reviews functionality"""
    from models.review import Review
    from models.user import User
    from sqlalchemy.orm import joinedload
    
    try:
        # Check if user exists
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get reviews with reviewer info using raw SQL for debugging
        sql = """
        SELECT r.*, u.full_name as reviewer_name, u.photo as reviewer_photo
        FROM review r
        LEFT JOIN user u ON r.reviewer_id = u.id
        WHERE r.worker_id = :worker_id
        ORDER BY r.created_at DESC
        """
        
        result = db.session.execute(text(sql), {'worker_id': user_id})
        reviews = [dict(row) for row in result.mappings()]
        
        # Also get using ORM for comparison
        orm_reviews = db.session.query(Review)\
                             .options(joinedload(Review.reviewer))\
                             .filter(Review.worker_id == user_id)\
                             .order_by(Review.created_at.desc())\
                             .all()
        
        orm_data = [{
            'id': r.id,
            'rating': r.rating,
            'comment': r.comment,
            'reviewer': r.reviewer.full_name if r.reviewer else 'Unknown',
            'created_at': r.created_at.isoformat() if r.created_at else None
        } for r in orm_reviews]
        
        return jsonify({
            'user_id': user_id,
            'user_exists': True,
            'sql_reviews': reviews,
            'orm_reviews': orm_data,
            'orm_review_count': len(orm_reviews),
            'sql_review_count': len(reviews)
        })
        
    except Exception as e:
        app.logger.error(f"Error in debug_reviews: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def send_help_request_email(user, help_request):
    try:
        # Log the start of email sending
        app.logger.info(f"Attempting to send email to {user.email} for ticket {help_request.ticket_id}")
        
        # Email content
        subject = f"Help Request Confirmation - Ticket #{help_request.ticket_id}"
        body = f"""
        <html>
        <body>
            <p>Dear {user.full_name},</p>
            <p>Thank you for contacting our support team. We've received your request and a ticket has been created.</p>
            
            <h3>Ticket Details:</h3>
            <p><strong>Ticket ID:</strong> {help_request.ticket_id}</p>
            <p><strong>Subject:</strong> {help_request.subject}</p>
            <p><strong>Description:</strong></p>
            <p>{help_request.description}</p>
            <p><strong>Status:</strong> {help_request.status.title()}</p>
            <p><strong>Submitted On:</strong> {help_request.created_at.strftime('%B %d, %Y %I:%M %p')}</p>
            
            <p>You can track the status of your ticket using the following link:</p>
            <p><a href="{url_for('track_help_request', _external=True)}">Track Your Ticket</a></p>
            
            <p>Our support team will review your request and get back to you as soon as possible.</p>
            <p>Thank you for your patience.</p>
            
            <p>Best regards,<br>Support Team</p>
        </body>
        </html>
        """
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = user.email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        # Debug log
        app.logger.info(f"SMTP Server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
        app.logger.info(f"Using TLS: {app.config['MAIL_USE_TLS']}")
        app.logger.info(f"From: {app.config['MAIL_DEFAULT_SENDER']}")
        app.logger.info(f"To: {user.email}")
        
        # Send email with more detailed error handling
        try:
            app.logger.info(f"Connecting to SMTP server with SSL: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
            
            try:
                # Create SMTP_SSL connection
                server = smtplib.SMTP_SSL(
                    host=app.config['MAIL_SERVER'],
                    port=app.config['MAIL_PORT'],
                    timeout=30
                )
                server.set_debuglevel(1)  # Enable debug output
                
                # Identify ourselves to the SMTP server
                server.ehlo()
                
                # Login to SMTP server
                if app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
                    try:
                        app.logger.info("Authenticating with SMTP server...")
                        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
                        app.logger.info("Successfully authenticated with SMTP server")
                    except smtplib.SMTPAuthenticationError as auth_err:
                        app.logger.error(f"SMTP Authentication Error: {str(auth_err)}")
                        server.quit()
                        return False
                    except Exception as login_err:
                        app.logger.error(f"SMTP Login Error: {str(login_err)}")
                        server.quit()
                        return False
                
                # Send the email
                try:
                    app.logger.info(f"Sending email to {user.email}...")
                    server.send_message(msg)
                    app.logger.info(f"Successfully sent email to {user.email}")
                    return True
                except Exception as send_err:
                    app.logger.error(f"Error sending email: {str(send_err)}")
                    return False
                
            except smtplib.SMTPConnectError as conn_err:
                app.logger.error(f"SMTP Connection Error: {str(conn_err)}")
                return False
            except smtplib.SMTPException as smtp_err:
                app.logger.error(f"SMTP Error: {str(smtp_err)}")
                return False
            except Exception as e:
                app.logger.error(f"Unexpected error: {str(e)}")
                return False
            finally:
                # Always close the connection
                try:
                    if 'server' in locals():
                        server.quit()
                except Exception as e:
                    app.logger.error(f"Error closing SMTP connection: {str(e)}")
                
        except smtplib.SMTPException as smtp_err:
            app.logger.error(f"SMTP Error: {str(smtp_err)}")
            return False
        except Exception as e:
            app.logger.error(f"Unexpected error while sending email: {str(e)}")
            app.logger.error(traceback.format_exc())  # Log full traceback
            return False
            
    except Exception as e:
        app.logger.error(f"Error in send_help_request_email: {str(e)}")
        app.logger.error(traceback.format_exc())  # Log full traceback
        return False

@app.route('/help/submit', methods=['POST'])
@login_required
def submit_help_request():
    if request.method == 'POST':
        subject = request.form.get('subject')
        description = request.form.get('description')
        
        app.logger.info(f"Received help request from user {current_user.id} with subject: {subject}")
        
        if not subject or not description:
            error_msg = 'Please fill in all fields'
            app.logger.warning(f"Validation failed: {error_msg}")
            flash(error_msg, 'error')
            return redirect(url_for('help'))
        
        try:
            # Generate a unique ticket ID
            ticket_id = str(uuid.uuid4().hex)[:10].upper()
            app.logger.info(f"Generated ticket ID: {ticket_id}")
            
            # Create help request
            help_request = HelpRequest(
                ticket_id=ticket_id,
                user_id=current_user.id,
                subject=subject,
                description=description,
                status='open'
            )
            
            db.session.add(help_request)
            db.session.commit()
            app.logger.info(f"Successfully created help request with ID: {ticket_id}")
            
            # Send confirmation email
            app.logger.info("Attempting to send confirmation email...")
            if not send_help_request_email(current_user, help_request):
                error_msg = f"Failed to send confirmation email for ticket {ticket_id}"
                app.logger.error(error_msg)
                flash('Your request was submitted, but we encountered an issue sending the confirmation email.', 'warning')
            else:
                app.logger.info(f"Successfully sent confirmation email for ticket {ticket_id}")
                flash(f'Your help request has been submitted. Ticket ID: {ticket_id}', 'success')
            
            return redirect(url_for('help'))
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error submitting help request: {str(e)}"
            app.logger.error(error_msg)
            app.logger.error(traceback.format_exc())  # Log full traceback
            flash('An error occurred while submitting your request. Please try again.', 'error')
            return redirect(url_for('help'))

@app.route('/help/track', methods=['GET', 'POST'])
@login_required
def track_help_request():
    if request.method == 'POST':
        ticket_id = request.form.get('ticket_id')
        help_request = HelpRequest.query.filter_by(ticket_id=ticket_id).first()
        
        if not help_request:
            flash('Invalid ticket ID. Please try again.', 'error')
            return redirect(url_for('track_help_request'))
            
        return render_template('help_status.html', help_request=help_request)
    
    return render_template('track_help.html')

# Admin help request routes
@app.route('/admin/help-requests')
@login_required
@admin_required
def admin_help_requests():
    help_requests = HelpRequest.query.order_by(HelpRequest.created_at.desc()).all()
    return render_template('admin/help_requests.html', help_requests=help_requests)

@app.route('/admin/help-request/<ticket_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_help_request(ticket_id):
    help_request = HelpRequest.query.filter_by(ticket_id=ticket_id).first_or_404()
    
    if request.method == 'POST':
        status = request.form.get('status')
        solution = request.form.get('solution')
        
        if status:
            help_request.status = status
        if solution:
            help_request.solution = solution
            
        db.session.commit()
        flash('Help request updated successfully.', 'success')
        return redirect(url_for('admin_help_request', ticket_id=ticket_id))
    
    return render_template('admin/help_request_detail.html', help_request=help_request)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/filter-by-location')
def filter_by_location():
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
        
        # Get all users
        users = User.query.filter(User.active == True).all()
        filtered_users = []
        
        for user in users:
            if user.current_location:
                try:
                    # Parse user location (assumed to be 'lat,lng' format)
                    user_lat, user_lng = map(float, user.current_location.split(','))
                    
                    # Calculate distance using Haversine formula
                    R = 6371  # Earth's radius in km
                    dlat = radians(user_lat - lat)
                    dlng = radians(user_lng - lng)
                    a = sin(dlat/2)**2 + cos(radians(lat)) * cos(radians(user_lat)) * sin(dlng/2)**2
                    c = 2 * atan2(sqrt(a), sqrt(1-a))
                    distance = R * c
                    
                    # Add user and their distance to the filtered list
                    user_data = {
                        'user': user,
                        'distance': round(distance, 1)  # Round to 1 decimal place
                    }
                    filtered_users.append(user_data)
                except ValueError:
                    continue
        
        # Sort users by distance
        filtered_users.sort(key=lambda x: x['distance'])
        
        # Render the user cards with distance information
        html = render_template('components/location_filtered_users.html', users=filtered_users)
        return jsonify({'success': True, 'html': html})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/initiate-call/<int:target_user_id>', methods=['POST'])
@login_required
def initiate_call(target_user_id):
    CALL_COST = 2.5  # Cost in rupees
    
    try:
        # Get fresh user object from database
        user = User.query.get(current_user.id)
        if not user:
            app.logger.error(f'User not found: {current_user.id}')
            return jsonify({
                'success': False,
                'message': 'User not found'
            })
            
        # Get exact balance and ensure it's a float, default to 0.0 if None
        current_balance = float(user.wallet_balance) if user.wallet_balance is not None else 0.0
        
        # Check if user has sufficient balance (using strict comparison)
        if current_balance < CALL_COST or abs(current_balance - CALL_COST) < 0.01:
            app.logger.warning(f'Insufficient balance. User: {user.id}, Balance: {current_balance}, Cost: {CALL_COST}')
            return jsonify({
                'success': False,
                'redirect': url_for('wallet'),
                'message': 'Insufficient balance. Please recharge your wallet.'
            })
        
        # Get target user's phone number
        target_user = User.query.get_or_404(target_user_id)
        if not target_user.phone:
            return jsonify({
                'success': False,
                'message': 'User has not added their phone number.'
            })
            
        # Generate a unique call ID
        call_id = secrets.token_urlsafe(16)
        
        # Store call details in session
        session['pending_call'] = {
            'id': call_id,
            'target_user_id': target_user_id,
            'cost': CALL_COST,
            'timestamp': datetime.utcnow().timestamp()
        }
        
        return jsonify({
            'success': True,
            'phone': target_user.phone,
            'call_id': call_id
        })
            
    except Exception as e:
        app.logger.error(f'Unexpected error in initiate_call: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Failed to initiate call'
        })

@app.route('/complete-call/<string:call_id>', methods=['POST'])
@login_required
def complete_call(call_id):
    db_session = db.session
    try:
        app.logger.info(f'Starting complete_call for call_id: {call_id}')
        
        # Start a new session with fresh state
        db_session.rollback()
        
        # Get call data from request JSON with proper error handling
        if not request.is_json:
            app.logger.error('Request is not JSON')
            return jsonify({
                'success': False,
                'message': 'Request must be JSON',
                'error': 'invalid_content_type'
            }), 400
            
        try:
            call_data = request.get_json(force=True)
            if not call_data or not isinstance(call_data, dict):
                raise ValueError('Invalid JSON data')
        except Exception as e:
            app.logger.error(f'Error parsing JSON data: {str(e)}')
            return jsonify({
                'success': False,
                'message': 'Invalid JSON data',
                'error': 'invalid_json'
            }), 400
            
        app.logger.debug(f'Received call data: {call_data}')
            
        # Validate call duration
        try:
            call_duration = int(call_data.get('duration', 0))
            if call_duration < 0:
                raise ValueError('Duration cannot be negative')
        except (ValueError, TypeError) as e:
            app.logger.error(f'Invalid call duration: {call_data.get("duration")}')
            return jsonify({
                'success': False,
                'message': 'Invalid call duration',
                'error': 'invalid_duration'
            }), 400
            
        # Validate call status
        call_status = call_data.get('status', 'completed')
        valid_statuses = ['completed', 'missed', 'rejected', 'failed']
        if call_status not in valid_statuses:
            app.logger.warning(f'Invalid call status: {call_status}')
            call_status = 'completed'  # Default to completed for invalid statuses
            
        app.logger.info(f'Processing call completion - Duration: {call_duration}s, Status: {call_status}')
        
        # Get pending call details from session with validation
        pending_call = session.get('pending_call')
        if not pending_call:
            app.logger.warning('No pending call found in session')
            return jsonify({
                'success': False,
                'message': 'No active call session found. Please initiate a new call.',
                'error': 'no_pending_call'
            }), 400
            
        if not isinstance(pending_call, dict) or 'id' not in pending_call:
            app.logger.error(f'Invalid pending call data structure: {pending_call}')
            session.pop('pending_call', None)  # Clear invalid data
            return jsonify({
                'success': False,
                'message': 'Invalid call session data. Please try again.',
                'error': 'invalid_call_data'
            }), 400
            
        if pending_call.get('id') != call_id:
            app.logger.warning(f'Call ID mismatch. Expected: {call_id}, Got: {pending_call.get("id")}')
            return jsonify({
                'success': False,
                'message': 'Call session mismatch. Please try again.',
                'error': 'call_id_mismatch'
            }), 400
        
        # Validate call timestamp
        try:
            call_timestamp = pending_call.get('timestamp')
            if not call_timestamp:
                raise ValueError('Missing timestamp in pending call data')
                
            call_time = datetime.fromtimestamp(float(call_timestamp))
            time_since_call = (datetime.utcnow() - call_time).total_seconds()
            max_call_age = 1800  # 30 minutes in seconds
            
            if time_since_call > max_call_age:
                session.pop('pending_call', None)
                app.logger.warning(f'Call session expired. Call ID: {call_id}, Call time: {call_time}, Age: {time_since_call:.1f}s')
                return jsonify({
                    'success': False,
                    'message': 'Call session expired. Please initiate a new call.',
                    'error': 'call_session_expired',
                    'call_age_seconds': time_since_call,
                    'max_call_age_seconds': max_call_age
                }), 400
                
            if time_since_call < 0:
                app.logger.warning(f'Invalid future call time. Call ID: {call_id}, Call time: {call_time}, Current time: {datetime.utcnow()}')
                # Don't fail for small time sync issues, just log a warning
                
        except (ValueError, TypeError) as e:
            app.logger.error(f'Error validating call timestamp: {str(e)}, Timestamp: {pending_call.get("timestamp")}')
            session.pop('pending_call', None)
            return jsonify({
                'success': False,
                'message': 'Invalid call session data. Please try again.',
                'error': 'invalid_timestamp'
            }), 400
            
        CALL_COST = float(pending_call.get('cost', 2.5))  # Default to 2.5 if not set
        target_user_id = pending_call.get('target_user_id')
        
        app.logger.info(f'Processing call cost: ₹{CALL_COST}, Target User ID: {target_user_id}')
        
        # Start a new transaction with row-level locking
        with db_session.begin_nested():
            try:
                # Get user with row-level lock to prevent race conditions
                user = User.query.with_for_update().get(current_user.id)
                if not user:
                    raise ValueError('User not found')
                
                # Get target user
                target_user = User.query.get(target_user_id)
                if not target_user:
                    raise ValueError('Target user not found')
                
                # Get current balance with proper type handling
                current_balance = float(user.wallet_balance or 0.0)
                
                app.logger.info(f'User {user.id} current balance: ₹{current_balance}, Call cost: ₹{CALL_COST}')
                
                # Verify sufficient balance (double-check)
                if current_balance < CALL_COST:
                    error_msg = f'Insufficient balance. Current: ₹{current_balance}, Required: ₹{CALL_COST}'
                    app.logger.warning(error_msg)
                    raise ValueError(error_msg)
                
                # Calculate new balance with proper rounding
                new_balance = round(current_balance - CALL_COST, 2)
                
                # Update user's balance
                user.wallet_balance = new_balance
                db_session.add(user)
                
                # Create call record
                call_record = Call(
                    caller_id=user.id,
                    callee_id=target_user.id,
                    call_id=call_id,
                    duration=call_duration,
                    status=call_status,
                    cost=CALL_COST,
                    timestamp=datetime.utcnow()
                )
                db_session.add(call_record)
                
                # Create transaction record for caller (deduction)
                caller_transaction = Transaction(
                    user_id=user.id,
                    amount=-CALL_COST,  # Negative amount for deduction
                    description=f'Call charge for contacting {target_user.full_name} (ID: {target_user.id})',
                    transaction_type='call_charge',
                    status='completed',
                    reference_id=call_id,
                    metadata={
                        'call_duration_seconds': call_duration,
                        'callee_id': target_user.id,
                        'callee_name': target_user.full_name,
                        'call_status': call_status,
                        'previous_balance': current_balance,
                        'new_balance': new_balance
                    }
                )
                db_session.add(caller_transaction)
                
                # Commit the nested transaction
                db_session.commit()
                
                # Update the current_user object with the latest balance
                current_user.wallet_balance = new_balance
                
                # Clear the pending call from session
                session.pop('pending_call', None)
                
                # Emit socket.io event to update the UI in real-time
                socketio.emit('wallet_updated', {
                    'user_id': user.id,
                    'new_balance': new_balance,
                    'amount_deducted': CALL_COST,
                    'transaction_id': caller_transaction.id
                }, room=f'user_{user.id}')
                
                app.logger.info(f'Successfully processed call payment. User: {user.id}, Amount: ₹{CALL_COST}, New Balance: {new_balance}, Call ID: {call_id}')
                
                return jsonify({
                    'success': True,
                    'new_balance': new_balance,
                    'amount_deducted': CALL_COST,
                    'transaction_id': caller_transaction.id,
                    'call_id': call_id
                })
                
            except ValueError as ve:
                db_session.rollback()
                error_msg = f'Validation error in complete_call: {str(ve)}'
                app.logger.error(error_msg)
                return jsonify({
                    'success': False,
                    'redirect': url_for('wallet'),
                    'message': str(ve)
                }), 400
                
            except Exception as e:
                db_session.rollback()
                error_msg = f'Error in complete_call: {str(e)}'
                app.logger.error(error_msg, exc_info=True)
                return jsonify({
                    'success': False,
                    'message': 'An error occurred while processing your call. Please try again.',
                    'error': str(e)
                }), 500
                
    except Exception as e:
        if 'db_session' in locals():
            db_session.rollback()
        error_msg = f'Unexpected error in complete_call: {str(e)}'
        app.logger.error(error_msg, exc_info=True)
        return jsonify({
            'success': False,
            'message': 'An unexpected error occurred. Please try again.',
            'error': str(e)
        }), 500

# Wallet routes are now handled by the wallet blueprint
# Note: All wallet routes should be defined in routes/wallet.py

if __name__ == '__main__':
    import sys
    import traceback
    import locale
    
    # Set UTF-8 encoding for console output
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    print("\n--- Application Startup Diagnostics ---")
    print(f"Python Version: {sys.version}")
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    try:
        # Create all tables
        with app.app_context():
            db.create_all()
            # Test database connection
            db.session.execute(text('SELECT 1'))
            db.session.commit()
            
            # Validate database tables
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print("\nDatabase Tables:")
            for table in tables:
                print(f"- {table}")
            
            print("\nDatabase initialization successful")
    except Exception as e:
        print("\n--- DATABASE ERROR ---")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
    
    # Socket.IO event handlers (optional)
USE_WEBSOCKETS = False  # Set to False to disable WebSockets

if USE_WEBSOCKETS:
    @socketio.on('connect')
    def handle_connect():
        try:
            if not current_user.is_authenticated:
                app.logger.warning(f'Unauthenticated connection attempt from {request.sid}')
                return False  # Reject the connection
                
            app.logger.info(f'Client connected: {request.sid}, User: {current_user.id if current_user.is_authenticated else "Anonymous"}')
            
            # Update user's online status
            if current_user.is_authenticated:
                user = User.query.get(current_user.id)
                if user:
                    user.is_online = True
                    user.last_seen = datetime.utcnow()
                    db.session.commit()
                    
                    # Broadcast user's online status
                    socketio.emit('user_status', {
                        'user_id': user.id,
                        'is_online': True,
                        'last_seen': user.last_seen.isoformat()
                    }, namespace='/')
                    
        except Exception as e:
            app.logger.error(f'Error in handle_connect: {str(e)}', exc_info=True)
            return False

@socketio.on('disconnect')
def handle_disconnect():
    try:
        app.logger.info(f'Client disconnected: {request.sid}')
        
        if current_user.is_authenticated:
            user = User.query.get(current_user.id)
            if user:
                user.is_online = False
                user.last_seen = datetime.utcnow()
                db.session.commit()
                
                # Broadcast user's offline status
                socketio.emit('user_status', {
                    'user_id': user.id,
                    'is_online': False,
                    'last_seen': user.last_seen.isoformat()
                }, namespace='/')
                
    except Exception as e:
        app.logger.error(f'Error in handle_disconnect: {str(e)}', exc_info=True)
        try:
            db.session.rollback()
        except:
            pass

@socketio.on('user_online')
def handle_user_online(data):
    """Handle user coming online via WebSocket."""
    try:
        if not current_user.is_authenticated:
            return {'status': 'error', 'message': 'Authentication required'}
            
        user = User.query.get(current_user.id)
        if not user:
            return {'status': 'error', 'message': 'User not found'}
            
        # Update user status
        user.is_online = True
        user.last_seen = datetime.utcnow()
        db.session.commit()
        
        # Broadcast user online status to all connected clients
        socketio.emit('user_status', {
            'user_id': user.id,
            'is_online': True,
            'last_seen': user.last_seen.isoformat(),
            'username': user.username
        }, namespace='/')
        
        app.logger.info(f'User {user.id} is now online')
        return {'status': 'success', 'user_id': user.id}
        
    except Exception as e:
        error_msg = f'Error in handle_user_online: {str(e)}'
        app.logger.error(error_msg, exc_info=True)
        try:
            db.session.rollback()
        except:
            pass
        return {'status': 'error', 'message': str(e)}

@socketio.on('user_offline')
def handle_user_offline(data=None):
    """Handle user going offline via WebSocket.
    
    Args:
        data: Optional data sent with the event (not used, but required by Socket.IO)
    """
    try:
        if not current_user.is_authenticated:
            return {'status': 'error', 'message': 'Authentication required'}
            
        user = User.query.get(current_user.id)
        if not user:
            return {'status': 'error', 'message': 'User not found'}
            
        # Update user status
        user.is_online = False
        user.last_seen = datetime.utcnow()
        db.session.commit()
        
        # Broadcast user offline status to all connected clients
        socketio.emit('user_status', {
            'user_id': user.id,
            'is_online': False,
            'last_seen': user.last_seen.isoformat(),
            'username': user.username
        }, namespace='/')
        
        app.logger.info(f'User {user.id} is now offline')
        return {'status': 'success', 'user_id': user.id}
        
    except Exception as e:
        error_msg = f'Error in handle_user_offline: {str(e)}'
        app.logger.error(error_msg, exc_info=True)
        try:
            db.session.rollback()
        except:
            pass
        return {'status': 'error', 'message': str(e)}

@socketio.on('get_user_status')
def handle_get_user_status(data):
    try:
        if not current_user.is_authenticated:
            return {'status': 'error', 'message': 'Authentication required'}
            
        user_id = data.get('user_id')
        if not user_id:
            return {'status': 'error', 'message': 'User ID is required'}
            
        # Check if the requested user exists and the current user has permission
        user = User.query.get(user_id)
        if not user:
            return {'status': 'error', 'message': 'User not found'}
            
        # Basic permission check - users can only see status of their contacts
        # You may want to adjust this based on your requirements
        if user_id != current_user.id:
            # Check if users are connected/contacts
            is_contact = ContactRequest.query.filter(
                ((ContactRequest.requester_id == current_user.id) & (ContactRequest.requested_id == user_id)) |
                ((ContactRequest.requester_id == user_id) & (ContactRequest.requested_id == current_user.id)),
                ContactRequest.status == 'accepted'
            ).first() is not None
            
            if not is_contact:
                return {'status': 'error', 'message': 'Not authorized'}
        
        response = {
            'status': 'success',
            'user_id': user.id,
            'is_online': user.is_online,
            'last_seen': user.last_seen.isoformat() if user.last_seen else None,
            'username': user.username
        }
        
        emit('user_status_response', response, room=request.sid)
        return response
        
    except Exception as e:
        error_msg = f'Error in get_user_status handler: {str(e)}'
        app.logger.error(error_msg, exc_info=True)
        emit('user_status_error', {'message': str(e)}, room=request.sid)
        return {'status': 'error', 'message': str(e)}
        db.session.rollback()

@socketio.on('user_logout')
def handle_user_logout():
    """Handle explicit logout from client"""
    try:
        if hasattr(current_user, 'id'):
            user_id = current_user.id
            app.logger.info(f'User {user_id} initiated logout via socket')
            
            # Update user status
            user = User.query.get(user_id)
            if user:
                user.authenticated = False
                user.is_online = False
                user.update_last_seen()
                db.session.commit()
                
            # Leave all rooms
            leave_room(f'user_{user_id}')
            
            # Acknowledge the logout
            emit('logout_acknowledged', {'status': 'success'})
            
    except Exception as e:
        app.logger.error(f'Error during user_logout: {str(e)}')
        db.session.rollback()
        emit('logout_acknowledged', {'status': 'error', 'message': str(e)})

@socketio.on('join')
def on_join(data):
    try:
        room = data.get('room')
        if not room:
            emit('join_error', {'error': 'No room specified'})
            return
            
        # Get list of rooms this client is in
        rooms = socketio.server.rooms(request.sid)
        
        # Don't join if already in the room
        if room in rooms:
            emit('join_success', {'room': room, 'status': 'already_joined'})
            return
            
        # Join the room
        join_room(room)
        print(f'Client {request.sid} joined room: {room}')
        
        # Notify client of successful join
        emit('join_success', {'room': room, 'status': 'joined'})
        
    except Exception as e:
        error_msg = str(e)
        print(f'Error in join event: {error_msg}')
        import traceback
        traceback.print_exc()
        emit('join_error', {'error': error_msg})

@socketio.on('leave')
def on_leave(data):
    try:
        room = data.get('room')
        if not room:
            emit('leave_error', {'error': 'No room specified'})
            return
            
        # Only leave if in the room
        rooms = socketio.server.rooms(request.sid)
        if room not in rooms:
            emit('leave_error', {'error': 'Not in room', 'room': room})
            return
            
        # Leave the room
        leave_room(room)
        print(f'Client {request.sid} left room: {room}')
        
        # Notify client of successful leave
        emit('leave_success', {'room': room})
        
    except Exception as e:
        error_msg = str(e)
        print(f'Error in leave event: {error_msg}')
        import traceback
        traceback.print_exc()
        emit('leave_error', {'error': error_msg})

@app.route('/portfolio/project/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    user = project.user
    return render_template('portfolio/project_details.html', project=project, user=user)

# Template context processor
@app.context_processor
def inject_defaults():
    return {
        'average_rating': 0.0,
        'total_reviews': 0,
        'portfolio': None,
        'reviews': []
    }

# Start the server
@app.route('/update-session-balance', methods=['POST'])
@login_required
def update_session_balance():
    try:
        data = request.get_json()
        if not data or 'balance' not in data:
            return jsonify({
                'success': False,
                'message': 'Missing balance data'
            })
            
        new_balance = float(data['balance'])
        
        # Get fresh user object from database
        user = User.query.get(current_user.id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            })
            
        # Update user's balance in database
        user.wallet_balance = new_balance
        db.session.add(user)
        db.session.commit()
        
        # Update current_user object
        current_user.wallet_balance = new_balance
        
        return jsonify({
            'success': True,
            'balance': new_balance
        })
        
    except Exception as e:
        app.logger.error(f'Error updating session balance: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Failed to update balance'
        })

# Debug route to check upload configuration
@app.route('/debug/upload-config')
def debug_upload_config():
    ensure_upload_folders()
    profile_pics_dir = os.path.join(app.root_path, 'static', 'uploads', 'profile_pics')
    return jsonify({
        'UPLOAD_FOLDER': app.config.get('UPLOAD_FOLDER'),
        'PROFILE_PICS_FOLDER': app.config.get('PROFILE_PICS_FOLDER'),
        'profile_pics_exists': os.path.exists(profile_pics_dir),
        'files': os.listdir(profile_pics_dir) if os.path.exists(profile_pics_dir) else []
    })

@app.route('/debug/check-photo')
def debug_check_photo():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Not logged in'})
    profile_pics_dir = os.path.join(app.root_path, 'static', 'uploads', 'profile_pics')
    try:
        return jsonify({
            'username': current_user.username,
            'photo': current_user.photo,
            'photo_exists': os.path.exists(os.path.join(profile_pics_dir, current_user.photo)) if current_user.photo else False,
            'profile_pics_folder': profile_pics_dir,
            'files_in_folder': os.listdir(profile_pics_dir)
        })
    except Exception as e:
        files = f"Error listing directory: {str(e)}"
    
    return jsonify({
        'UPLOAD_FOLDER': app.config.get('UPLOAD_FOLDER'),
        'PROFILE_PICS_FOLDER': app.config.get('PROFILE_PICS_FOLDER'),
        'root_path': app.root_path,
        'static_folder': app.static_folder,
        'profile_pics_dir': profile_pics_dir,
        'profile_pics_dir_exists': os.path.exists(profile_pics_dir),
        'files_in_profile_pics': files
    })

# Profile pictures are served by the route at line 95 (@app.route('/profile_pic/<filename>'))
# The duplicate route has been removed to prevent conflicts

def configure_logging():
    """Configure application logging."""
    if not app.debug:
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        file_handler = RotatingFileHandler(
            'logs/fuetime.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler],
            format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        
        # Also add to app logger
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        
        # Log startup information
        app.logger.info('=' * 80)
        app.logger.info('Fuetime Server Starting...')
        app.logger.info(f'Environment: {app.config["ENV"]}')
        app.logger.info(f'Debug Mode: {app.debug}')
        app.logger.info(f'Database URI: {app.config["SQLALCHEMY_DATABASE_URI"]}')
        app.logger.info('=' * 80)

if __name__ == '__main__':
    try:
        # Configure logging
        configure_logging()
        
        # Ensure upload directories exist
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            os.makedirs(app.config['PROFILE_PICS_FOLDER'], exist_ok=True)
            app.logger.info('Upload directories verified')
        except Exception as e:
            app.logger.error(f'Failed to create upload directories: {str(e)}')
            raise
            
        # Initialize SocketIO with the app
        if socketio is None:
            app.logger.error("Fatal: socketio is not initialized")
            raise RuntimeError("Socket.IO not properly initialized")
            
        try:
            socketio.init_app(app,
                           cors_allowed_origins="*",
                           async_mode='gevent',
                           engineio_logger=True,
                           logger=True,
                           ping_timeout=60,
                           manage_session=False)
        except Exception as e:
            app.logger.error(f"Error initializing Socket.IO: {e}")
            raise
            
        # Register socket.io event handlers
        init_socketio_handlers()
        
        # Start the SocketIO server
        app.logger.info('Starting SocketIO server...')
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=app.debug,
            use_reloader=app.debug,
            allow_unsafe_werkzeug=True,
            log_output=True
        )
        
    except Exception as run_err:
        error_msg = '\n--- APPLICATION RUN ERROR ---\n'
        error_msg += f'Error: {run_err}\n'
        error_msg += '\n'.join(traceback.format_exception(type(run_err), run_err, run_err.__traceback__))
        
        # Log to file if possible, otherwise print to console
        if 'app' in locals() and hasattr(app, 'logger'):
            app.logger.critical(error_msg)
        else:
            print(error_msg, file=sys.stderr)
            
        sys.exit(1)

        # Start the SocketIO server
        app.logger.info('Starting SocketIO server...')
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=app.debug,
            use_reloader=app.debug,
            allow_unsafe_werkzeug=True,
            log_output=True
        )
        
    except Exception as run_err:
        error_msg = '\n--- APPLICATION RUN ERROR ---\n'
        error_msg += f'Error: {run_err}\n'
        error_msg += '\n'.join(traceback.format_exception(type(run_err), run_err, run_err.__traceback__))
        
        # Log to file if possible, otherwise print to console
        if 'app' in locals() and hasattr(app, 'logger'):
            app.logger.critical(error_msg)
        else:
            print(error_msg, file=sys.stderr)
            
        sys.exit(1)
