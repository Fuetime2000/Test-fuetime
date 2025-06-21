from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from flask import current_app
from extensions import socketio, db
from models.user import User
from models.transaction import Transaction
from models.Call import Call  # Import the Call model
from datetime import datetime
import uuid
import logging
from functools import wraps

# Set up logging
logger = logging.getLogger(__name__)

def socket_auth_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return {'error': 'Authentication required'}, 401
        return f(*args, **kwargs)
    return wrapped

def register_socketio_events():
    """Register all Socket.IO event handlers."""
    @socketio.on('connect')
    @socket_auth_required
    def handle_connect():
        if current_user.is_authenticated:
            join_room(f'user_{current_user.id}')
            emit('status', {'user_id': current_user.id, 'status': 'online'}, broadcast=True, namespace='/')
            print(f"User {current_user.id} connected to WebSocket")
        else:
            print("Unauthenticated WebSocket connection attempt")

    @socketio.on('disconnect')
    @socket_auth_required
    def handle_disconnect():
        if current_user.is_authenticated:
            leave_room(f'user_{current_user.id}')
            emit('status', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True, namespace='/')
            print(f"User {current_user.id} disconnected from WebSocket")

    @socketio.on('join')
    @socket_auth_required
    def on_join(data):
        try:
            room = data.get('room')
            user_id = data.get('user_id')
            
            if not room:
                return {'success': False, 'error': 'Room name is required'}
                
            # Validate that the user is allowed to join this room
            if room.startswith('user_') and user_id:
                room_user_id = room.replace('user_', '')
                if str(user_id) != room_user_id and not current_user.is_authenticated:
                    return {'success': False, 'error': 'Unauthorized'}
            
            join_room(room)
            print(f"User {user_id} joined room: {room}")
            return {'success': True}
            
        except Exception as e:
            print(f"Error in on_join: {str(e)}")
            return {'success': False, 'error': str(e)}

    @socketio.on('leave')
    @socket_auth_required
    def on_leave(data):
        room = data.get('room')
        if room:
            leave_room(room)
            print(f"User {current_user.id} left room: {room}")

@socketio.on('typing')
def handle_typing(data):
    room = data.get('room')
    if room and current_user.is_authenticated:
        emit('user_typing', {
            'user_id': current_user.id,
            'typing': data.get('typing', False)
        }, room=room)

@socketio.on('profile_updated')
def handle_profile_updated(data):
    """Handle profile update events"""
    user_id = data.get('user_id')
    if not user_id:
        return
        
    # Forward the event to the specific user's room
    emit('profile_updated', {
        'user_id': user_id,
        'success': data.get('success', True),
        'message': data.get('message', 'Profile updated successfully'),
        'error': data.get('error')
    }, room=f'user_{user_id}')


@socketio.on('initiate_call')
def handle_initiate_call(data):
    """Handle call initiation request"""
    app = current_app._get_current_object()
    
    try:
        if not current_user.is_authenticated:
            emit('call_initiated', {'success': False, 'error': 'Authentication required'})
            return
        
        recipient_id = data.get('recipient_id')
        call_type = data.get('type', 'audio')  # audio or video
        
        if not recipient_id:
            emit('call_initiated', {'success': False, 'error': 'Recipient ID is required'})
            return
        
        # Start a new database session
        with app.app_context():
            recipient = User.query.get(recipient_id)
            if not recipient:
                emit('call_initiated', {'success': False, 'error': 'Recipient not found'})
                return
            
            # Get call cost (configurable)
            call_cost = 2.5  # ₹2.50 per call
            
            # Check if user has sufficient balance
            if not hasattr(current_user, 'wallet_balance') or current_user.wallet_balance is None:
                current_user.wallet_balance = 0.0
                
            if float(current_user.wallet_balance) < call_cost:
                emit('call_initiated', {
                    'success': False, 
                    'error': 'Insufficient balance',
                    'required': call_cost,
                    'current_balance': float(current_user.wallet_balance)
                })
                return
    
            # Start a transaction with proper error handling
            try:
                # Get fresh user with row-level lock
                user = User.query.with_for_update().get(current_user.id)
                if not user:
                    raise ValueError('User not found')
                
                # Calculate new balance with proper float handling
                call_cost = round(float(call_cost), 2)
                old_balance = float(user.wallet_balance) if user.wallet_balance is not None else 0.0
                new_balance = round(old_balance - call_cost, 2)
                
                # Update user's balance
                user.wallet_balance = new_balance
                
                # Generate a unique call ID
                call_id = str(uuid.uuid4())
                
                # Create call record
                call = Call(
                    call_id=call_id,
                    caller_id=current_user.id,
                    callee_id=recipient_id,
                    status='initiated',
                    cost=call_cost
                )
                
                # Create transaction record
                transaction = Transaction(
                    user_id=user.id,
                    amount=-call_cost,  # Negative amount for deduction
                    description=f'Call charge for {call_type} call to {recipient.phone or recipient.email}'
                )
                
                # Add records to session
                db.session.add(call)
                db.session.add(transaction)
                db.session.commit()
                
                # Update current_user balance in memory
                current_user.wallet_balance = new_balance
                
                # Log the successful transaction
                logger.info(f'Call charge processed. User: {user.id}, Amount: {call_cost}, New Balance: {new_balance}')
                
                # Notify recipient about the incoming call
                emit('incoming_call', {
                    'caller_id': current_user.id,
                    'caller_name': current_user.full_name or current_user.email.split('@')[0],
                    'call_type': call_type,
                    'call_id': call.call_id,
                    'call_cost': call_cost
                }, room=f'user_{recipient_id}')
                
                # Send success response to caller
                emit('call_initiated', {
                    'success': True,
                    'message': 'Call initiated successfully',
                    'call_id': call.call_id,
                    'call_cost': call_cost,
                    'new_balance': new_balance,
                    'phone_number': recipient.phone  # Send recipient's phone number
                })
                
            except Exception as e:
                db.session.rollback()
                logger.error(f'Error processing call: {str(e)}', exc_info=True)
                emit('call_initiated', {
                    'success': False,
                    'error': f'Failed to initiate call: {str(e)}',
                    'current_balance': float(getattr(current_user, 'wallet_balance', 0.0))
                })
    
    except Exception as e:
        logger.error(f'Unexpected error in handle_initiate_call: {str(e)}', exc_info=True)
        emit('call_initiated', {
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        })
