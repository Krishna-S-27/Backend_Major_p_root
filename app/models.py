"""
Pydantic models for FastAPI
Request/Response validation
"""

from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ===================== ENUMS =====================

class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"

class DetectionType(str, Enum):
    REALTIME = "REALTIME"
    BATCH = "BATCH"

class UploadStatus(str, Enum):
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class OtpType(str, Enum):
    PHONE = "phone"
    EMAIL = "email"

# ===================== OTP MODELS =====================

class SendOtpRequest(BaseModel):
    """Request to send an OTP to a phone number or email address"""
    target: str
    type: OtpType

    @validator('target')
    def target_valid(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('Target is required')
        return cleaned

class VerifyOtpRequest(BaseModel):
    """Request to verify a previously sent OTP"""
    target: str
    otp: str

    @validator('target')
    def verify_target_valid(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('Target is required')
        return cleaned

    @validator('otp')
    def otp_valid(cls, v):
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('OTP is required')
        if not cleaned.isdigit() or len(cleaned) != 6:
            raise ValueError('OTP must be a 6-digit code')
        return cleaned

# ===================== USER MODELS =====================

class UserRegisterRequest(BaseModel):
    """User registration request"""
    first_name: str
    last_name: str
    username: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    emergency_phone: str
    emergency_email: EmailStr
    
    @validator('username')
    def username_valid(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v
    
    @validator('password')
    def password_valid(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

    @validator('phone', 'emergency_phone')
    def phone_valid(cls, v):
        if v is None:
            return v
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('Phone number cannot be empty')
        return cleaned

    @validator('emergency_phone')
    def emergency_phone_different(cls, v, values):
        phone = values.get('phone')
        if phone and v and phone == v:
            raise ValueError('Emergency phone must be different from user phone')
        return v

class UserLoginRequest(BaseModel):
    """User login request"""
    username: str
    password: str

class UserResponse(BaseModel):
    """User response (without password)"""
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    emergency_phone: Optional[str]
    emergency_email: Optional[str]
    profile_picture_url: Optional[str]
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    """Authentication response with token"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class UserProfileUpdate(BaseModel):
    """Update user profile"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    emergency_phone: Optional[str] = None
    emergency_email: Optional[EmailStr] = None
    drive_folder_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    bio: Optional[str] = None
    organization: Optional[str] = None

    @validator('emergency_phone')
    def profile_emergency_phone_different(cls, v, values):
        phone = values.get('phone')
        if phone and v and phone == v:
            raise ValueError('Emergency phone must be different from user phone')
        return v

class UserProfileResponse(BaseModel):
    """Complete user profile response"""
    user: UserResponse
    bio: Optional[str]
    organization: Optional[str]
    drive_folder_id: Optional[str]
    total_incidents: int
    total_videos_saved: int
    notifications_enabled: bool
    email_alerts: bool

# ===================== INCIDENT MODELS =====================

class IncidentCreateRequest(BaseModel):
    """Create incident from detection"""
    detection_type: DetectionType
    prediction: str  # "VIOLENT" or "NONVIOLENT"
    confidence: float
    video_file_name: str
    video_file_path: Optional[str] = None
    video_duration_seconds: Optional[int] = None
    frame_count: Optional[int] = None
    preprocessing_time_ms: Optional[int] = None
    inference_time_ms: Optional[int] = None
    total_time_ms: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None

class IncidentResponse(BaseModel):
    """Incident response"""
    id: int
    user_id: int
    detection_type: str
    prediction: str
    confidence: float
    video_file_name: str
    video_google_drive_link: Optional[str]
    is_uploaded_to_drive: bool
    upload_status: str
    is_marked_for_police: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class IncidentListResponse(BaseModel):
    """List of incidents with pagination"""
    total: int
    page: int
    page_size: int
    incidents: list[IncidentResponse]

class IncidentInReport(BaseModel):
    id: int
    detection_type: str
    prediction: str
    confidence: float
    location: Optional[str]
    emergency_response: bool
    timestamp: datetime

    class Config:
        orm_mode = True

class ReportResponse(BaseModel):
    total_incidents: int
    violent_incidents: int
    non_violent_incidents: int
    violent_percentage: float
    average_confidence: float
    accuracy_rate: float
    incidents: List[IncidentInReport]

# ===================== NOTIFICATION MODELS =====================

class NotificationResponse(BaseModel):
    """Notification response"""
    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# ===================== ADMIN MODELS =====================

class AdminDashboardStats(BaseModel):
    """Admin dashboard statistics"""
    total_users: int
    total_incidents: int
    violent_incidents_count: int
    pending_uploads: int
    pending_reviews: int
    average_confidence: Optional[float]
