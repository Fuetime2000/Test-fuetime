from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_wtf.csrf import generate_csrf
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models import (
    User, Portfolio, PortfolioProject, ProjectTechnology, 
    PortfolioSkill, PortfolioRating, db
)
from sqlalchemy.orm import joinedload

portfolio_bp = Blueprint('portfolio', __name__)

@portfolio_bp.route('/view/<int:user_id>')
@login_required
def view_portfolio(user_id):
    user = User.query.options(joinedload(User.portfolio)).get(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('main.index'))

    portfolio = user.portfolio
    if not portfolio:
        flash('Portfolio not found.', 'error')
        return redirect(url_for('main.index'))

    return render_template('portfolio/view.html', portfolio=portfolio, user=user)

@portfolio_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_portfolio(user_id):
    if user_id != current_user.id:
        flash('You can only edit your own portfolio.', 'error')
        return redirect(url_for('main.index'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('main.index'))

    portfolio = Portfolio.query.filter_by(user_id=user.id).first()
    
    if request.method == 'POST':
        if not portfolio:
            portfolio = Portfolio(user_id=user.id)

        portfolio.title = request.form.get('title')
        portfolio.description = request.form.get('description')

        db.session.add(portfolio)
        db.session.commit()

        flash('Portfolio saved successfully!', 'success')
        return redirect(url_for('portfolio.view_portfolio', user_id=user.id))
    
    return render_template('portfolio/edit.html', portfolio=portfolio)

@portfolio_bp.route('/add_project/<int:user_id>', methods=['GET', 'POST'])
@login_required
def add_project(user_id):
    if user_id != current_user.id:
        flash('You can only add projects to your own portfolio.', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            # Validate required fields
            required_fields = ['title', 'description', 'category']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'{field.capitalize()} is required', 'error')
                    return render_template('portfolio/add_project.html', 
                                       user_id=user_id,
                                       form_data=request.form)
            
            # Start a transaction
            db.session.begin_nested()
            
            # Get or create portfolio for the user
            portfolio = Portfolio.query.filter_by(user_id=user_id).first()
            if not portfolio:
                portfolio = Portfolio(
                    user_id=user_id, 
                    title=f"{current_user.full_name}'s Portfolio",
                    description=f"Portfolio for {current_user.full_name}"
                )
                db.session.add(portfolio)
                db.session.flush()
            
            # Parse dates safely
            start_date = None
            end_date = None
            
            try:
                if request.form.get('start_date'):
                    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
                if request.form.get('end_date'):
                    end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            except ValueError as e:
                db.session.rollback()
                flash('Invalid date format. Please use YYYY-MM-DD format.', 'error')
                return render_template('portfolio/add_project.html', 
                                   user_id=user_id,
                                   form_data=request.form)
            
            # Create project
            project = PortfolioProject(
                portfolio_id=portfolio.id,
                user_id=user_id,
                title=request.form['title'],
                description=request.form['description'],
                project_url=request.form.get('project_url', ''),
                category=request.form['category'],
                start_date=start_date,
                end_date=end_date
            )
            
            # Handle image upload
            if 'project_image' in request.files:
                file = request.files['project_image']
                if file and file.filename and allowed_file(file.filename):
                    try:
                        filename = secure_filename(file.filename)
                        # Create upload folder if it doesn't exist
                        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
                        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        project.image_url = filename
                    except Exception as e:
                        current_app.logger.error(f'Error saving file: {str(e)}')
                        flash('Error saving uploaded file', 'error')
            
            db.session.add(project)
            db.session.flush()
            
            # Handle technologies
            tech_input = request.form.get('technologies', '')
            if tech_input:
                # Clear existing technologies first if needed
                ProjectTechnology.query.filter_by(project_id=project.id).delete()
                
                # Create a set to avoid duplicates
                tech_names = {t.strip() for t in tech_input.split(',') if t.strip()}
                for tech_name in tech_names:
                    # Create and add technology using the relationship
                    tech = ProjectTechnology(
                        name=tech_name[:100],  # Ensure it doesn't exceed the column limit
                        project_ref=project  # Use the relationship
                    )
                    db.session.add(tech)
            
            db.session.commit()
            flash('Project added successfully!', 'success')
            return redirect(url_for('portfolio.view_portfolio', user_id=user_id))
            
        except Exception as e:
            db.session.rollback()
            # Log the full traceback for debugging
            import traceback
            error_traceback = traceback.format_exc()
            current_app.logger.error(f'Error adding project: {str(e)}\n{error_traceback}')
            
            # For development, show the actual error message
            error_msg = str(e)
            if 'UNIQUE constraint failed' in error_msg:
                error_msg = 'A project with these details already exists.'
                
            flash(f'Error: {error_msg}', 'error')
            
            # Return the form with the entered data
            return render_template('portfolio/add_project.html', 
                               user_id=user_id,
                               form_data=request.form)
    
    # GET request - show empty form
    return render_template('portfolio/add_project.html', 
                         user_id=user_id,
                         form_data=request.form if request.method == 'POST' else {})
    
    return render_template('portfolio/add_project.html', user_id=user_id)

@portfolio_bp.route('/portfolio/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    try:
        # Verify CSRF token
        if not request.form.get('csrf_token'):
            flash('Session expired. Please refresh the page and try again.', 'error')
            return redirect(url_for('portfolio.view_portfolio', user_id=current_user.id))

        project = PortfolioProject.query.get_or_404(project_id)
        portfolio = Portfolio.query.filter_by(user_id=current_user.id).first()
        
        if not portfolio:
            flash('Portfolio not found.', 'error')
            return redirect(url_for('main.index'))
        
        if project.portfolio_id != portfolio.id:
            flash('Unauthorized access!', 'error')
            return redirect(url_for('portfolio.view_portfolio', user_id=current_user.id))
        
        db.session.delete(project)
        db.session.commit()
        
        flash('Project deleted successfully!', 'success')
        return redirect(url_for('portfolio.view_portfolio', user_id=current_user.id))
    
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the project. Please try again.', 'error')
        return redirect(url_for('portfolio.view_portfolio', user_id=current_user.id))

@portfolio_bp.route('/portfolio/skills', methods=['POST'])
@login_required
def update_skills():
    portfolio = Portfolio.query.filter_by(user_id=current_user.id).first()
    
    # Clear existing skills
    PortfolioSkill.query.filter_by(portfolio_id=portfolio.id).delete()
    
    # Add new skills
    skills = request.json.get('skills', [])
    for skill_data in skills:
        skill = PortfolioSkill(
            portfolio_id=portfolio.id,
            name=skill_data['name'],
            proficiency_level=skill_data['proficiency_level'],
            years_experience=skill_data['years_experience']
        )
        db.session.add(skill)
    
    db.session.commit()
    response = jsonify({'message': 'Skills updated successfully', 'csrf_token': generate_csrf()})
    return response

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@portfolio_bp.route('/rate/<int:portfolio_id>', methods=['POST'])
@login_required
def rate_portfolio(portfolio_id):
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    
    # Don't allow users to rate their own portfolio
    if portfolio.user_id == current_user.id:
        return jsonify({
            'status': 'error',
            'message': 'You cannot rate your own portfolio'
        }), 400
    
    rating_value = request.json.get('rating')
    comment = request.json.get('comment', '')
    
    if not rating_value or not isinstance(rating_value, int) or rating_value < 1 or rating_value > 5:
        return jsonify({
            'status': 'error',
            'message': 'Invalid rating value'
        }), 400
    
    # Check if user has already rated this portfolio
    existing_rating = PortfolioRating.query.filter_by(
        portfolio_id=portfolio_id,
        user_id=current_user.id
    ).first()
    
    if existing_rating:
        # Update existing rating
        existing_rating.rating = rating_value
        existing_rating.comment = comment
    else:
        # Create new rating
        new_rating = PortfolioRating(
            portfolio_id=portfolio_id,
            user_id=current_user.id,
            rating=rating_value,
            comment=comment
        )
        db.session.add(new_rating)
    
    try:
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Rating updated successfully',
            'average_rating': portfolio.average_rating,
            'total_ratings': portfolio.total_ratings
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Failed to save rating'
        }), 500

@portfolio_bp.route('/ratings/<int:portfolio_id>')
@login_required
def get_portfolio_ratings(portfolio_id):
    portfolio = Portfolio.query.get_or_404(portfolio_id)
    ratings = PortfolioRating.query.filter_by(portfolio_id=portfolio_id).all()
    
    ratings_data = [{
        'rating': r.rating,
        'comment': r.comment,
        'user': User.query.get(r.user_id).username,
        'date': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'is_own_rating': r.user_id == current_user.id
    } for r in ratings]
    
    return jsonify({
        'status': 'success',
        'ratings': ratings_data,
        'average_rating': portfolio.average_rating,
        'total_ratings': portfolio.total_ratings,
        'user_rating': next(
            (r.rating for r in ratings if r.user_id == current_user.id),
            None
        )
    })
