from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

from models.user import User
from models.review import Review
from extensions import db

bp = Blueprint('profile', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@bp.route('/profile')
@login_required
def view_profile():
    return render_template('profile/view.html', user=current_user)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name)
        current_user.bio = request.form.get('bio', current_user.bio)
        current_user.location = request.form.get('location', current_user.location)
        
        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"user_{current_user.id}.{file.filename.rsplit('.', 1)[1].lower()}")
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pics', filename)
                file.save(filepath)
                current_user.profile_pic = f"uploads/profile_pics/{filename}"
        
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile.view_profile'))
        
    return render_template('profile/edit.html', user=current_user)

@bp.route('/user/<int:user_id>')
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    reviews = Review.query.filter_by(worker_id=user_id).all()
    return render_template('profile.html', user=user, reviews=reviews)

@bp.route('/account/notifications', methods=['POST'])
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
            }), 500
        
        flash('An error occurred while updating notification settings.', 'error')
        return redirect(url_for('main.account'))
