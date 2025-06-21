from .main import bp as main_bp
from .auth import bp as auth_bp
from .profile import bp as profile_bp
from .messages import bp as messages_bp
from .test_route import bp as test_bp
from routes.portfolio import portfolio_bp
from routes.review import review_bp

# Dictionary of all blueprints with their URL prefixes
blueprints = {
    'main': (main_bp, ''),  # No URL prefix for main blueprint
    'auth': (auth_bp, '/auth'),
    'profile': (profile_bp, '/profile'),
    'messages': (messages_bp, '/messages'),
    'portfolio': (portfolio_bp, '/portfolio'),
    'review': (review_bp, '/review'),
    'test': (test_bp, '/test')
}

def init_app(app):
    """Register all blueprints with the Flask application."""
    # Track registered blueprints to prevent duplicates
    registered = set()
    
    for name, (bp, url_prefix) in blueprints.items():
        if name not in registered:
            app.register_blueprint(bp, url_prefix=url_prefix)
            registered.add(name)
    
    return app
