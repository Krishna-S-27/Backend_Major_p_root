"""
Violence Detection API - Complete Backend
Includes:
- User Authentication (Register/Login)
- Batch Video Prediction
- Real-time Frame-based Prediction
- Incident Management
- Google Drive Auto-upload
- Admin Dashboard
- Database Integration
"""
import os
import tempfile
import logging
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor
import struct
from datetime import datetime

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from tensorflow import keras
import uvicorn
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# ===================== LOCAL IMPORTS =====================

from app.database import get_db, init_db
from app.auth import get_current_user
from app.routes import auth_routes, prediction_routes, incident_routes, admin_routes
from app.routes.auth_routes import send_real_sms, send_real_email
from app.routes.reports import router as reports_router
from app.models import AuthResponse, IncidentCreateRequest
from app.database_models import Incident, User, UserProfile, Notification
from app.utils.logger import setup_logger

load_dotenv()

# ===================== CONFIGURATION =====================

BASE_DIR = Path(__file__).resolve().parent
MODEL_ROOT = BASE_DIR / "exports_v2" / "exports_v2"

H5_MODEL_PATH = MODEL_ROOT / "violence_model_v2.h5"

# Frame processing parameters
FRAMES_REQUIRED = 16
FRAME_SIZE = 224
NORMALIZATION = 255.0

TWILIO_SID = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "")

# Configure logging
logger = setup_logger("main")

# ===================== GLOBAL STATE =====================

model = None
model_type = None
temp_cleanup_executor = ThreadPoolExecutor(max_workers=2)

# ===================== MODEL LOADING =====================

def load_model_optimized():
    """Load the H5 inference model used by every prediction endpoint."""
    global model, model_type
    
    logger.info("Initializing H5 model loading...")

    if not os.path.exists(H5_MODEL_PATH):
        raise FileNotFoundError(f"H5 model not found: {H5_MODEL_PATH}")

    try:
        logger.info(f"Loading Keras H5 model: {H5_MODEL_PATH}")
        model = _load_keras_h5_model(H5_MODEL_PATH)
        model_type = "keras_h5"
        logger.info("✓ Keras H5 model loaded successfully")
    except Exception as e:
        logger.error(f"H5 model loading failed: {e}")
        raise RuntimeError(f"Could not load H5 model from {H5_MODEL_PATH}") from e


def _load_keras_h5_model(model_path: Path):
    """Load legacy H5 exports with config keys unsupported by this Keras version."""
    class LegacyLayerMixin:
        @staticmethod
        def clean_kwargs(kwargs):
            kwargs.pop("quantization_config", None)
            return kwargs

    class LegacyBatchNormalization(LegacyLayerMixin, keras.layers.BatchNormalization):
        def __init__(self, *args, **kwargs):
            kwargs = self.clean_kwargs(kwargs)
            kwargs.pop("renorm", None)
            kwargs.pop("renorm_clipping", None)
            kwargs.pop("renorm_momentum", None)
            super().__init__(*args, **kwargs)

    class LegacyDense(LegacyLayerMixin, keras.layers.Dense):
        def __init__(self, *args, **kwargs):
            kwargs = self.clean_kwargs(kwargs)
            super().__init__(*args, **kwargs)

    return keras.models.load_model(
        model_path,
        compile=False,
        custom_objects={
            "BatchNormalization": LegacyBatchNormalization,
            "Dense": LegacyDense,
        },
    )


# ===================== PREPROCESSING =====================

def preprocess_video(video_path: str) -> np.ndarray:
    """
    Preprocess video with uniform sampling
    
    Input: Video file path
    Output: (1, 16, 224, 224, 3) normalized float array
    """
    start_time = time.time()
    logger.info(f"Starting video preprocessing: {video_path}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video file")
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    logger.info(f"Video info: {total_frames} frames @ {fps} fps")
    
    if total_frames < FRAMES_REQUIRED:
        cap.release()
        raise ValueError(f"Video requires minimum {FRAMES_REQUIRED} frames, got {total_frames}")
    
    step = total_frames // FRAMES_REQUIRED
    logger.info(f"Sampling strategy: Every {step}th frame from {total_frames} total")
    
    frames = []
    for i in range(FRAMES_REQUIRED):
        frame_idx = i * step
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            cap.release()
            raise ValueError(f"Failed to extract frame at index {frame_idx}")
        
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (FRAME_SIZE, FRAME_SIZE))
        frame = frame.astype(np.float32) / NORMALIZATION
        frames.append(frame)
    
    cap.release()
    
    frames_array = np.array(frames, dtype=np.float32)
    frames_array = np.expand_dims(frames_array, axis=0)
    
    processing_time = time.time() - start_time
    logger.info(f"Preprocessing complete: shape={frames_array.shape}, time={processing_time:.2f}s")
    
    return frames_array

def preprocess_frame_buffer(frame_buffer: np.ndarray) -> np.ndarray:
    """Preprocess real-time frame buffer"""
    logger.info(f"Preprocessing frame buffer: shape={frame_buffer.shape}")
    
    if frame_buffer.shape != (1, 16, FRAME_SIZE, FRAME_SIZE, 3):
        raise ValueError(f"Invalid frame buffer shape: {frame_buffer.shape}")
    
    if frame_buffer.dtype != np.float32:
        logger.warning(f"Converting dtype from {frame_buffer.dtype} to float32")
        frame_buffer = frame_buffer.astype(np.float32)
    
    min_val = np.min(frame_buffer)
    max_val = np.max(frame_buffer)
    
    if min_val < 0 or max_val > 1.0:
        logger.warning(f"Frame values outside [0, 1]: min={min_val}, max={max_val}")
        if max_val > 1.0:
            frame_buffer = frame_buffer / 255.0
            logger.info("Auto-normalized frame buffer")
    
    logger.info(f"✓ Frame buffer validated: shape={frame_buffer.shape}")
    return frame_buffer

# ===================== MODEL INFERENCE =====================

def predict_violence(frames: np.ndarray) -> dict:
    """Run inference on frames"""
    global model, model_type
    
    if model is None:
        raise RuntimeError("Model not loaded")
    
    start_time = time.time()
    logger.info(f"Running inference with {model_type} model (input shape: {frames.shape})")
    
    try:
        import tensorflow as tf
        input_tensor = tf.constant(frames, dtype=tf.float32)
        output = model(input_tensor, training=False)
        
        output_array = output.numpy() if hasattr(output, 'numpy') else np.asarray(output)
        confidence = float(output_array.reshape(-1)[0])
        
        inference_time = time.time() - start_time
        prediction = "VIOLENT" if confidence >= 0.5 else "NONVIOLENT"
        
        logger.info(f"Inference complete: {prediction} ({confidence:.4f}), time={inference_time:.2f}s")
        
        return {
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "inference_time_ms": round(inference_time * 1000, 2),
            "model_type": model_type,
            "total_time_ms": round(inference_time * 1000, 2)
        }
    
    except Exception as e:
        logger.error(f"Inference error: {str(e)}")
        raise RuntimeError(f"Model inference failed: {str(e)}")

# ===================== CLEANUP =====================

def cleanup_temp_file(filepath: str):
    """Background cleanup"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"✓ Cleaned up: {filepath}")
    except Exception as e:
        logger.warning(f"Cleanup failed for {filepath}: {e}")


def build_whatsapp_share_url(phone_number: Optional[str], message: str) -> str:
    encoded_message = quote_plus(message)
    if phone_number:
        clean_phone = phone_number.strip().lstrip("+").replace(" ", "")
        return f"https://wa.me/{clean_phone}?text={encoded_message}"
    return f"https://api.whatsapp.com/send?text={encoded_message}"


def send_whatsapp_message(to_number: str, body: str) -> bool:
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_PHONE:
        logger.warning("Twilio WhatsApp is not configured")
        return False

    try:
        from twilio.rest import Client

        client = Client(TWILIO_SID, TWILIO_TOKEN)
        whatsapp_from = f"whatsapp:{TWILIO_PHONE}"
        whatsapp_to = f"whatsapp:{to_number}"

        message = client.messages.create(
            body=body,
            from_=whatsapp_from,
            to=whatsapp_to
        )
        logger.info(f"✓ WhatsApp message sent: {message.sid}")
        return True
    except ImportError:
        logger.warning("Twilio package is not installed; WhatsApp send skipped")
        return False
    except Exception as e:
        logger.warning(f"WhatsApp send failed: {e}")
        return False

# ===================== FASTAPI APPLICATION =====================

app = FastAPI(
    title="Violence Detection API",
    description="Production-ready ML backend with authentication and incident management",
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== INCLUDE ROUTERS =====================

app.include_router(auth_routes.router)
app.include_router(incident_routes.router)
app.include_router(prediction_routes.router)
app.include_router(admin_routes.router)
app.include_router(reports_router)
app.add_api_route(
    "/api/register",
    auth_routes.register,
    methods=["POST"],
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
)

# ===================== STARTUP & SHUTDOWN =====================

@app.on_event("startup")
async def startup():
    """Load model and initialize on startup"""
    try:
        load_model_optimized()
        init_db()
        logger.info("🚀 API Ready for requests")
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    temp_cleanup_executor.shutdown(wait=True)

# ===================== BATCH PREDICTION ENDPOINT =====================

@app.post("/predict", status_code=status.HTTP_200_OK)
async def predict(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Batch prediction endpoint
    
    Upload video file and get violence prediction
    Requires authentication
    
    - Input: Video file
    - Output: Prediction with confidence
    - Automatically saves incident to database
    - If violent, schedules Google Drive upload
    """
    
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    allowed_ext = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Allowed: {', '.join(allowed_ext)}"
        )
    
    request_start = time.time()
    temp_path = None
    
    try:
        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            temp_path = tmp.name
            content = await file.read()
            tmp.write(content)
        
        logger.info(f"Upload received: {file.filename} ({len(content)/1024/1024:.2f}MB)")
        
        # Preprocess
        frames = preprocess_video(temp_path)
        
        # Inference
        result = predict_violence(frames)
        
        total_time = time.time() - request_start
        
        # Get video info
        from app.utils.video_handler import VideoHandler
        video_info = VideoHandler.get_video_info(temp_path)
        
        # Create incident
        incident = Incident(
            user_id=current_user["id"],
            detection_type="BATCH",
            prediction=result["prediction"],
            confidence=result["confidence"],
            video_file_name=file.filename,
            video_file_path=temp_path,
            video_duration_seconds=int(video_info['duration_seconds']),
            frame_count=video_info['total_frames'],
            preprocessing_time_ms=0,
            inference_time_ms=result["inference_time_ms"],
            total_time_ms=round(total_time * 1000, 2),
            upload_status="LOCAL"
        )
        db.add(incident)
        db.flush()
        
        incident_id = incident.id
        
        # Update user profile
        user_profile = db.query(UserProfile).filter(
            UserProfile.user_id == current_user["id"]
        ).first()
        if user_profile:
            user_profile.total_incidents += 1
            if result["prediction"] == "VIOLENT":
                user_profile.total_videos_saved += 1
        
        db.commit()
        
        alert_message = ""
        share_whatsapp_video = False
        if result["prediction"] == "VIOLENT":
            alert_message = (
                "CRITICAL: Violence detected. Save the video locally and "
                "notify emergency contacts via WhatsApp."
            )
            share_whatsapp_video = True

        response = {
            "success": True,
            "prediction": result["prediction"],
            "confidence": result["confidence"],
            "inference_time_ms": result["inference_time_ms"],
            "total_time_ms": round(total_time * 1000, 2),
            "incident_id": incident_id,
            "filename": file.filename,
            "model_type": result["model_type"],
            "alert_message": alert_message,
            "share_whatsapp_video": share_whatsapp_video,
            "local_save_folder": "CrimeDetection"
        }
        
        logger.info(f"✓ Batch prediction complete: {response}")
        return JSONResponse(status_code=200, content=response)
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Batch prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if temp_path and background_tasks:
            background_tasks.add_task(cleanup_temp_file, temp_path)

# ===================== REALTIME PREDICTION ENDPOINT =====================

@app.post("/predict-realtime", status_code=status.HTTP_200_OK)
async def predict_realtime(
    file: UploadFile = File(...),
    fps: Optional[float] = Form(None),
    buffer_count: Optional[int] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Real-time prediction endpoint
    
    Accepts pre-processed frame buffer from Android

    - Input: Binary frame buffer (float32 or uint8)
    - Shape: (1, 16, 224, 224, 3)
    - Already normalized (0-1) or raw RGB bytes
    Every 8 frames triggers a new prediction
    """
    
    if not file:
        raise HTTPException(status_code=400, detail="No frames provided")
    
    request_start = time.time()
    
    try:
        content = await file.read()
        logger.info(f"Real-time prediction request ({len(content)} bytes)")

        # Convert bytes to array. Accept either raw uint8 RGB bytes or float32 serialized frames.
        expected_bytes = 1 * 16 * 224 * 224 * 3
        if len(content) == expected_bytes:
            frames_array = np.frombuffer(content, dtype=np.uint8)
        elif len(content) == expected_bytes * 4:
            frames_array = np.frombuffer(content, dtype=np.float32)
        else:
            raise ValueError(
                f"Frame byte size mismatch: {len(content)} vs {expected_bytes} or {expected_bytes * 4}"
            )

        expected_size = expected_bytes // (4 if frames_array.dtype == np.float32 else 1)
        if len(frames_array) != expected_size:
            raise ValueError(
                f"Frame size mismatch: {len(frames_array)} vs {expected_size}"
            )

        # Reshape
        frames_array = frames_array.reshape((1, 16, 224, 224, 3))
        frames_array = preprocess_frame_buffer(frames_array)
        
        # Inference
        result = predict_violence(frames_array)
        total_time = time.time() - request_start
        
        # Create incident
        incident = Incident(
            user_id=current_user["id"],
            detection_type="REALTIME",
            prediction=result["prediction"],
            confidence=result["confidence"],
            inference_time_ms=result["inference_time_ms"],
            total_time_ms=round(total_time * 1000, 2),
            upload_status="PENDING"
        )
        db.add(incident)
        db.commit()

        alert_message = ""
        user = None
        whatsapp_sent = False
        whatsapp_share_url = ""
        if result["prediction"] == "VIOLENT" and result["confidence"] > 0.85:
            alert_message = "CRITICAL: Violence detected! Notifying emergency contacts."
            user = db.query(User).filter(User.id == current_user["id"]).first()

            sms_body = (
                "Emergency alert from CrimeDetection: violence detected. "
                "Please contact the user immediately."
            )
            email_body = (
                "Emergency alert from CrimeDetection. "
                "Violence has been detected and you should check on the user immediately."
            )
            whatsapp_body = (
                "CrimeDetection Emergency Alert: violence detected. "
                "Please review the incident and contact the user immediately."
            )

            if user:
                if user.emergency_phone:
                    sent_sms = send_real_sms(user.emergency_phone, sms_body)
                    logger.info(f"Emergency SMS sent={sent_sms} to {user.emergency_phone}")
                    whatsapp_sent = send_whatsapp_message(user.emergency_phone, whatsapp_body)
                    logger.info(f"Emergency WhatsApp sent={whatsapp_sent} to {user.emergency_phone}")

                if user.emergency_email:
                    sent_email = send_real_email(
                        user.emergency_email,
                        email_body,
                        subject="CrimeDetection Emergency Alert"
                    )
                    logger.info(f"Emergency email sent={sent_email} to {user.emergency_email}")

            whatsapp_share_url = build_whatsapp_share_url(
                user.emergency_phone if user and user.emergency_phone else None,
                whatsapp_body
            )

        alert_message = alert_message or ""
        share_whatsapp_video = result["prediction"] == "VIOLENT" and result["confidence"] > 0.85

        response = {
            "success": True,
            "prediction": result["prediction"],
            "confidence": result["confidence"],
            "inference_time_ms": result["inference_time_ms"],
            "total_time_ms": round(total_time * 1000, 2),
            "incident_id": incident.id,
            "type": "realtime",
            "frame_count": FRAMES_REQUIRED,
            "fps": fps or 0,
            "buffer_count": buffer_count or 0,
            "detection_status": result["prediction"],
            "alert_message": alert_message,
            "share_whatsapp_video": share_whatsapp_video,
            "whatsapp_sent": whatsapp_sent,
            "whatsapp_share_url": whatsapp_share_url,
            "local_save_folder": "CrimeDetection"
        }
        
        logger.info(f"✓ Real-time prediction: {result['prediction']}")
        return JSONResponse(status_code=200, content=response)
    
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Real-time error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================== BACKGROUND TASK FOR UPLOAD =====================


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if model is not None else "unhealthy",
        "model_loaded": model is not None,
        "model_type": model_type,
        "api_version": "5.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/stats", status_code=status.HTTP_200_OK)
async def get_stats():
    """Server statistics"""
    return {
        "status": "ready" if model is not None else "not_loaded",
        "model_loaded": model is not None,
        "model_type": model_type,
        "api_version": "5.0.0",
        "frames_required": FRAMES_REQUIRED,
        "frame_size": FRAME_SIZE,
        "normalization": NORMALIZATION
    }

@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """API information"""
    return {
        "service": "Violence Detection API",
        "version": "5.0.0",
        "status": "operational",
        "endpoints": {
            "authentication": {
                "register": "POST /auth/register",
                "login": "POST /auth/login",
                "profile": "GET /auth/profile"
            },
            "predictions": {
                "batch": "POST /predict (requires auth)",
                "realtime": "POST /predict-realtime (requires auth)"
            },
            "incidents": {
                "list": "GET /api/v1/incidents/list (requires auth)",
                "details": "GET /api/v1/incidents/{id} (requires auth)",
                "delete": "DELETE /api/v1/incidents/{id} (requires auth)",
                "statistics": "GET /api/v1/incidents/user/statistics (requires auth)"
            },
            "admin": {
                "dashboard": "GET /api/v1/admin/dashboard (admin only)",
                "users": "GET /api/v1/admin/users (admin only)"
            },
            "system": {
                "health": "GET /health",
                "stats": "GET /stats"
            }
        },
        "documentation": {
            "swagger": "GET /docs",
            "redoc": "GET /redoc"
        }
    }

# ===================== ENTRY POINT =====================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", 8000)),
        workers=4,
        log_level="info"
    )
