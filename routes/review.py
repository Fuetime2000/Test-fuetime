import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models import User, Review, db
from sqlalchemy.exc import SQLAlchemyError

review_bp = Blueprint('review', __name__)
logger = logging.getLogger(__name__)

@review_bp.route('/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def review(worker_id):
    def is_ajax():
        return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json'
    
    try:
        worker = User.query.get_or_404(worker_id)
        
        # Don't allow users to review themselves
        if worker.id == current_user.id:
            response = {'success': False, 'message': 'You cannot review yourself.'}
            return jsonify(response) if is_ajax() else redirect(url_for('profile', user_id=worker.id))
        
        # Check if user has already reviewed this worker
        existing_review = Review.query.filter_by(
            reviewer_id=current_user.id,
            worker_id=worker.id
        ).first()
        
        if request.method == 'POST':
            if existing_review:
                response = {'success': False, 'message': 'You have already reviewed this user.'}
                return jsonify(response) if is_ajax() else redirect(url_for('profile', user_id=worker.id))
            
            rating = request.form.get('rating')
            comment = request.form.get('comment')
            
            if not rating or not comment:
                response = {'success': False, 'message': 'Both rating and comment are required.'}
                return jsonify(response) if is_ajax() else render_template('review.html', worker=worker, existing_review=None)
            
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    raise ValueError('Rating must be between 1 and 5')
            except ValueError as e:
                response = {'success': False, 'message': str(e) if str(e) else 'Invalid rating value.'}
                return jsonify(response) if is_ajax() else render_template('review.html', worker=worker, existing_review=None)
            
            new_review = Review(
                reviewer_id=current_user.id,
                worker_id=worker.id,
                rating=rating,
                comment=comment
            )
            
            try:
                # Add review and update rating in a single transaction
                db.session.begin_nested()
                db.session.add(new_review)
                db.session.flush()
                worker.update_rating()
                db.session.commit()
                
                response = {'success': True, 'message': 'Review submitted successfully!'}
                return jsonify(response) if is_ajax() else redirect(url_for('profile', user_id=worker.id))
            except SQLAlchemyError as e:
                db.session.rollback()
                logger.error(f'Database error while submitting review: {str(e)}')
                response = {'success': False, 'message': 'An error occurred while submitting your review. Please try again.'}
                return jsonify(response) if is_ajax() else render_template('review.html', worker=worker, existing_review=None)
        
        return render_template('review.html', worker=worker, existing_review=existing_review)
        
    except Exception as e:
        logger.error(f'Unexpected error in review route: {str(e)}')
        response = {'success': False, 'message': 'An unexpected error occurred. Please try again.'}
        return jsonify(response) if is_ajax() else render_template('error.html', error=str(e))
