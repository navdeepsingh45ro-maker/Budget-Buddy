import logging
from sqlalchemy.orm import Session
from models.notification_model import Notification
from services.device_service import DeviceService
from .android_adapter import AndroidAdapter
from .ios_adapter import IOSAdapter
from .web_adapter import WebAdapter

logger = logging.getLogger("delivery_manager")

class DeliveryManager:
    """
    Platform-independent Notification Delivery Framework.
    Orchestrates notification dispatch to the correct platform adapter.
    """
    
    def __init__(self):
        self.adapters = {
            "android": AndroidAdapter(),
            "ios": IOSAdapter(),
            "web": WebAdapter()
        }

    def process_delivery(self, db: Session, notification_id: int):
        """
        Retrieves a notification from the DB and attempts delivery 
        to all active devices registered to the user.
        """
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            return

        # 1. Fetch active devices using DeviceService
        devices = DeviceService.get_active_devices(db, notification.user_id)
        
        if not devices:
            logger.info(f"No active devices found for user {notification.user_id}. Leaving notification queued.")
            self._update_notification_status(db, notification, "queued")
            return
            
        # Update status to pending/processing
        self._update_notification_status(db, notification, "pending")

        # Map internal priority
        priority_map = {
            "critical": "high",
            "warning": "default",
            "success": "default",
            "info": "low"
        }
        mapped_priority = priority_map.get(notification.priority, "default")
        
        payload = {
            "title": notification.title,
            "body": notification.message,
            "icon": notification.icon,
            "priority": mapped_priority,
            "data": {
                "action_type": notification.action_type,
                "action_payload": notification.action_payload,
                "notification_id": notification.id
            }
        }

        delivery_success = False

        # 2. Group devices by platform
        from collections import defaultdict
        grouped_devices = defaultdict(list)
        for device in devices:
            grouped_devices[device.platform].append(device)

        # 3. Send notification to matching adapter
        for platform, platform_devices in grouped_devices.items():
            adapter = self.adapters.get(platform)
            
            if not adapter:
                logger.warning(f"No adapter found for platform: {platform}")
                continue
                
            for device in platform_devices:
                if not adapter.validate_device(device):
                    logger.warning(f"Device {device.id} failed validation for platform {platform}.")
                    continue
                    
                # Dispatch to the specific adapter
                try:
                    success = adapter.send(payload, device.device_token)
                    if success:
                        delivery_success = True
                except Exception as e:
                    logger.error(f"Error dispatching via {platform} adapter: {e}")

        # Update final delivery status based on adapter responses
        if delivery_success:
            self._update_notification_status(db, notification, "delivered")
        else:
            # Since adapters are currently placeholders, they will return False (Not Implemented)
            # We mark as failed (or queued) based on framework rules.
            self._update_notification_status(db, notification, "failed")

    def _update_notification_status(self, db: Session, notification: Notification, status: str):
        """
        Updates the delivery status (pending -> queued -> delivered -> failed).
        """
        try:
            notification.status = status
            db.commit()
        except Exception as e:
            logger.error(f"Failed to update status to {status} for notification {notification.id}: {e}")
            db.rollback()
