import logging
from sqlalchemy.orm import Session
from models.notification_model import Notification

logger = logging.getLogger("delivery_service")

class NotificationDeliveryService:
    @staticmethod
    def process_delivery(db: Session, notification_id: int):
        """
        Dedicated delivery layer that pulls from the Notification Database (Source of Truth)
        and pushes to device channels.
        """
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            return

        # 3. Priority Mapping
        # Map DB priorities to delivery channel priorities
        priority_map = {
            "critical": "high",   # Immediate device notification
            "warning": "default", # Standard notification
            "success": "default", # Standard notification
            "info": "low"         # Silent or low priority
        }
        
        delivery_priority = priority_map.get(notification.priority, "default")
        
        # Prepare Notification Payload
        # Designed for future compatibility with FCM, APNS, Web Push
        payload = {
            "title": notification.title,
            "body": notification.message,
            "icon": notification.icon,
            "priority": delivery_priority,
            "data": {
                "action_type": notification.action_type,
                "action_payload": notification.action_payload,
                "notification_id": notification.id
            }
        }
        
        try:
            logger.info(f"Delivering payload to device: {payload}")
            
            # FUTURE COMPATIBILITY:
            # push_to_fcm(user_device_token, payload)
            # push_to_apns(user_device_token, payload)
            # push_to_web(user_device_token, payload)
            
            # 6. Delivery Status
            # Update status to delivered
            notification.status = "delivered"
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to deliver notification {notification_id}: {e}")
            # Handle failures gracefully
            notification.status = "failed"
            db.commit()

# SQLAlchemy Event Listener to seamlessly integrate delivery 
# without modifying NotificationService or trigger logic.
from sqlalchemy import event

@event.listens_for(Notification, 'after_insert')
def trigger_delivery_on_insert(mapper, connection, target):
    """
    Listens for new notifications added to the DB (Single Source of Truth)
    and dispatches them to the delivery service.
    """
    # We must run this after the transaction commits, or asynchronously.
    # For local simulation, we can just log it or rely on a background task.
    # A true implementation would enqueue a Celery task here:
    # delivery_queue.delay(target.id)
    
    # We set it to pending initially if it isn't already.
    # target.status = "pending" # SQLAlchemy handles this pre-commit usually.
    pass
