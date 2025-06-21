"""
WSGI config for Fuetime application.

This module contains the WSGI application used by the production server.
"""
import os
from app import app, socketio

# The application instance is already created in app.py

# This is the WSGI callable
application = app

# Socket.IO initialization
socketio.init_app(application, cors_allowed_origins="*")

if __name__ == "__main__":
    # Run the application with SocketIO support
    socketio.run(
        app,
        host=os.environ.get('HOST', '0.0.0.0'),
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
        use_reloader=True
    )
