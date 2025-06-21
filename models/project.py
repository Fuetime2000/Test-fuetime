from datetime import datetime
from extensions import db

project_technologies = db.Table('portfolio_project_technologies',
    db.Column('project_id', db.Integer, db.ForeignKey('portfolio_projects.id'), primary_key=True),
    db.Column('technology_id', db.Integer, db.ForeignKey('portfolio_technologies.id'), primary_key=True),
    extend_existing=True
)

class Technology(db.Model):
    __tablename__ = 'portfolio_technologies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Technology {self.name}>'

class Project(db.Model):
    __tablename__ = 'portfolio_projects'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(255))
    project_url = db.Column(db.String(255))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('projects', lazy='dynamic'))
    technologies = db.relationship('Technology', secondary=project_technologies, lazy='joined',
                                 backref=db.backref('projects', lazy=True))

    def __repr__(self):
        return f'<Project {self.title}>'
