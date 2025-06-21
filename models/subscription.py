from datetime import datetime, timedelta
from .base import Base, db

class Subscription(Base):
    """
    Model for storing user subscription information.
    """
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    plan_id = db.Column(db.String(50), nullable=False)  # e.g., 'basic', 'premium', 'enterprise'
    status = db.Column(db.String(20), default='active')  # 'active', 'cancelled', 'expired', 'trial'
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    auto_renew = db.Column(db.Boolean, default=True)
    payment_method = db.Column(db.String(50))  # e.g., 'razorpay', 'stripe', 'manual'
    payment_reference = db.Column(db.String(100))  # External payment reference ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('subscriptions', lazy='dynamic'))
    
    def __init__(self, user_id, plan_id, status='active', duration_days=30, auto_renew=True, 
                 payment_method=None, payment_reference=None):
        self.user_id = user_id
        self.plan_id = plan_id
        self.status = status
        self.auto_renew = auto_renew
        self.payment_method = payment_method
        self.payment_reference = payment_reference
        self.start_date = datetime.utcnow()
        self.end_date = datetime.utcnow() + timedelta(days=duration_days)
    
    def __repr__(self):
        return f'<Subscription {self.id}: User {self.user_id} - {self.plan_id} ({self.status})>'
    
    def is_active(self):
        """Check if the subscription is currently active."""
        return self.status == 'active' and datetime.utcnow() <= self.end_date
    
    def days_remaining(self):
        """Get the number of days remaining in the subscription."""
        if not self.is_active():
            return 0
        return (self.end_date - datetime.utcnow()).days
    
    def to_dict(self):
        """Convert subscription to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'status': self.status,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'days_remaining': self.days_remaining(),
            'is_active': self.is_active(),
            'auto_renew': self.auto_renew,
            'payment_method': self.payment_method,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
