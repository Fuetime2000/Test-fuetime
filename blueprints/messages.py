from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from datetime import datetime

from models.message import Message
from models.user import User
from extensions import db, socketio

bp = Blueprint('messages', __name__)

@bp.route('/messages')
@login_required
def messages():
    # Get list of users for the sidebar
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('messages/index.html', users=users)

@bp.route('/messages/<int:recipient_id>')
@login_required
def chat(recipient_id):
    recipient = User.query.get_or_404(recipient_id)
    
    # Mark messages as read
    Message.query.filter_by(
        sender_id=recipient_id,
        recipient_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    # Get message history
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) |
        ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    return render_template('messages/chat.html', 
                         recipient=recipient, 
                         messages=messages)

# SocketIO event handlers
def register_socket_events():
    """Register Socket.IO event handlers for messages."""
    @socketio.on('connect')
    @login_required
    def handle_connect():
        join_room(f'user_{current_user.id}')
        emit('status', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)
    
    @socketio.on('disconnect')
    @login_required
    def handle_disconnect():
        leave_room(f'user_{current_user.id}')
        emit('status', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)
    
    @socketio.on('message')
    @login_required
    def handle_message(data):
        recipient_id = data.get('recipient_id')
        content = data.get('content')
        
        if not recipient_id or not content:
            return
            
        # Save message to database
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient_id,
            content=content,
            timestamp=datetime.utcnow()
        )
        db.session.add(message)
        db.session.commit()
        
        # Emit to both sender and recipient
        emit('new_message', {
            'id': message.id,
            'sender_id': current_user.id,
            'recipient_id': recipient_id,
            'content': content,
            'timestamp': message.timestamp.isoformat(),
            'sender_name': current_user.name,
            'sender_avatar': current_user.profile_pic or url_for('static', filename='img/default-avatar.png')
        }, room=f'user_{recipient_id}')
        
        # Also send back to sender for their own UI update
        emit('new_message', {
            'id': message.id,
            'sender_id': current_user.id,
            'recipient_id': recipient_id,
            'content': content,
            'timestamp': message.timestamp.isoformat(),
            'sender_name': 'You',
            'sender_avatar': current_user.profile_pic or url_for('static', filename='img/default-avatar.png')
        }, room=f'user_{current_user.id}')

# Socket events will be registered after app and socketio are fully initialized
