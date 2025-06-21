from flask import Blueprint, render_template, request, g, redirect, url_for, flash, jsonify, current_app, session
from flask_login import login_required, current_user, login_user, logout_user
from datetime import datetime
# Import models
from models import (
    User, Message, Portfolio, ContactRequest, Review, 
    HelpRequest, UserInteraction, Transaction, UserBehavior, 
    FraudAlert, Donation, Call, Project, Technology, PortfolioRating
)
from extensions import db, socketio, csrf
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import traceback

main_bp = Blueprint('main', __name__)

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'doc', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main_bp.route('/')
def index():
    try:
        page = request.args.get('page', 1, type=int)
        category = request.args.get('category', '')
        location = request.args.get('location', '')
        q = request.args.get('q', '')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Only show worker profiles
        users = User.query.filter_by(is_admin=False, user_type='worker')
        
        # Apply filters
        if q:
            users = users.filter(
                db.or_(
                    db.func.lower(User.skills).like(f'%{q.lower()}%'),
                    db.func.lower(User.work).like(f'%{q.lower()}%'),
                    db.func.lower(User.full_name).like(f'%{q.lower()}%')
                )
            )
        
        if category:
            users = users.filter(db.func.lower(User.categories).like(f'%{category.lower()}%'))
        
        if location:
            users = users.filter(
                db.or_(
                    db.func.lower(User.current_location).like(f'%{location.lower()}%'),
                    db.func.lower(User.live_location).like(f'%{location.lower()}%')
                )
            )
        
        # Order by rating and get paginated results
        users = users.order_by(User.average_rating.desc())
        total = users.count()
        per_page = 9
        offset = (page - 1) * per_page
        users = users.offset(offset).limit(per_page).all()
        
        if is_ajax:
            # Return HTML for user cards only
            html = render_template('components/profile_cards.html',
                                users=users,
                                now=datetime.now())
            return jsonify({
                'html': html,
                'has_more': total > offset + per_page
            })
        
        # Get unique categories and locations for filters
        categories_query = db.session.query(User.categories).distinct()
        categories_list = [cat[0] for cat in categories_query if cat[0]]
        categories = sorted(set(','.join(categories_list).split(','))) if categories_list else []
        
        locations_query = db.session.query(User.current_location).distinct()
        locations_list = [loc[0] for loc in locations_query if loc[0]]
        locations = sorted(set(locations_list)) if locations_list else []
        
        return render_template('index.html',
                             users=users,
                             categories=categories,
                             locations=locations,
                             now=datetime.now(),
                             total_users=total)
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        db.session.rollback()
        if is_ajax:
            return jsonify({'error': str(e)}), 500
        return render_template('500.html'), 500

# Profile route
@main_bp.route('/profile/<int:user_id>')
def profile(user_id):
    try:
        user = User.query.get_or_404(user_id)
        # Get the user's portfolio
        portfolio = Portfolio.query.filter_by(user_id=user_id).first()
        
        # Increment profile views if the viewer is not the profile owner
        if current_user.is_authenticated and current_user.id != user.id:
            user.profile_views += 1
            db.session.commit()
        
        # Update rating in case there are any pending review calculations
        user.update_rating()
        db.session.commit()
        
        return render_template('profile.html', user=user, portfolio=portfolio)
    except Exception as e:
        print(f"Error in profile route: {str(e)}")
        return render_template('500.html'), 500

# Chat route
@main_bp.route('/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):
    try:
        if not user_id or user_id == 'NaN':
            flash('Invalid user ID', 'error')
            return redirect(url_for('main.index'))
            
        receiver = User.query.get_or_404(user_id)
        
        if request.method == 'POST':
            content = request.form.get('content', '').strip()
            file = request.files.get('attachment')
            attachment_url = None
            
            if file and file.filename:
                if not allowed_file(file.filename):
                    return jsonify({'status': 'error', 'message': 'Invalid file type. Allowed types: ' + ', '.join(ALLOWED_EXTENSIONS)}), 400
                    
                # Check file size
                file.seek(0, 2)  # Seek to end of file
                file_size = file.tell()
                file.seek(0)  # Reset file pointer
                
                if file_size > 16 * 1024 * 1024:  # 16MB
                    return jsonify({'status': 'error', 'message': 'File size too large. Maximum size is 16MB'}), 413
                    
                try:
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat', filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    file.save(file_path)
                    attachment_url = url_for('static', filename=f'uploads/chat/{filename}')
                except Exception as e:
                    print(f'Error saving attachment: {str(e)}')
                    return jsonify({'status': 'error', 'message': 'Error uploading file'}), 400
            
            if content or attachment_url:
                try:
                    message = Message(
                        sender_id=current_user.id,
                        receiver_id=user_id,
                        content=content,
                        attachment=attachment_url
                    )
                    db.session.add(message)
                    db.session.commit()
                    
                    message_data = {
                        'status': 'success',
                        'content': content,
                        'attachment_url': attachment_url,
                        'sender_id': current_user.id,
                        'sender_photo': current_user.photo or '/static/images/default-avatar.png',
                        'sender_name': current_user.full_name,
                        'timestamp': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    socketio.emit('receive_message', message_data, room=f'user_{current_user.id}')
                    socketio.emit('receive_message', message_data, room=f'user_{user_id}')
                    
                    return jsonify(message_data)
                except Exception as e:
                    print(f'Error saving message: {str(e)}')
                    db.session.rollback()
                    return jsonify({'status': 'error', 'message': 'Error saving message'}), 500
            
            return jsonify({'status': 'error', 'message': 'No content provided'}), 400
        
        # Get chat history
        messages = Message.query.filter(
            db.or_(
                db.and_(Message.sender_id == current_user.id, Message.receiver_id == user_id),
                db.and_(Message.sender_id == user_id, Message.receiver_id == current_user.id)
            )
        ).order_by(Message.created_at.asc()).all()
        
        # Mark messages as read
        unread_messages = Message.query.filter_by(
            sender_id=user_id,
            receiver_id=current_user.id,
            is_read=False
        ).all()
        
        for msg in unread_messages:
            msg.is_read = True
        db.session.commit()
        
        # Get receiver user info
        receiver = User.query.get_or_404(user_id)

        return render_template('chat.html', 
                            receiver=receiver, 
                            messages=messages,
                            current_userid=current_user.id,
                            receiverid=user_id)
        
    except Exception as e:
        print(f'Error in chat route: {str(e)}')
        import traceback
        print(f'Traceback: {traceback.format_exc()}')
        flash('An error occurred while loading the chat.', 'error')
        return redirect(url_for('main.index'))

# Edit profile route
@main_bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    try:
        if request.method == 'POST':
            # Start transaction
            try:
                # Get form data
                full_name = request.form.get('full_name')
                email = request.form.get('email')
                phone = request.form.get('phone')
                bio = request.form.get('bio')
                education = request.form.get('education')
                work = request.form.get('work')
                skills = request.form.get('skills')
                current_location = request.form.get('current_location')
                payment_type = request.form.get('payment_type')
                
                # Handle payment charge conversion
                payment_charge_str = request.form.get('payment_charge')
                try:
                    payment_charge = float(payment_charge_str) if payment_charge_str else None
                except ValueError:
                    print(f"Invalid payment charge value: {payment_charge_str}")
                    payment_charge = None
                categories = request.form.get('categories')
                
                # Validate unique constraints
                if email != current_user.email:
                    existing_user = User.query.filter_by(email=email).first()
                    if existing_user and existing_user.id != current_user.id:
                        flash('Email address is already in use.', 'error')
                        return redirect(url_for('main.edit_profile'))
                
                if phone != current_user.phone:
                    existing_user = User.query.filter_by(phone=phone).first()
                    if existing_user and existing_user.id != current_user.id:
                        flash('Phone number is already in use.', 'error')
                        return redirect(url_for('main.edit_profile'))
                
                # Debug print form data
                print("Received form data:")
                for key in request.form:
                    print(f"{key}: {request.form[key]}")
                
                # Get original values for comparison
                original_values = {
                    'full_name': current_user.full_name or '',
                    'email': current_user.email or '',
                    'phone': current_user.phone or '',
                    'bio': current_user.bio or '',
                    'education': current_user.education or '',
                    'work': current_user.work or '',
                    'skills': current_user.skills or '',
                    'current_location': current_user.current_location or '',
                    'payment_type': current_user.payment_type or '',
                    'payment_charge': current_user.payment_charge or 0,
                    'categories': current_user.categories or ''
                }
                
                # Debug print original values
                print("Original values:")
                for key, value in original_values.items():
                    print(f"{key}: {value}")
                
                # Debug print form values
                print("\nForm values:")
                for key in original_values.keys():
                    value = request.form.get(key, '')
                    if key == 'payment_charge':
                        try:
                            value = float(value) if value else 0
                        except ValueError:
                            value = 0
                    print(f"{key}: {value}")
                
                # Debug print original values
                print("Original values:")
                for key, value in original_values.items():
                    print(f"{key}: {value}")
                
                # Update user fields
                # Required fields with fallback to current values
                current_user.full_name = full_name if full_name else current_user.full_name
                current_user.email = email if email else current_user.email
                current_user.phone = phone if phone else current_user.phone
                
                # Optional fields that can be None/empty
                current_user.bio = bio
                current_user.education = education
                current_user.work = work
                current_user.skills = skills
                current_user.current_location = current_location
                current_user.payment_type = payment_type
                current_user.payment_charge = payment_charge
                current_user.categories = categories
                
                # Check if any changes were made by comparing with original values
                print("\nChecking for changes:")
                changes_made = False
                
                # Compare all fields
                field_changes = {
                    'full_name': (current_user.full_name, original_values['full_name']),
                    'email': (current_user.email, original_values['email']),
                    'phone': (current_user.phone, original_values['phone']),
                    'bio': (current_user.bio or '', original_values['bio']),
                    'education': (current_user.education or '', original_values['education']),
                    'work': (current_user.work or '', original_values['work']),
                    'skills': (current_user.skills or '', original_values['skills']),
                    'current_location': (current_user.current_location or '', original_values['current_location']),
                    'payment_type': (current_user.payment_type or '', original_values['payment_type']),
                    'payment_charge': (current_user.payment_charge, original_values['payment_charge']),
                    'categories': (current_user.categories or '', original_values['categories'])
                }
                
                for field, (current, original) in field_changes.items():
                    if str(current) != str(original):
                        changes_made = True
                        print(f"Change detected in {field}: {original} -> {current}")
                
                print(f"\nChanges made: {changes_made}")
                # Handle photo upload separately since it's a file
                if 'photo' in request.files:
                    photo = request.files['photo']
                    if photo and photo.filename and allowed_file(photo.filename):
                        try:
                            filename = secure_filename(photo.filename)
                            # Create upload directory if it doesn't exist
                            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_photos')
                            os.makedirs(upload_dir, exist_ok=True)
                            # Save the file
                            photo_path = os.path.join(upload_dir, filename)
                            photo.save(photo_path)
                            # Update user's photo field with relative path
                            new_photo_path = f'/static/uploads/profile_photos/{filename}'
                            if new_photo_path != current_user.photo:
                                current_user.photo = new_photo_path
                                changes_made = True
                        except Exception as e:
                            print(f"Error saving profile photo: {e}")
                            import traceback
                            traceback.print_exc()
                
                # Handle date of birth
                dob_str = request.form.get('date_of_birth')
                if dob_str:
                    try:
                        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                        if dob != current_user.date_of_birth:
                            current_user.date_of_birth = dob
                            # Calculate age
                            today = datetime.now().date()
                            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                            current_user.age = age
                            changes_made = True
                    except ValueError as e:
                        print(f"Error parsing date of birth: {e}")
                
                # Handle profile photo upload
                if 'photo' in request.files:
                    photo = request.files['photo']
                    if photo and photo.filename and allowed_file(photo.filename):
                        try:
                            filename = secure_filename(photo.filename)
                            # Create upload directory if it doesn't exist
                            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_photos')
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            # Save the file
                            photo_path = os.path.join(upload_dir, filename)
                            photo.save(photo_path)
                            
                            # Update user's photo field with relative path
                            new_photo_path = f'/static/uploads/profile_photos/{filename}'
                            if new_photo_path != current_user.photo:
                                current_user.photo = new_photo_path
                                changes_made = True
                                print(f"Change detected in photo: {current_user.photo} -> {new_photo_path}")
                        except Exception as e:
                            print(f"Error saving profile photo: {e}")
                            import traceback
                            traceback.print_exc()
                
                # Check if any changes were made by comparing with original values
                print("\nChecking for changes:")
                for key, value in original_values.items():
                    if key == 'payment_charge':
                        try:
                            new_value = float(request.form.get(key, '0')) if request.form.get(key) else None
                        except ValueError:
                            new_value = None
                    else:
                        new_value = request.form.get(key, '')
                    
                    if str(new_value) != str(value):
                        changes_made = True
                        print(f"Change detected in {key}: {value} -> {new_value}")
                        # Update the field
                        if key == 'payment_charge':
                            setattr(current_user, key, new_value)
                        else:
                            setattr(current_user, key, new_value or value)
                
                print(f"\nChanges made: {changes_made}")
                
                # Only save if changes were made
                if changes_made:
                    try:
                        print("Attempting to save changes...")
                        # Mark object as modified
                        db.session.add(current_user)
                        
                        # Print current session state
                        print("Session state before commit:")
                        print(f"Dirty objects: {db.session.dirty}")
                        print(f"New objects: {db.session.new}")
                        
                        # Commit changes
                        db.session.commit()
                        print("Changes committed successfully")
                        
                        # Emit socket event for profile update
                        room = f'user_{current_user.id}'
                        socketio.emit('profile_updated', {
                            'user_id': current_user.id,
                            'timestamp': datetime.now().isoformat(),
                            'success': True
                        }, room=room)
                        
                        flash('Profile updated successfully!', 'success')
                    except Exception as commit_error:
                        db.session.rollback()
                        print(f"Error committing changes: {commit_error}")
                        print("Full error details:")
                        import traceback
                        traceback.print_exc()
                        
                        # Print object state
                        print("Current user object state:")
                        for attr in ['full_name', 'email', 'phone', 'bio', 'education', 'work', 'skills']:
                            print(f"{attr}: {getattr(current_user, attr)}")
                        
                        # Emit error event
                        socketio.emit('profile_updated', {
                            'user_id': current_user.id,
                            'error': str(commit_error),
                            'success': False
                        }, room=f'user_{current_user.id}')
                        
                        flash('An error occurred while saving your changes.', 'error')
                        return redirect(url_for('main.profile', user_id=current_user.id))
                else:
                    print("No changes detected")
                    flash('No changes were made to your profile.', 'info')
                    
            except Exception as e:
                print(f"Error in profile update process: {e}")
                print("Full error details:")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                
                # Emit error event to client
                socketio.emit('profile_updated', {
                    'user_id': current_user.id,
                    'error': str(e),
                    'success': False
                }, room=f'user_{current_user.id}')
                
                flash('An error occurred while saving your changes.', 'error')
            
            return redirect(url_for('main.profile', user_id=current_user.id))
        
        return render_template('edit_profile.html', user=current_user)
        
    except Exception as e:
        print(f"Error in edit_profile route: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        flash('An error occurred while updating your profile.', 'error')
        return redirect(url_for('main.profile', user_id=current_user.id))

# Change password route
@main_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    try:
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not all([current_password, new_password, confirm_password]):
            flash('All password fields are required.', 'error')
            return redirect(url_for('main.account'))
        
        # Check if current password is correct
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('main.account'))
        
        # Check if new passwords match
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('main.account'))
        
        # Check password length
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'error')
            return redirect(url_for('main.account'))
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('main.account'))
        
    except Exception as e:
        print(f"Error in change_password: {str(e)}")
        db.session.rollback()
        flash('An error occurred while changing your password.', 'error')
        return redirect(url_for('main.account'))

# Update notification settings route
@main_bp.route('/account/notifications', methods=['POST'])
@login_required
def notifications():
    try:
        # Get notification settings from form
        email_notifications = request.form.get('email_notifications') == 'on'
        message_notifications = request.form.get('message_notifications') == 'on'
        review_notifications = request.form.get('review_notifications') == 'on'
        
        # Update user settings
        current_user.email_notifications = email_notifications
        current_user.message_notifications = message_notifications
        current_user.review_notifications = review_notifications
        
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Notification settings updated successfully'
            })
        
        flash('Notification settings updated successfully!', 'success')
        return redirect(url_for('main.account'))
        
    except Exception as e:
        print(f"Error in update_notifications: {str(e)}")
        db.session.rollback()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'An error occurred while updating notification settings'
            })
        
        flash('An error occurred while updating notification settings.', 'error')
        return redirect(url_for('main.account'))

# Account settings page route
@main_bp.route('/account', methods=['GET'])
@login_required
def account():
    print("Accessing account route...")
    try:
        # Debug information
        print(f"Current user: {current_user}")
        print(f"User ID: {current_user.id}")
        print(f"User authenticated: {current_user.is_authenticated}")
        
        # Get user's current settings
        user_settings = {
            'email_notifications': getattr(current_user, 'email_notifications', True),
            'message_notifications': getattr(current_user, 'message_notifications', True),
            'review_notifications': getattr(current_user, 'review_notifications', True)
        }
        
        print(f"User settings: {user_settings}")
        
        # Ensure base.html exists
        template_path = os.path.join(current_app.root_path, 'templates', 'base.html')
        if not os.path.exists(template_path):
            print(f"Error: base.html not found at {template_path}")
            raise FileNotFoundError(f"Template base.html not found at {template_path}")
        
        # Try rendering the template
        try:
            rendered = render_template('account.html', user=current_user, settings=user_settings)
            print("Template rendered successfully")
            return rendered
        except Exception as template_error:
            print(f"Template rendering error: {str(template_error)}")
            raise
            
    except Exception as e:
        print(f"Error in account route: {str(e)}")
        print("Full error details:")
        import traceback
        traceback.print_exc()
        
        # Check if the error is related to database
        if 'SQLAlchemy' in str(e) or 'database' in str(e).lower():
            flash('Database error occurred. Please try again later.', 'error')
        else:
            flash('An error occurred while loading account settings.', 'error')
            
        return redirect(url_for('main.profile', user_id=current_user.id))

# Delete account route
@main_bp.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    try:
        password = request.form.get('password')
        if not check_password_hash(current_user.password_hash, password):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Incorrect password'
                })
            flash('Incorrect password', 'error')
            return redirect(url_for('main.account'))

        # Delete user's data
        user_id = current_user.id
        logout_user()

        # Delete user's messages
        Message.query.filter(
            db.or_(
                Message.sender_id == user_id,
                Message.receiver_id == user_id
            )
        ).delete()

        # Delete user's portfolio
        Portfolio.query.filter_by(user_id=user_id).delete()

        # Delete user account
        User.query.filter_by(id=user_id).delete()

        db.session.commit()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': 'Your account has been deleted successfully'
            })

        flash('Your account has been deleted successfully', 'success')
        return redirect(url_for('main.index'))

    except Exception as e:
        print(f"Error in delete_account: {str(e)}")
        db.session.rollback()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'An error occurred while deleting your account'
            })

        flash('An error occurred while deleting your account', 'error')
        return redirect(url_for('main.account'))

# Track registered blueprints to prevent duplicates
_registered_blueprints = set()

def register_blueprint(app, blueprint, url_prefix=''):
    """Helper function to register a blueprint only once"""
    if blueprint.name not in _registered_blueprints:
        app.register_blueprint(blueprint, url_prefix=url_prefix)
        _registered_blueprints.add(blueprint.name)

# Import blueprints
from .portfolio import portfolio_bp
from .review import review_bp

# Register blueprints
def init_app(app):
    """Register blueprints with the Flask application"""
    register_blueprint(app, wallet_bp, '/wallet')
    register_blueprint(app, portfolio_bp, '/portfolio')
    register_blueprint(app, review_bp, '/reviews')
