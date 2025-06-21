from flask import Blueprint, jsonify
from models.user import User
from extensions import db

bp = Blueprint('test', __name__)

@bp.route('/test')
def test_route():
    try:
        # Test database connection
        users = User.query.limit(5).all()
        users_data = [{'id': u.id, 'email': u.email, 'name': u.full_name} for u in users]
        
        return jsonify({
            'status': 'success',
            'users': users_data,
            'total_users': len(users_data)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
