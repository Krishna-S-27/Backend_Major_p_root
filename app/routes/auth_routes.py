"""
Authentication routes for login, register, profile
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import logging
import os
import random
import smtplib
import time
from email.mime.text import MIMEText

from app.database import get_db
from app.database_models import User, UserProfile
from app.models import (
    UserRegisterRequest, UserLoginRequest, AuthResponse,
    UserResponse, UserProfileResponse, UserProfileUpdate,
    SendOtpRequest, VerifyOtpRequest
)
from app.auth import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, get_current_user
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
otp_storage = {}
OTP_EXPIRY_SECONDS = 300

SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "")


def send_real_email(to_email: str, body: str, subject: str = "CrimeDetection Alert") -> bool:
    """Send an email notification when SMTP_USER and SMTP_PASS are configured."""
    if not SMTP_USER or not SMTP_PASS:
        return False

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to_email

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        return True
    except Exception as e:
        logger.warning(f"Email delivery failed for {to_email}: {e}")
        return False


def send_real_sms(to_phone: str, body: str) -> bool:
    """Send an SMS notification when Twilio environment variables are configured."""
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_PHONE:
        return False

    try:
        from twilio.rest import Client

        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            body=body,
            from_=TWILIO_PHONE,
            to=to_phone
        )
        return True
    except ImportError:
        logger.warning("Twilio package is not installed; using OTP development fallback")
        return False
    except Exception as e:
        logger.warning(f"SMS OTP delivery failed for {to_phone}: {e}")
        return False

# ===================== OTP ENDPOINTS =====================

@router.post("/send-otp", status_code=status.HTTP_200_OK)
async def send_otp(request: SendOtpRequest):
    """
    Send an OTP to a phone number or email address.

    Tries real SMS/email delivery when credentials are configured. If delivery
    is unavailable, returns DEV_MODE_OTP:<code> so the Android app can auto-fill.
    """

    otp_code = f"{random.randint(100000, 999999)}"
    otp_storage[request.target] = {
        "otp": otp_code,
        "type": request.type.value,
        "expiry": time.time() + OTP_EXPIRY_SECONDS
    }

    print(f"DEBUG: Generated OTP {otp_code} for {request.target}")

    sent = False
    if request.type.value == "phone":
        sent = send_real_sms(request.target, otp_code)
    elif request.type.value == "email":
        sent = send_real_email(request.target, otp_code)

    if sent:
        return {
            "message": "OTP sent successfully",
            "success": True
        }

    return {
        "message": f"DEV_MODE_OTP:{otp_code}",
        "success": True
    }


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp(request: VerifyOtpRequest):
    """Verify a one-time password sent by /auth/send-otp."""

    record = otp_storage.get(request.target)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP requested for this target"
        )

    if time.time() > record["expiry"]:
        del otp_storage[request.target]
        return {"message": "OTP expired", "success": False}

    if record["otp"] != request.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code"
        )

    del otp_storage[request.target]
    return {"message": "Verified", "success": True}

# ===================== REGISTER ENDPOINT =====================

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Register new user
    
    - Creates user with hashed password
    - Creates user profile
    - Returns access token
    """
    
    logger.info(f"Registration attempt for username: {request.username}")
    
    try:
        # Check if user exists
        existing_user = db.query(User).filter(
            (User.username == request.username) | (User.email == request.email)
        ).first()
        
        if existing_user:
            logger.warning(f"Registration failed: user {request.username} already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered"
            )
        
        # Create user
        user = User(
            username=request.username,
            email=request.email,
            password_hash=hash_password(request.password),
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            emergency_phone=request.emergency_phone,
            emergency_email=str(request.emergency_email),
            is_verified=True  # Auto-verify for now
        )
        
        db.add(user)
        db.flush()  # Get user ID without committing
        
        # Create profile
        profile = UserProfile(
            user_id=user.id
        )
        db.add(profile)
        
        db.commit()
        db.refresh(user)
        
        logger.info(f"✓ User registered: {user.username} (ID: {user.id})")
        
        # Generate token
        access_token = create_access_token(
            data={"sub": user.username, "id": user.id, "role": user.role}
        )
        
        user_response = UserResponse.from_orm(user)
        
        return AuthResponse(
            access_token=access_token,
            user=user_response
        )
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed"
        )

# ===================== LOGIN ENDPOINT =====================

@router.post("/login", response_model=AuthResponse)
async def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """
    User login
    
    - Validates username and password
    - Returns access token
    """
    
    logger.info(f"Login attempt for username: {request.username}")
    
    # Find user
    user = db.query(User).filter(User.username == request.username).first()
    
    if not user or not verify_password(request.password, user.password_hash):
        logger.warning(f"Login failed for username: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not user.is_active:
        logger.warning(f"Login attempt on inactive user: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    logger.info(f"✓ User logged in: {user.username}")
    
    # Generate token
    access_token = create_access_token(
        data={"sub": user.username, "id": user.id, "role": user.role}
    )
    
    user_response = UserResponse.from_orm(user)
    
    return AuthResponse(
        access_token=access_token,
        user=user_response
    )

# ===================== PROFILE ENDPOINTS =====================

@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user profile
    """
    
    user = db.query(User).filter(User.id == current_user["id"]).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    profile = user.profile
    
    return UserProfileResponse(
        user=UserResponse.from_orm(user),
        bio=profile.bio if profile else None,
        organization=profile.organization if profile else None,
        drive_folder_id=(
            profile.google_drive_folder_id
            if profile and profile.google_drive_folder_id
            else user.drive_folder_id
        ),
        total_incidents=profile.total_incidents if profile else 0,
        total_videos_saved=profile.total_videos_saved if profile else 0,
        notifications_enabled=profile.notifications_enabled if profile else True,
        email_alerts=profile.email_alerts if profile else True
    )

@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    request: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile
    """
    
    user = db.query(User).filter(User.id == current_user["id"]).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    new_phone = request.phone or user.phone
    new_emergency_phone = request.emergency_phone or user.emergency_phone
    if new_phone and new_emergency_phone and new_phone == new_emergency_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Emergency phone must be different from user phone"
        )

    # Update user fields
    if request.first_name:
        user.first_name = request.first_name
    if request.last_name:
        user.last_name = request.last_name
    if request.phone:
        user.phone = request.phone
    if request.emergency_phone:
        user.emergency_phone = request.emergency_phone
    if request.emergency_email:
        user.emergency_email = str(request.emergency_email)
    if request.drive_folder_id:
        user.drive_folder_id = request.drive_folder_id
    if request.address:
        user.address = request.address
    if request.city:
        user.city = request.city
    if request.state:
        user.state = request.state
    if request.country:
        user.country = request.country
    if request.postal_code:
        user.postal_code = request.postal_code
    
    # Update profile fields
    if user.profile:
        if request.bio:
            user.profile.bio = request.bio
        if request.organization:
            user.profile.organization = request.organization
        if request.drive_folder_id:
            user.profile.google_drive_folder_id = request.drive_folder_id
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    logger.info(f"✓ Profile updated for user: {user.username}")
    
    profile = user.profile
    
    return UserProfileResponse(
        user=UserResponse.from_orm(user),
        bio=profile.bio if profile else None,
        organization=profile.organization if profile else None,
        drive_folder_id=(
            profile.google_drive_folder_id
            if profile and profile.google_drive_folder_id
            else user.drive_folder_id
        ),
        total_incidents=profile.total_incidents if profile else 0,
        total_videos_saved=profile.total_videos_saved if profile else 0,
        notifications_enabled=profile.notifications_enabled if profile else True,
        email_alerts=profile.email_alerts if profile else True
    )
