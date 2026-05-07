import os
import tempfile
import logging
import time
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from tensorflow import keras
import uvicorn

# CONFIGURATION

BASE_DIR = Path(__file__).resolve().parent
MODEL_ROOT = BASE_DIR / "exports_v2" / "exports_v2"

MODEL_DIR = MODEL_ROOT / "violence_model_v2_savedmodel"
TFLITE_MODEL_PATH = MODEL_ROOT / "violence_model_v2.tflite"
KERAS_MODEL_PATH = MODEL_ROOT / "violence_model_v2.keras"
H5_MODEL_PATH = MODEL_ROOT / "violence_model_v2.h5"

# Frame processing parameters
FRAMES_REQUIRED = 16
FRAME_SIZE = 224
NORMALIZATION = 255.0

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# GLOBAL STATE (Loaded Once at Startup)

model = None
model_type = None  # 'keras', 'savedmodel', or 'tflite'
model_signature = None
temp_cleanup_executor = ThreadPoolExecutor(max_workers=2)

# MODEL LOADING

def load_model_optimized():
    """
    Load model with fallback strategy.
    Priority: TFLite > Keras > SavedModel
    TFLite is fastest for mobile inference.
    """
    global model, model_type, model_signature
    
    logger.info("Initializing model loading with fallback strategy...")
    
    # Try TFLite first (fastest for inference)
    if os.path.exists(TFLITE_MODEL_PATH):
        try:
            logger.info(f"Loading TFLite model: {TFLITE_MODEL_PATH}")
            import tensorflow as tf
            interpreter = tf.lite.Interpreter(model_path=str(TFLITE_MODEL_PATH))
            interpreter.allocate_tensors()
            model = interpreter
            model_type = "tflite"
            model_signature = None
            logger.info("✓ TFLite model loaded successfully (FASTEST)")
            return
        except Exception as e:
            logger.warning(f"TFLite loading failed: {e}. Trying Keras...")
    
    # Fallback to Keras (.keras or .h5)
    if os.path.exists(KERAS_MODEL_PATH):
        try:
            logger.info(f"Loading Keras model: {KERAS_MODEL_PATH}")
            model = keras.models.load_model(KERAS_MODEL_PATH)
            if hasattr(model, "signatures"):
                model_type = "savedmodel"
                model_signature = _get_savedmodel_signature(model)
                logger.info("✓ SavedModel-style Keras model loaded successfully")
            else:
                model_type = "keras"
                model_signature = None
                logger.info("✓ Keras model loaded successfully")
            return
        except Exception as e:
            logger.warning(f"Keras loading failed: {e}. Trying .h5 or SavedModel...")

    if os.path.exists(H5_MODEL_PATH):
        try:
            logger.info(f"Loading Keras H5 model: {H5_MODEL_PATH}")
            model = keras.models.load_model(H5_MODEL_PATH)
            model_type = "keras"
            model_signature = None
            logger.info("✓ Keras H5 model loaded successfully")
            return
        except Exception as e:
            logger.warning(f"H5 loading failed: {e}. Trying SavedModel...")

    # Final fallback to SavedModel
    try:
        logger.info(f"Loading SavedModel: {MODEL_DIR}")
        import tensorflow as tf
        model = tf.saved_model.load(str(MODEL_DIR))
        model_type = "savedmodel"
        model_signature = _get_savedmodel_signature(model)
        logger.info("✓ SavedModel loaded successfully")
        return
    except Exception as e:
        logger.error(f"All model loading attempts failed: {e}")
        raise Exception(
            f"Could not load model from {MODEL_DIR}. "
            "Ensure model files exist in the correct location."
        )


def _get_savedmodel_signature(saved_model):
    """Return the best concrete function for a TensorFlow SavedModel export."""
    if not hasattr(saved_model, "signatures") or not saved_model.signatures:
        raise ValueError("SavedModel has no callable signatures")

    if "serving_default" in saved_model.signatures:
        return saved_model.signatures["serving_default"]

    first_name = next(iter(saved_model.signatures))
    logger.warning(f"SavedModel missing 'serving_default'; using '{first_name}' signature")
    return saved_model.signatures[first_name]

# PREPROCESSING (EXACT SPECIFICATION)

def preprocess_video(video_path: str) -> np.ndarray:
    """
    Extract and preprocess frames with uniform sampling.
    
    Exact logic:
    1. Load video using OpenCV
    2. Get total frame count
    3. Validate minimum 16 frames
    4. Uniform sampling: step = total_frames // 16
    5. Extract frames at indices: i * step
    6. Resize to 224x224
    7. Normalize: frame / 255.0
    8. Stack to shape (1, 16, 224, 224, 3)
    9. Return as float32
    """
    start_time = time.time()
    logger.info(f"Starting video preprocessing: {video_path}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video file. Ensure it's a valid video format (mp4, avi, mov, etc.)")
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(f"Video info: {total_frames} frames")
    
    if total_frames < FRAMES_REQUIRED:
        cap.release()
        raise ValueError(
            f"Video has {total_frames} frames but requires minimum {FRAMES_REQUIRED}. "
            f"Ensure video is at least {FRAMES_REQUIRED * 0.033:.1f} seconds long (30fps)"
        )
    
    # Uniform sampling step
    step = total_frames // FRAMES_REQUIRED
    logger.info(f"Sampling strategy: Every {step}th frame from {total_frames} total")
    
    frames = []
    frame_indices = []
    
    for i in range(FRAMES_REQUIRED):
        frame_idx = i * step
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            cap.release()
            raise ValueError(f"Failed to extract frame at index {frame_idx}")
        
        # BGR → RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Resize to 224x224
        frame = cv2.resize(frame, (FRAME_SIZE, FRAME_SIZE))
        
        # Normalize: frame / 255.0
        frame = frame.astype(np.float32) / NORMALIZATION
        
        frames.append(frame)
        frame_indices.append(frame_idx)
    
    cap.release()
    
    # Stack: (16, 224, 224, 3) → (1, 16, 224, 224, 3)
    frames_array = np.array(frames, dtype=np.float32)
    frames_array = np.expand_dims(frames_array, axis=0)
    
    processing_time = time.time() - start_time
    logger.info(
        f"Preprocessing complete: shape={frames_array.shape}, "
        f"dtype={frames_array.dtype}, time={processing_time:.2f}s"
    )
    
    return frames_array

# MODEL INFERENCE

def predict_violence(frames: np.ndarray) -> dict:
    """
    Run inference on custom SavedModel using TensorFlow concrete function.
    """
    global model, model_type, model_signature
    
    if model is None:
        raise RuntimeError("Model not loaded. Check startup logs.")
    
    start_time = time.time()
    logger.info(f"Running inference with {model_type} model (input shape: {frames.shape})...")
    
    try:
        import tensorflow as tf
        
        logger.info("Executing model inference...")

        if model_type == "tflite":
            input_details = model.get_input_details()
            output_details = model.get_output_details()
            input_index = input_details[0]["index"]
            output_index = output_details[0]["index"]

            input_data = frames.astype(input_details[0]["dtype"])
            model.set_tensor(input_index, input_data)
            model.invoke()
            output = model.get_tensor(output_index)

        elif model_type == "savedmodel":
            if model_signature is None:
                model_signature = _get_savedmodel_signature(model)

            input_tensor = tf.constant(frames, dtype=tf.float32)
            _, signature_kwargs = model_signature.structured_input_signature
            if len(signature_kwargs) != 1:
                raise ValueError(
                    f"Expected one SavedModel input, got {list(signature_kwargs.keys())}"
                )

            input_name = next(iter(signature_kwargs))
            signature_output = model_signature(**{input_name: input_tensor})
            if not signature_output:
                raise ValueError("SavedModel returned no outputs")

            output_name = next(iter(signature_output))
            output = signature_output[output_name]

        else:
            input_tensor = tf.constant(frames, dtype=tf.float32)
            output = model(input_tensor, training=False)

        # Extract confidence
        output_array = output.numpy() if hasattr(output, 'numpy') else np.asarray(output)
        confidence = float(output_array.reshape(-1)[0])
        
        inference_time = time.time() - start_time
        
        # Apply threshold
        prediction = "VIOLENT" if confidence >= 0.5 else "NONVIOLENT"
        
        logger.info(
            f"Inference complete: prediction={prediction}, "
            f"confidence={confidence:.4f}, time={inference_time:.2f}s"
        )
        
        return {
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "inference_time_ms": round(inference_time * 1000, 2),
            "model_type": model_type
        }
    
    except Exception as e:
        logger.error(f"Inference error: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise RuntimeError(f"Model inference failed: {str(e)}")

# CLEANUP (Background Task)

def cleanup_temp_file(filepath: str):
    """Background cleanup of temporary files."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Cleaned up: {filepath}")
    except Exception as e:
        logger.warning(f"Cleanup failed for {filepath}: {e}")

# FASTAPI APPLICATION

app = FastAPI(
    title="Violence Detection API",
    description="Production-ready mobile-friendly backend for violence detection",
    version="2.0.0"
)

# CORS Configuration for Mobile App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure with actual mobile app domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# STARTUP & SHUTDOWN

@app.on_event("startup")
async def startup():
    """Load model on startup."""
    try:
        load_model_optimized()
        logger.info("🚀 API Ready for requests")
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("Shutting down...")
    temp_cleanup_executor.shutdown(wait=True)

# API ENDPOINTS

@app.post("/predict")
async def predict(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """
    Predict violence in uploaded video.
    
    - Input: Video file (mp4, avi, mov, mkv, flv, wmv)
    - Output: JSON with prediction, confidence, and timing
    - Optimized for mobile app performance
    """
    
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file type
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
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            temp_path = tmp.name
            content = await file.read()
            tmp.write(content)
        
        logger.info(f"Upload received: {file.filename} ({len(content)/1024/1024:.2f}MB)")
        
        # Preprocess video
        try:
            frames = preprocess_video(temp_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Run inference
        try:
            result = predict_violence(frames)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        
        # Calculate total time
        total_time = time.time() - request_start
        
        response = {
            "success": True,
            "prediction": result["prediction"],
            "confidence": result["confidence"],
            "inference_time_ms": result["inference_time_ms"],
            "total_time_ms": round(total_time * 1000, 2),
            "model_type": result["model_type"],
            "filename": file.filename
        }
        
        logger.info(f"✓ Request completed in {total_time:.2f}s: {response}")
        
        return JSONResponse(status_code=200, content=response)
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Processing error")
    
    finally:
        # Schedule cleanup
        if temp_path and background_tasks:
            background_tasks.add_task(cleanup_temp_file, temp_path)

@app.get("/health")
async def health_check():
    """Health check for mobile app."""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "model_type": model_type,
        "api_version": "2.0.0"
    }

@app.get("/stats")
async def get_stats():
    """Runtime statistics for monitoring clients."""
    return {
        "status": "ready" if model is not None else "not_loaded",
        "model_loaded": model is not None,
        "model_type": model_type,
        "api_version": "2.0.0",
        "frames_required": FRAMES_REQUIRED,
        "frame_size": FRAME_SIZE,
        "normalization": NORMALIZATION,
        "model_paths": {
            "tflite": str(TFLITE_MODEL_PATH),
            "keras": str(KERAS_MODEL_PATH),
            "h5": str(H5_MODEL_PATH),
            "savedmodel": str(MODEL_DIR)
        }
    }

@app.get("/")
async def root():
    """API information."""
    return {
        "service": "Violence Detection API",
        "version": "2.0.0",
        "status": "ready",
        "endpoints": {
            "predict": "POST /predict",
            "health": "GET /health",
            "stats": "GET /stats",
            "docs": "GET /docs"
        }
    }

# ENTRY POINT

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=4,  # Multiple workers for concurrent requests
        log_level="info"
    )
