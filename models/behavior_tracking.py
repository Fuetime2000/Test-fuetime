from datetime import datetime
from extensions import db

class UserBehavior(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    action_type = db.Column(db.String(50))  # login, message, profile_view, payment, etc.
    action_details = db.Column(db.JSON)
    risk_score = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('behaviors', lazy='dynamic'))

    def __repr__(self):
        return f'<UserBehavior {self.user_id} - {self.action_type}>'

class FraudAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    alert_type = db.Column(db.String(50))  # suspicious_login, payment_fraud, spam, etc.
    severity = db.Column(db.String(20))  # low, medium, high
    details = db.Column(db.JSON)
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    user = db.relationship('User', backref=db.backref('fraud_alerts', lazy='dynamic'))

    def __repr__(self):
        return f'<FraudAlert {self.user_id} - {self.alert_type}>'
