"""
Video processing and handling utilities
"""

import os
import cv2
import numpy as np
from pathlib import Path
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class VideoHandler:
    """Handles video file operations"""
    
    FRAME_SIZE = 224
    FRAMES_REQUIRED = 16
    NORMALIZATION = 255.0
    ALLOWED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.3gp'}
    MAX_FILE_SIZE_MB = 500
    
    @staticmethod
    def validate_video_file(file_path: str) -> Tuple[bool, str]:
        """
        Validate video file
        
        @param file_path: Path to video file
        @return: (is_valid, error_message)
        """
        
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        # Check file extension
        ext = Path(file_path).suffix.lower()
        if ext not in VideoHandler.ALLOWED_FORMATS:
            return False, f"Invalid format. Allowed: {', '.join(VideoHandler.ALLOWED_FORMATS)}"
        
        # Check file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > VideoHandler.MAX_FILE_SIZE_MB:
            return False, f"File too large: {file_size_mb:.1f}MB (max: {VideoHandler.MAX_FILE_SIZE_MB}MB)"
        
        # Check if video is readable
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return False, "Cannot open video file"
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        
        if total_frames < VideoHandler.FRAMES_REQUIRED:
            return False, f"Video too short: {total_frames} frames (min: {VideoHandler.FRAMES_REQUIRED})"
        
        return True, ""
    
    @staticmethod
    def get_video_info(file_path: str) -> dict:
        """
        Get video information
        
        @param file_path: Path to video file
        @return: Dictionary with video info
        """
        
        cap = cv2.VideoCapture(file_path)
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        duration_seconds = total_frames / fps if fps > 0 else 0
        file_size_bytes = os.path.getsize(file_path)
        
        cap.release()
        
        return {
            "total_frames": total_frames,
            "fps": fps,
            "width": width,
            "height": height,
            "duration_seconds": duration_seconds,
            "file_size_bytes": file_size_bytes
        }
    
    @staticmethod
    def cleanup_file(file_path: str) -> bool:
        """
        Delete file
        
        @param file_path: Path to file
        @return: True if successful
        """
        
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"✓ File deleted: {file_path}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to delete {file_path}: {e}")
            return False