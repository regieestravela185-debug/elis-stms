"""
Smart Notification System
Intelligent notification prioritization and automated triggers
"""

from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from enum import Enum


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationType(str, Enum):
    PAYMENT_REMINDER = "payment_reminder"
    RENEWAL_REMINDER = "renewal_reminder"
    CONCERN_ALERT = "concern_alert"
    RESERVATION_ALERT = "reservation_alert"


class NotificationTrigger(str, Enum):
    PAYMENT_DUE = "payment_due"
    PAYMENT_OVERDUE = "payment_overdue"
    LEASE_EXPIRING = "lease_expiring"
    CONCERN_UNRESOLVED = "concern_unresolved"
    RESERVATION_PENDING = "reservation_pending"
    RISK_HIGH = "risk_high"


class SmartNotificationSystem:
    """Intelligent notification system with prioritization"""
    
    def __init__(self):
        self.notification_queue: List[Dict] = []
        self.priority_weights = {
            NotificationPriority.URGENT: 4,
            NotificationPriority.HIGH: 3,
            NotificationPriority.MEDIUM: 2,
            NotificationPriority.LOW: 1,
        }
    
    def calculate_notification_priority(
        self,
        notification_type: NotificationType,
        trigger_type: NotificationTrigger,
        user_data: Optional[Dict] = None,
    ) -> NotificationPriority:
        """
        Calculate notification priority based on type, trigger, and user data.
        Returns priority level.
        """
        base_priority = self._get_base_priority(notification_type, trigger_type)
        
        # Adjust based on user data (payment risk, etc.)
        if user_data:
            if user_data.get("payment_risk_level") == "high":
                # Increase priority for high-risk tenants
                if base_priority == NotificationPriority.LOW:
                    base_priority = NotificationPriority.MEDIUM
                elif base_priority == NotificationPriority.MEDIUM:
                    base_priority = NotificationPriority.HIGH
            
            if user_data.get("days_overdue", 0) > 7:
                base_priority = NotificationPriority.URGENT
            elif user_data.get("days_overdue", 0) > 3:
                if base_priority != NotificationPriority.URGENT:
                    base_priority = NotificationPriority.HIGH
            
            if user_data.get("concern_priority") == "high":
                base_priority = NotificationPriority.HIGH
            
            if user_data.get("lease_days_remaining", 30) < 7:
                base_priority = NotificationPriority.HIGH
        
        return base_priority
    
    def _get_base_priority(
        self,
        notification_type: NotificationType,
        trigger_type: NotificationTrigger,
    ) -> NotificationPriority:
        """Get base priority for notification type and trigger"""
        priority_map = {
            (NotificationType.PAYMENT_REMINDER, NotificationTrigger.PAYMENT_DUE): NotificationPriority.MEDIUM,
            (NotificationType.PAYMENT_REMINDER, NotificationTrigger.PAYMENT_OVERDUE): NotificationPriority.URGENT,
            (NotificationType.RENEWAL_REMINDER, NotificationTrigger.LEASE_EXPIRING): NotificationPriority.HIGH,
            (NotificationType.CONCERN_ALERT, NotificationTrigger.CONCERN_UNRESOLVED): NotificationPriority.HIGH,
            (NotificationType.RESERVATION_ALERT, NotificationTrigger.RESERVATION_PENDING): NotificationPriority.MEDIUM,
            (NotificationType.PAYMENT_REMINDER, NotificationTrigger.RISK_HIGH): NotificationPriority.HIGH,
        }
        
        return priority_map.get((notification_type, trigger_type), NotificationPriority.LOW)
    
    def generate_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        trigger_type: NotificationTrigger,
        message: str,
        user_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Generate a notification with calculated priority.
        Returns notification dict.
        """
        priority = self.calculate_notification_priority(notification_type, trigger_type, user_data)
        
        notification = {
            "user_id": user_id,
            "notification_type": notification_type.value,
            "notification_priority": priority.value,
            "automated_trigger_type": trigger_type.value,
            "message": message,
            "sent_at": datetime.now().isoformat(),
            "status": "sent",
        }
        
        self.notification_queue.append(notification)
        return notification
    
    def get_payment_reminder_notification(
        self,
        user_id: int,
        days_until_due: int,
        amount: float,
        payment_risk_level: str = "low",
    ) -> Dict:
        """Generate payment reminder notification"""
        if days_until_due <= 0:
            trigger = NotificationTrigger.PAYMENT_OVERDUE
            message = f"URGENT: Your payment of ₱{amount:,.2f} is overdue. Please pay immediately to avoid penalties."
        elif days_until_due <= 3:
            trigger = NotificationTrigger.PAYMENT_DUE
            message = f"Reminder: Your payment of ₱{amount:,.2f} is due in {days_until_due} day(s)."
        else:
            trigger = NotificationTrigger.PAYMENT_DUE
            message = f"Your payment of ₱{amount:,.2f} is due on the 5th. Please ensure timely payment."
        
        user_data = {"payment_risk_level": payment_risk_level, "days_overdue": max(0, -days_until_due)}
        
        return self.generate_notification(
            user_id=user_id,
            notification_type=NotificationType.PAYMENT_REMINDER,
            trigger_type=trigger,
            message=message,
            user_data=user_data,
        )
    
    def get_renewal_reminder_notification(
        self,
        user_id: int,
        lease_end_date: date,
        days_until_expiry: int,
    ) -> Dict:
        """Generate lease renewal reminder notification"""
        trigger = NotificationTrigger.LEASE_EXPIRING
        
        if days_until_expiry <= 7:
            message = f"URGENT: Your lease expires on {lease_end_date.strftime('%B %d, %Y')}. Please submit renewal request immediately."
        elif days_until_expiry <= 30:
            message = f"Your lease expires on {lease_end_date.strftime('%B %d, %Y')}. Please consider renewal."
        else:
            message = f"Lease renewal reminder: Your lease ends on {lease_end_date.strftime('%B %d, %Y')}."
        
        user_data = {"lease_days_remaining": days_until_expiry}
        
        return self.generate_notification(
            user_id=user_id,
            notification_type=NotificationType.RENEWAL_REMINDER,
            trigger_type=trigger,
            message=message,
            user_data=user_data,
        )
    
    def get_concern_alert_notification(
        self,
        user_id: int,
        concern_subject: str,
        days_open: int,
        priority: str = "medium",
    ) -> Dict:
        """Generate concern alert notification"""
        trigger = NotificationTrigger.CONCERN_UNRESOLVED
        
        if days_open > 7:
            message = f"URGENT: Concern '{concern_subject}' has been open for {days_open} days. Immediate attention required."
        elif days_open > 3:
            message = f"Concern '{concern_subject}' has been open for {days_open} days. Please follow up."
        else:
            message = f"New concern: '{concern_subject}'. Please review."
        
        user_data = {"concern_priority": priority, "days_open": days_open}
        
        return self.generate_notification(
            user_id=user_id,
            notification_type=NotificationType.CONCERN_ALERT,
            trigger_type=trigger,
            message=message,
            user_data=user_data,
        )
    
    def get_reservation_alert_notification(
        self,
        user_id: int,
        reservation_id: int,
        status: str,
    ) -> Dict:
        """Generate reservation alert notification"""
        trigger = NotificationTrigger.RESERVATION_PENDING
        
        if status == "pending":
            message = f"New reservation #{reservation_id} requires approval. Please review and process."
        elif status == "approved":
            message = f"Reservation #{reservation_id} has been approved. Tenant has been notified."
        elif status == "rejected":
            message = f"Reservation #{reservation_id} has been rejected. Tenant has been notified."
        else:
            message = f"Reservation #{reservation_id} status updated to {status}."
        
        return self.generate_notification(
            user_id=user_id,
            notification_type=NotificationType.RESERVATION_ALERT,
            trigger_type=trigger,
            message=message,
        )
    
    def get_high_risk_alert_notification(
        self,
        user_id: int,
        tenant_name: str,
        risk_score: float,
    ) -> Dict:
        """Generate high-risk tenant alert notification"""
        trigger = NotificationTrigger.RISK_HIGH
        
        message = f"ALERT: Tenant {tenant_name} has been flagged as high payment risk (score: {risk_score:.2f}). Consider proactive outreach."
        
        user_data = {"payment_risk_level": "high"}
        
        return self.generate_notification(
            user_id=user_id,
            notification_type=NotificationType.PAYMENT_REMINDER,
            trigger_type=trigger,
            message=message,
            user_data=user_data,
        )
    
    def sort_notifications_by_priority(self, notifications: List[Dict]) -> List[Dict]:
        """Sort notifications by priority (urgent first)"""
        priority_order = {
            NotificationPriority.URGENT.value: 0,
            NotificationPriority.HIGH.value: 1,
            NotificationPriority.MEDIUM.value: 2,
            NotificationPriority.LOW.value: 3,
        }
        
        return sorted(notifications, key=lambda x: priority_order.get(x.get("notification_priority", "low"), 3))
    
    def get_pending_notifications(self, user_id: Optional[int] = None) -> List[Dict]:
        """Get pending notifications, optionally filtered by user"""
        notifications = self.notification_queue
        
        if user_id:
            notifications = [n for n in notifications if n.get("user_id") == user_id]
        
        return self.sort_notifications_by_priority(notifications)
    
    def clear_notification_queue(self):
        """Clear the notification queue"""
        self.notification_queue.clear()


# Global notification system instance
_notification_system_instance = None

def get_notification_system() -> SmartNotificationSystem:
    """Get or create global notification system instance"""
    global _notification_system_instance
    if _notification_system_instance is None:
        _notification_system_instance = SmartNotificationSystem()
    return _notification_system_instance


def send_notification_to_db(notification: Dict, db_model) -> bool:
    """
    Save notification to database using the provided model.
    Returns True if successful.
    """
    try:
        # Create notification record
        notification_record = db_model(
            user_id=notification["user_id"],
            notification_type=notification["notification_type"],
            notification_priority=notification["notification_priority"],
            automated_trigger_type=notification["automated_trigger_type"],
            message=notification["message"],
            sent_at=datetime.fromisoformat(notification["sent_at"]),
            status=notification["status"],
        )
        
        # Save to database
        from app.extensions import db
        db.session.add(notification_record)
        db.session.commit()
        
        return True
    except Exception as e:
        print(f"Error saving notification to database: {e}")
        return False


def generate_automated_notifications(tenant_data: List[Dict]) -> List[Dict]:
    """
    Generate automated notifications for all tenants based on their data.
    Returns list of notifications.
    """
    system = get_notification_system()
    notifications = []
    
    for tenant in tenant_data:
        user_id = tenant.get("user_id")
        
        # Payment reminders
        if tenant.get("payment_due_soon"):
            notifications.append(
                system.get_payment_reminder_notification(
                    user_id=user_id,
                    days_until_due=tenant.get("days_until_due", 5),
                    amount=tenant.get("monthly_rent", 0),
                    payment_risk_level=tenant.get("payment_risk_level", "low"),
                )
            )
        
        # Renewal reminders
        if tenant.get("lease_expiring_soon"):
            notifications.append(
                system.get_renewal_reminder_notification(
                    user_id=user_id,
                    lease_end_date=tenant.get("lease_end_date"),
                    days_until_expiry=tenant.get("days_until_expiry", 30),
                )
            )
        
        # High-risk alerts
        if tenant.get("payment_risk_level") == "high":
            notifications.append(
                system.get_high_risk_alert_notification(
                    user_id=user_id,
                    tenant_name=tenant.get("full_name", "Unknown"),
                    risk_score=tenant.get("prediction_score", 0.8),
                )
            )
    
    return notifications
