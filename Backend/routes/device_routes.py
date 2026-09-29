from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.user_model import User
from auth.auth2 import get_current_user
from services.device_service import DeviceService
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/devices", tags=["Devices"])

class DeviceRegister(BaseModel):
    platform: str
    device_token: Optional[str] = None
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None

class DeviceUpdate(BaseModel):
    device_token: Optional[str] = None
    is_active: Optional[bool] = None

@router.post("/register")
def register_device(
    device_data: DeviceRegister,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if device_data.platform not in ["android", "ios", "web"]:
        raise HTTPException(status_code=400, detail="Invalid platform")

    device = DeviceService.register_device(
        db=db,
        user_id=current_user.id,
        platform=device_data.platform,
        device_token=device_data.device_token,
        device_name=device_data.device_name,
        manufacturer=device_data.manufacturer,
        model=device_data.model,
        os_version=device_data.os_version,
        app_version=device_data.app_version,
        language=device_data.language,
        timezone=device_data.timezone
    )
    return {"message": "Device registered successfully", "id": device.id}

@router.put("/update/{device_id}")
def update_device(
    device_id: int,
    device_data: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = DeviceService.update_device(
        db, current_user.id, device_id, 
        device_data.device_token, device_data.is_active
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    return {"message": "Device updated successfully"}

@router.delete("/unregister/{device_id}")
def unregister_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success = DeviceService.delete_device(db, current_user.id, device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
        
    return {"message": "Device unregistered successfully"}

@router.get("/")
def get_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    devices = DeviceService.get_active_devices(db, current_user.id)
    return {"devices": devices}

@router.get("/platform/{platform}")
def get_devices_by_platform(
    platform: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    devices = DeviceService.get_devices_by_platform(db, current_user.id, platform)
    return {"devices": devices}

