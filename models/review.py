from datetime import datetime
from models.base import Base, db

class Review(Base):
    __tablename__ = 'review'
    __module__ = 'models.review'
    
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], back_populates='reviews_given')
    worker = db.relationship('User', foreign_keys=[worker_id], back_populates='reviews_received')
    
    def __repr__(self):
        return f'<Review {self.id} by User {self.reviewer_id} for User {self.worker_id}>'
