from sqlalchemy.orm import Session
from models.legislation import Alert, User, Bill
from typing import List, Optional
from datetime import datetime

class AlertService:
    def __init__(self, db: Session):
        self.db = db

    def create_alert(self, user_id: int, bill_id: int, alert_type: str,
                    message: str, severity: str = "medium") -> Alert:
        """Create a new alert for a user"""
        alert = Alert(
            user_id=user_id,
            bill_id=bill_id,
            alert_type=alert_type,
            message=message,
            severity=severity
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_user_alerts(self, user_id: int, unread_only: bool = False,
                       limit: int = 50) -> List[Alert]:
        """Get alerts for a user"""
        query = self.db.query(Alert).filter(Alert.user_id == user_id)

        if unread_only:
            query = query.filter(Alert.is_read == False)

        return query.order_by(Alert.triggered_at.desc()).limit(limit).all()

    def get_bill_alerts(self, bill_id: int, alert_type: str = None) -> List[Alert]:
        """Get alerts for a specific bill"""
        query = self.db.query(Alert).filter(Alert.bill_id == bill_id)

        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)

        return query.order_by(Alert.triggered_at.desc()).all()

    def mark_alert_read(self, alert_id: int, user_id: int) -> bool:
        """Mark an alert as read"""
        alert = self.db.query(Alert).filter(
            Alert.id == alert_id,
            Alert.user_id == user_id
        ).first()

        if alert:
            alert.is_read = True
            alert.read_at = datetime.utcnow()
            self.db.commit()
            return True
        return False

    def mark_all_read(self, user_id: int) -> int:
        """Mark all alerts as read for a user"""
        count = self.db.query(Alert).filter(
            Alert.user_id == user_id,
            Alert.is_read == False
        ).update({
            Alert.is_read: True,
            Alert.read_at: datetime.utcnow()
        })
        self.db.commit()
        return count

    def delete_alert(self, alert_id: int, user_id: int) -> bool:
        """Delete an alert"""
        alert = self.db.query(Alert).filter(
            Alert.id == alert_id,
            Alert.user_id == user_id
        ).first()

        if alert:
            self.db.delete(alert)
            self.db.commit()
            return True
        return False

    def create_bill_status_alert(self, bill_id: int, old_status: str, new_status: str):
        """Create alerts for all interested users when a bill status changes"""
        # This would typically find users who have subscribed to this bill
        # For now, we'll create a basic implementation
        message = f"Bill status changed from '{old_status}' to '{new_status}'"

        # In a real implementation, you'd find users subscribed to this bill
        # For now, we'll just create an alert for admin users
        admin_users = self.db.query(User).filter(User.role == "admin").all()

        for user in admin_users:
            self.create_alert(
                user_id=user.id,
                bill_id=bill_id,
                alert_type="status_change",
                message=message,
                severity="medium"
            )

    def create_keyword_match_alert(self, bill_id: int, keyword_term: str,
                                  confidence_score: float):
        """Create alerts for keyword matches"""
        message = f"New bill matched keyword '{keyword_term}' with {confidence_score:.1%} confidence"

        # Find users interested in this keyword category
        # This is a simplified implementation
        interested_users = self.db.query(User).filter(User.is_active == True).all()

        severity = "high" if confidence_score > 0.8 else "medium"

        for user in interested_users:
            self.create_alert(
                user_id=user.id,
                bill_id=bill_id,
                alert_type="keyword_match",
                message=message,
                severity=severity
            )

    def get_alert_stats(self, user_id: int) -> dict:
        """Get alert statistics for a user"""
        total = self.db.query(Alert).filter(Alert.user_id == user_id).count()
        unread = self.db.query(Alert).filter(
            Alert.user_id == user_id,
            Alert.is_read == False
        ).count()

        # Count by severity
        high = self.db.query(Alert).filter(
            Alert.user_id == user_id,
            Alert.severity == "high",
            Alert.is_read == False
        ).count()

        return {
            "total": total,
            "unread": unread,
            "high_priority": high
        }