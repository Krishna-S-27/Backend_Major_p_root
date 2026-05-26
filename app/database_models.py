"""
SQLAlchemy ORM models for database tables
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, ForeignKey, Text, BigInteger, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base  # ← FIXED: Use relative import

# ===================== USER MODEL =====================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    emergency_phone = Column(String(20))
    emergency_email = Column(String(100))
    drive_folder_id = Column(String(255))
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    
    profile_picture_url = Column(String(255))
    
    role = Column(String(20), default="USER", index=True)
    
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    incidents = relationship(
        "Incident",
        back_populates="user",
        foreign_keys="Incident.user_id",
        cascade="all, delete-orphan"
    )
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    device_tokens = relationship("DeviceToken", back_populates="user", cascade="all, delete-orphan")

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    bio = Column(Text)
    organization = Column(String(255))
    location_latitude = Column(Float)
    location_longitude = Column(Float)
    
    google_drive_folder_id = Column(String(255))
    google_drive_sync_enabled = Column(Boolean, default=True)
    
    notifications_enabled = Column(Boolean, default=True)
    email_alerts = Column(Boolean, default=True)
    
    total_incidents = Column(Integer, default=0)
    total_videos_saved = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="profile")

# ===================== INCIDENT MODEL =====================

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    detection_type = Column(String(20), nullable=False)
    prediction = Column(String(50), nullable=False, index=True)
    confidence = Column(Float, nullable=False, index=True)
    
    video_duration_seconds = Column(Integer)
    frame_count = Column(Integer)
    
    preprocessing_time_ms = Column(Integer)
    inference_time_ms = Column(Integer)
    total_time_ms = Column(Integer)
    
    latitude = Column(Float)
    longitude = Column(Float)
    location_name = Column(String(255))
    
    video_file_name = Column(String(255))
    video_file_path = Column(String(255))
    video_google_drive_id = Column(String(255))
    video_google_drive_link = Column(String(500))
    video_size_bytes = Column(BigInteger)
    
    is_uploaded_to_drive = Column(Boolean, default=False)
    upload_status = Column(String(20), default="PENDING", index=True)
    upload_error_message = Column(Text)
    
    is_reviewed_by_admin = Column(Boolean, default=False)
    admin_notes = Column(Text)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    is_marked_for_police = Column(Boolean, default=False)
    police_reference_number = Column(String(50))
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship(
        "User",
        back_populates="incidents",
        foreign_keys=[user_id],
        primaryjoin="User.id==Incident.user_id"
    )

# ===================== NOTIFICATION MODEL =====================

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), default="INCIDENT_DETECTED")
    
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    
    is_read = Column(Boolean, default=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="notifications")

# ===================== DEVICE TOKEN MODEL =====================

class DeviceToken(Base):
    __tablename__ = "device_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    device_token = Column(String(255), unique=True, nullable=False)
    device_type = Column(String(20), default="ANDROID")
    device_name = Column(String(255))
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="device_tokens")

# ===================== AUDIT LOG MODEL =====================

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(Integer)
    details = Column(JSON)
    ip_address = Column(String(45))
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
