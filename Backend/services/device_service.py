from sqlalchemy.orm import Session
from models.device_model import Device
from datetime import datetime

class DeviceService:
    @staticmethod
    def register_device(
        db: Session,
        user_id: int,
        platform: str,
        device_token: str = None,
        device_name: str = None,
        manufacturer: str = None,
        model: str = None,
        os_version: str = None,
        app_version: str = None,
        language: str = None,
        timezone: str = None
    ) -> Device:
        # If token exists, try to update the existing one
        if device_token:
            existing = db.query(Device).filter(Device.device_token == device_token).first()
            if existing:
                existing.user_id = user_id
                existing.last_seen = datetime.utcnow()
                existing.is_active = True
                
                # Update provided metadata
                if device_name: existing.device_name = device_name
                if manufacturer: existing.manufacturer = manufacturer
                if model: existing.model = model
                if os_version: existing.os_version = os_version
                if app_version: existing.app_version = app_version
                if language: existing.language = language
                if timezone: existing.timezone = timezone
                
                db.commit()
                db.refresh(existing)
                return existing

        # Create new device
        new_device = Device(
            user_id=user_id,
            platform=platform,
            device_token=device_token,
            device_name=device_name,
            manufacturer=manufacturer,
            model=model,
            os_version=os_version,
            app_version=app_version,
            language=language,
            timezone=timezone
        )
        db.add(new_device)
        db.commit()
        db.refresh(new_device)
        return new_device

    @staticmethod
    def update_device(
        db: Session,
        user_id: int,
        device_id: int,
        device_token: str = None,
        is_active: bool = None
    ) -> Device:
        device = db.query(Device).filter(Device.id == device_id, Device.user_id == user_id).first()
        if not device:
            return None
            
        if device_token is not None:
            device.device_token = device_token
        if is_active is not None:
            device.is_active = is_active
            
        device.last_seen = datetime.utcnow()
        db.commit()
        db.refresh(device)
        return device

    @staticmethod
    def deactivate_device(db: Session, user_id: int, device_id: int) -> bool:
        device = db.query(Device).filter(Device.id == device_id, Device.user_id == user_id).first()
        if not device:
            return False
            
        device.is_active = False
        db.commit()
        return True

    @staticmethod
    def delete_device(db: Session, user_id: int, device_id: int) -> bool:
        device = db.query(Device).filter(Device.id == device_id, Device.user_id == user_id).first()
        if not device:
            return False
            
        db.delete(device)
        db.commit()
        return True

    @staticmethod
    def get_active_devices(db: Session, user_id: int):
        return db.query(Device).filter(Device.user_id == user_id, Device.is_active == True).all()

    @staticmethod
    def get_devices_by_platform(db: Session, user_id: int, platform: str):
        return db.query(Device).filter(
            Device.user_id == user_id, 
            Device.platform == platform,
            Device.is_active == True
        ).all()
