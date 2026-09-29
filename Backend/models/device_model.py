from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    # Platform info
    platform = Column(String(50), nullable=False) # 'android', 'ios', 'web'
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(50), nullable=True)
    device_name = Column(String(100), nullable=True)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    language = Column(String(20), nullable=True)
    timezone = Column(String(50), nullable=True)
    
    # Delivery info
    device_token = Column(String(255), nullable=True, unique=True, index=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    owner = relationship("User")
