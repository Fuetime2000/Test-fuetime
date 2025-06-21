from datetime import datetime
from . import db
from sqlalchemy import event

class Call(db.Model):
    __tablename__ = 'calls'
    
    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    caller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    callee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='initiated', nullable=False)  # initiated, completed, missed, rejected, failed
    duration = db.Column(db.Integer, default=0)  # in seconds
    cost = db.Column(db.Float, default=0.0, nullable=False)  # in INR
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    caller = db.relationship('User', foreign_keys=[caller_id], backref=db.backref('outgoing_calls', lazy=True))
    callee = db.relationship('User', foreign_keys=[callee_id], backref=db.backref('incoming_calls', lazy=True))
    
    def __init__(self, call_id, caller_id, callee_id, status='initiated', duration=0, cost=0.0, **kwargs):
        self.call_id = call_id
        self.caller_id = caller_id
        self.callee_id = callee_id
        self.status = status
        self.duration = duration
        self.cost = cost
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __repr__(self):
        return f'<Call {self.call_id} from {self.caller_id} to {self.callee_id} ({self.status})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'call_id': self.call_id,
            'caller_id': self.caller_id,
            'callee_id': self.callee_id,
            'status': self.status,
            'duration': self.duration,
            'cost': self.cost,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# Set up event listeners for the Call model
@event.listens_for(Call, 'before_insert')
def set_created_updated(mapper, connection, target):
    target.created_at = datetime.utcnow()
    target.updated_at = datetime.utcnow()

@event.listens_for(Call, 'before_update')
def set_updated(mapper, connection, target):
    target.updated_at = datetime.utcnow()
