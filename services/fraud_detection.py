from datetime import datetime, timedelta
from models.behavior_tracking import UserBehavior, FraudAlert
from extensions import db
import json

class FraudDetectionService:
    def __init__(self):
        # Risk thresholds
        self.RISK_THRESHOLD_LOW = 0.3
        self.RISK_THRESHOLD_MEDIUM = 0.6
        self.RISK_THRESHOLD_HIGH = 0.8

        # Time windows for analysis (in hours)
        self.TIME_WINDOW_SHORT = 1
        self.TIME_WINDOW_MEDIUM = 24
        self.TIME_WINDOW_LONG = 168  # 7 days

    def track_behavior(self, user_id, ip_address, user_agent, action_type, action_details):
        """Record user behavior for analysis"""
        behavior = UserBehavior(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action_type=action_type,
            action_details=json.dumps(action_details) if isinstance(action_details, dict) else action_details
        )
        
        risk_score = self._calculate_risk_score(behavior)
        behavior.risk_score = risk_score
        
        db.session.add(behavior)
        db.session.commit()
        
        if risk_score > self.RISK_THRESHOLD_LOW:
            self._create_fraud_alert(user_id, risk_score, action_type, action_details)
        
        return risk_score

    def _calculate_risk_score(self, behavior):
        """Calculate risk score based on various factors"""
        risk_score = 0.0
        
        # Get recent behaviors
        recent_behaviors = UserBehavior.query.filter(
            UserBehavior.user_id == behavior.user_id,
            UserBehavior.timestamp >= datetime.utcnow() - timedelta(hours=self.TIME_WINDOW_MEDIUM)
        ).all()
        
        # Check for rapid actions
        if self._check_rapid_actions(recent_behaviors, behavior.action_type):
            risk_score += 0.3
            
        # Check for location anomalies
        if self._check_location_anomaly(recent_behaviors, behavior.ip_address):
            risk_score += 0.4
            
        # Check for suspicious patterns based on action type
        pattern_risk = self._check_suspicious_patterns(behavior, recent_behaviors)
        risk_score += pattern_risk
        
        return min(risk_score, 1.0)

    def _check_rapid_actions(self, recent_behaviors, action_type):
        """Check for unusually rapid actions of the same type"""
        recent_similar_actions = [b for b in recent_behaviors if b.action_type == action_type]
        if len(recent_similar_actions) > 10:  # More than 10 similar actions in 24 hours
            time_diffs = []
            for i in range(1, len(recent_similar_actions)):
                diff = recent_similar_actions[i].timestamp - recent_similar_actions[i-1].timestamp
                time_diffs.append(diff.total_seconds())
            
            if time_diffs and min(time_diffs) < 10:  # Less than 10 seconds between actions
                return True
        return False

    def _check_location_anomaly(self, recent_behaviors, current_ip):
        """Check for suspicious location changes"""
        if not recent_behaviors:
            return False
            
        recent_ips = set(b.ip_address for b in recent_behaviors)
        if len(recent_ips) > 5:  # More than 5 different IPs in 24 hours
            return True
            
        return False

    def _check_suspicious_patterns(self, behavior, recent_behaviors):
        """Check for suspicious patterns based on action type"""
        risk_score = 0.0
        
        if behavior.action_type == 'login':
            # Check for failed login attempts
            failed_logins = sum(1 for b in recent_behaviors 
                              if b.action_type == 'login' 
                              and json.loads(b.action_details).get('success', True) is False)
            if failed_logins > 3:
                risk_score += 0.4
                
        elif behavior.action_type == 'message':
            # Check for spam-like behavior
            message_count = sum(1 for b in recent_behaviors if b.action_type == 'message')
            if message_count > 50:  # More than 50 messages in 24 hours
                risk_score += 0.3
                
        elif behavior.action_type == 'payment':
            # Check for unusual payment patterns
            amount = behavior.action_details.get('amount', 0)
            recent_payments = [b for b in recent_behaviors if b.action_type == 'payment']
            if recent_payments:
                avg_amount = sum(float(b.action_details.get('amount', 0)) for b in recent_payments) / len(recent_payments)
                if amount > avg_amount * 5:  # Amount is 5x higher than average
                    risk_score += 0.5
                    
        return risk_score

    def _create_fraud_alert(self, user_id, risk_score, action_type, action_details):
        """Create a fraud alert based on risk score"""
        severity = 'low'
        if risk_score >= self.RISK_THRESHOLD_HIGH:
            severity = 'high'
        elif risk_score >= self.RISK_THRESHOLD_MEDIUM:
            severity = 'medium'
            
        alert = FraudAlert(
            user_id=user_id,
            alert_type=f'suspicious_{action_type}',
            severity=severity,
            details={
                'risk_score': risk_score,
                'action_type': action_type,
                'action_details': action_details
            }
        )
        
        db.session.add(alert)
        db.session.commit()
        
        return alert

    def get_user_risk_profile(self, user_id):
        """Get overall risk profile for a user"""
        recent_behaviors = UserBehavior.query.filter(
            UserBehavior.user_id == user_id,
            UserBehavior.timestamp >= datetime.utcnow() - timedelta(hours=self.TIME_WINDOW_LONG)
        ).all()
        
        if not recent_behaviors:
            return {
                'risk_level': 'low',
                'average_risk_score': 0.0,
                'alert_count': 0
            }
            
        avg_risk_score = sum(b.risk_score for b in recent_behaviors) / len(recent_behaviors)
        alert_count = FraudAlert.query.filter(
            FraudAlert.user_id == user_id,
            FraudAlert.created_at >= datetime.utcnow() - timedelta(hours=self.TIME_WINDOW_LONG)
        ).count()
        
        risk_level = 'low'
        if avg_risk_score >= self.RISK_THRESHOLD_HIGH:
            risk_level = 'high'
        elif avg_risk_score >= self.RISK_THRESHOLD_MEDIUM:
            risk_level = 'medium'
            
        return {
            'risk_level': risk_level,
            'average_risk_score': avg_risk_score,
            'alert_count': alert_count
        }
