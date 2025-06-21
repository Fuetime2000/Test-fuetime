from datetime import datetime
from .base import Base, db

class ContactRequest(Base):
    """
    Model for storing contact requests between users.
    """
    __tablename__ = 'contact_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requested_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'rejected', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    requester = db.relationship('User', foreign_keys=[requester_id], backref=db.backref('contact_requests_sent', lazy='dynamic'))
    requested = db.relationship('User', foreign_keys=[requested_id], backref=db.backref('contact_requests_received', lazy='dynamic'))
    
    def __init__(self, requester_id, requested_id, message=None, status='pending'):
        self.requester_id = requester_id
        self.requested_id = requested_id
        self.message = message
        self.status = status
    
    def __repr__(self):
        return f'<ContactRequest {self.id}: {self.requester_id} -> {self.requested_id} ({self.status})>'
    
    def to_dict(self):
        """Convert contact request to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'requester_id': self.requester_id,
            'requested_id': self.requested_id,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
