from datetime import datetime
from extensions import db
from sqlalchemy import func

class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    projects = db.relationship('PortfolioProject', backref='portfolio', lazy=True, cascade='all, delete-orphan')
    skills = db.relationship('PortfolioSkill', backref='portfolio', lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('PortfolioRating', backref='portfolio', lazy=True, cascade='all, delete-orphan')
    
    @property
    def average_rating(self):
        result = db.session.query(func.avg(PortfolioRating.rating)).filter(PortfolioRating.portfolio_id == self.id).scalar()
        return round(float(result), 1) if result else 0.0
    
    @property
    def total_ratings(self):
        return PortfolioRating.query.filter_by(portfolio_id=self.id).count()

class PortfolioProject(db.Model):
    __tablename__ = 'portfolio_projects'
    
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    project_url = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Project categories (e.g., Web Development, Mobile App, etc.)
    category = db.Column(db.String(100))
    
    # Relationships
    user = db.relationship('User', backref=db.backref('portfolio_projects', lazy='dynamic'))
    
    # Relationship to technologies
    technologies = db.relationship('ProjectTechnology', 
                                 backref='project_ref',
                                 lazy='dynamic',
                                 cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PortfolioProject {self.title}>'

class ProjectTechnology(db.Model):
    __tablename__ = 'project_technologies'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('portfolio_projects.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    
    # Simple relationship without backref
    project = db.relationship('PortfolioProject')
    
    def __repr__(self):
        return f'<ProjectTechnology {self.name} (Project ID: {self.project_id})>'


class PortfolioSkill(db.Model):
    __tablename__ = 'portfolio_skills'
    
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    proficiency_level = db.Column(db.Integer)  # 1-5 scale
    years_experience = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PortfolioRating(db.Model):
    __tablename__ = 'portfolio_ratings'
    __module__ = 'models.portfolio'
    
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 scale
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Ensure a user can only rate a portfolio once
    __table_args__ = (db.UniqueConstraint('portfolio_id', 'user_id', name='unique_portfolio_rating'),)
