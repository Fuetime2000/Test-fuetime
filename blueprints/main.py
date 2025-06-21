from flask import Blueprint, render_template, request, jsonify, current_app, render_template_string
from models.user import User
from extensions import db
from flask_login import current_user

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Main landing page with pagination support"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 12  # Number of users per page
        
        # Log the request
        current_app.logger.info(f"Processing request for page {page}")
        
        # Debug: Log all users in the database
        all_users = User.query.all()
        current_app.logger.debug(f"Users in database: {[{'id': u.id, 'email': u.email, 'active': u.active} for u in all_users]}")
        
        # Query for active users with pagination
        users_pagination = User.query.filter(User.active == True).order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False)
            
        current_app.logger.debug(f"Found {users_pagination.total} active users, page {page}/{users_pagination.pages}")
        
        # Debug: Log the users being returned
        if users_pagination.items:
            current_app.logger.debug(f"Users in this page: {[u.id for u in users_pagination.items]}")
        else:
            current_app.logger.warning("No active users found in the query")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests, return JSON with HTML and pagination info
            if not users_pagination.items:
                current_app.logger.warning("No active users found in the database")
                html = ''
            else:
                current_app.logger.debug(f"Rendering {len(users_pagination.items)} user cards")
                # Render the profile cards using the template
                try:
                    from datetime import datetime
                    html = render_template('components/profile_cards.html', 
                                        users=users_pagination.items,
                                        current_user=current_user,
                                        now=datetime.utcnow())
                    current_app.logger.debug(f"Rendered HTML length: {len(html) if html else 0}")
                except Exception as e:
                    current_app.logger.error(f"Error rendering template: {str(e)}", exc_info=True)
                    html = ''
            
            response_data = {
                'html': html,
                'has_more': users_pagination.has_next,
                'total': users_pagination.total,
                'page': page,
                'per_page': per_page
            }
            current_app.logger.debug(f"Sending response with {len(html)} characters of HTML")
            return jsonify(response_data)
        
        # For regular requests, render the full page with users
        from datetime import datetime
        return render_template('index.html', 
                            users=users_pagination.items, 
                            pagination=users_pagination,
                            has_more=users_pagination.has_next,
                            now=datetime.utcnow())
    except Exception as e:
        error_msg = f"Error in index route: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'error': 'Failed to load users',
                'details': str(e),
                'html': '',
                'has_more': False
            }), 500
            
        # Return empty users list in case of error for regular requests
        return render_template('index.html', users=[], has_more=False, error=str(e))
