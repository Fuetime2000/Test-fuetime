from datetime import datetime
from .base import Base, db

class Transaction(Base):
    """
    Model for storing financial transactions in the system.
    """
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # 'debit', 'credit', 'refund', etc.
    status = db.Column(db.String(20), default='completed')  # 'pending', 'completed', 'failed', 'refunded'
    reference_id = db.Column(db.String(100), unique=True)  # External reference ID (e.g., Razorpay order ID)
    transaction_metadata = db.Column('metadata', db.JSON)  # Additional transaction data (stored as 'metadata' in DB)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('user_transactions', lazy='dynamic'))
    
    def __init__(self, user_id=None, amount=None, description=None, transaction_type='debit', status='completed', reference_id=None, metadata=None):
        if user_id is not None:
            self.user_id = user_id
        if amount is not None:
            self.amount = amount
        if description is not None:
            self.description = description
        self.transaction_type = transaction_type
        self.status = status
        self.reference_id = reference_id
        self.transaction_metadata = metadata or {}
        
        # For call transactions, automatically set the transaction type based on amount sign
        if amount is not None:
            if amount < 0:
                self.transaction_type = 'debit'
                self.description = self.description or f"Call charge"
            else:
                self.transaction_type = 'credit'
                self.description = self.description or "Wallet recharge"
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.amount} {self.transaction_type} - {self.status}>'
    
    def to_dict(self):
        """Convert transaction to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': float(self.amount) if self.amount is not None else 0.0,
            'description': self.description,
            'transaction_type': self.transaction_type,
            'status': self.status,
            'reference_id': self.reference_id,
            'metadata': self.transaction_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
