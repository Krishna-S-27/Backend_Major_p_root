"""
Authentication and authorization logic
JWT token generation and validation
Password hashing
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# ===================== CONFIGURATION =====================

SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production-min-32-chars')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing - use rounds=4 for bcrypt to handle edge cases
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=4  # Lower rounds to ensure we don't exceed 72 bytes
)

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)

# ===================== PASSWORD FUNCTIONS =====================

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt
    Handles long passwords by truncating to 72 bytes
    
    @param password: Plain text password
    @return: Hashed password
    """
    # Bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password = password_bytes[:72].decode('utf-8', errors='ignore')
        logger.warning("Password truncated to 72 bytes for bcrypt compatibility")
    
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash
    
    @param plain_password: Plain text password
    @param hashed_password: Hashed password from database
    @return: True if valid, False otherwise
    """
    # Truncate to 72 bytes if necessary (same as hashing)
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        plain_password = password_bytes[:72].decode('utf-8', errors='ignore')
    
    return pwd_context.verify(plain_password, hashed_password)

# ===================== JWT TOKEN FUNCTIONS =====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    
    @param data: Data to encode in token
    @param expires_delta: Token expiration time
    @return: JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Access token created for user: {data.get('sub')}")
    
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """
    Create JWT refresh token
    
    @param data: Data to encode in token
    @return: JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Refresh token created for user: {data.get('sub')}")
    
    return encoded_jwt

def verify_token(token: str) -> dict:
    """
    Verify and decode JWT token
    
    @param token: JWT token
    @return: Decoded token data
    @raise: HTTPException if token invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        return payload
        
    except JWTError as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# ===================== DEPENDENCY FUNCTIONS =====================

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Get current authenticated user from token
    
    @param credentials: HTTP Bearer credentials
    @return: User data from token
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Send: Authorization: Bearer <access_token>",
        )

    token = credentials.credentials
    payload = verify_token(token)
    return payload

async def get_current_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Get current user and verify admin role
    
    @param current_user: Current user data
    @return: User data if admin
    @raise: HTTPException if not admin
    """
    if current_user.get("role") != "ADMIN":
        logger.warning(f"Non-admin user {current_user.get('sub')} attempted admin action")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user
