"""
Prediction endpoints for video analysis
"""

import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path
import tempfile
import time
import numpy as np

from app.database import get_db
from app.auth import get_current_user
from app.database_models import Incident
from app.models import IncidentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Predictions"])

# Import from main.py (will need to refactor later)
# For now, these will be called from main.py

@router.get("/incidents")
async def get_user_incidents(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20
):
    """
    Get user's incidents
    
    @param current_user: Current authenticated user
    @param db: Database session
    @param skip: Number of records to skip
    @param limit: Number of records to return
    @return: List of incidents
    """
    
    try:
        incidents = db.query(Incident).filter(
            Incident.user_id == current_user["id"]
        ).order_by(Incident.created_at.desc()).offset(skip).limit(limit).all()
        
        total = db.query(Incident).filter(
            Incident.user_id == current_user["id"]
        ).count()
        
        logger.info(f"Retrieved {len(incidents)} incidents for user {current_user['id']}")
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "incidents": [
                {
                    "id": i.id,
                    "detection_type": i.detection_type,
                    "prediction": i.prediction,
                    "confidence": i.confidence,
                    "created_at": i.created_at.isoformat(),
                    "video_name": i.video_file_name,
                    "upload_status": i.upload_status
                }
                for i in incidents
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching incidents: {e}")
        raise HTTPException(status_code=500, detail="Error fetching incidents")

@router.get("/incidents/{incident_id}")
async def get_incident_details(
    incident_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get incident details
    
    @param incident_id: Incident ID
    @param current_user: Current user
    @param db: Database session
    @return: Incident details
    """
    
    try:
        incident = db.query(Incident).filter(
            (Incident.id == incident_id) & (Incident.user_id == current_user["id"])
        ).first()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        logger.info(f"Retrieved incident {incident_id}")
        
        return {
            "id": incident.id,
            "detection_type": incident.detection_type,
            "prediction": incident.prediction,
            "confidence": incident.confidence,
            "video_name": incident.video_file_name,
            "video_url": incident.video_google_drive_link,
            "upload_status": incident.upload_status,
            "inference_time_ms": incident.inference_time_ms,
            "total_time_ms": incident.total_time_ms,
            "latitude": incident.latitude,
            "longitude": incident.longitude,
            "location_name": incident.location_name,
            "created_at": incident.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching incident: {e}")
        raise HTTPException(status_code=500, detail="Error fetching incident")

@router.delete("/incidents/{incident_id}")
async def delete_incident(
    incident_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete incident
    
    @param incident_id: Incident ID
    @param current_user: Current user
    @param db: Database session
    @return: Success message
    """
    
    try:
        incident = db.query(Incident).filter(
            (Incident.id == incident_id) & (Incident.user_id == current_user["id"])
        ).first()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        db.delete(incident)
        db.commit()
        
        logger.info(f"Deleted incident {incident_id}")
        
        return {"message": "Incident deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting incident: {e}")
        raise HTTPException(status_code=500, detail="Error deleting incident")

@router.get("/statistics")
async def get_user_statistics(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user statistics
    
    @param current_user: Current user
    @param db: Database session
    @return: User statistics
    """
    
    try:
        total_incidents = db.query(Incident).filter(
            Incident.user_id == current_user["id"]
        ).count()
        
        violent_incidents = db.query(Incident).filter(
            (Incident.user_id == current_user["id"]) & 
            (Incident.prediction == "VIOLENT")
        ).count()
        
        avg_confidence = db.query(Incident).filter(
            Incident.user_id == current_user["id"]
        ).count()
        
        logger.info(f"Retrieved statistics for user {current_user['id']}")
        
        return {
            "total_incidents": total_incidents,
            "violent_incidents": violent_incidents,
            "non_violent_incidents": total_incidents - violent_incidents,
            "detection_rate": (violent_incidents / total_incidents * 100) if total_incidents > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching statistics")