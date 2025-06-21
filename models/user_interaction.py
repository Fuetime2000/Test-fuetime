from datetime import datetime
from .base import db

class UserInteraction(db.Model):
    """
    Model for tracking interactions between users (e.g., profile views, messages, etc.)
    """
    __tablename__ = 'user_interactions'
    
    id = db.Column(db.Integer, primary_key=True)
    viewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    viewed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    interaction_type = db.Column(db.String(20), nullable=False)  # 'profile_view', 'message', 'call', etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    viewer = db.relationship('User', foreign_keys=[viewer_id], backref=db.backref('interactions_made', lazy='dynamic'))
    viewed = db.relationship('User', foreign_keys=[viewed_id], backref=db.backref('interactions_received', lazy='dynamic'))
    
    def __repr__(self):
        return f'<UserInteraction {self.viewer_id} -> {self.viewed_id} ({self.interaction_type})>'
    
    def to_dict(self):
        """Convert the user interaction to a dictionary."""
        return {
            'id': self.id,
            'viewer_id': self.viewer_id,
            'viewed_id': self.viewed_id,
            'interaction_type': self.interaction_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
