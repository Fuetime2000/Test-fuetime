from datetime import datetime
from extensions import db
from models.user import User

class Donation(db.Model):
    __tablename__ = 'donations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), server_default='INR')
    donor_name = db.Column(db.String(100), nullable=True)
    donor_email = db.Column(db.String(120), nullable=True)
    message = db.Column(db.Text, nullable=True)
    is_anonymous = db.Column(db.Boolean, server_default='0')
    status = db.Column(db.String(20), server_default='pending')  # pending, completed, failed
    transaction_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    
    user = db.relationship(
        'User',
        backref=db.backref('donations', lazy=True, cascade='all, delete-orphan')
    )
    
    def __repr__(self):
        return f'<Donation {self.id} - {self.amount} {self.currency}>'
