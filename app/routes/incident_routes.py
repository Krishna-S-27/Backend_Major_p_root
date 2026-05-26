"""
Incident management routes
Handle incident creation, retrieval, and management
"""

import logging
import os
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.auth import get_current_user
from app.database_models import Incident, User, UserProfile, Notification
from app.models import IncidentCreateRequest, IncidentResponse
from app.notifications import NotificationManager

logger = logging.getLogger(__name__)

# Use different prefix to avoid conflicts
router = APIRouter(tags=["Incidents"])

notification_manager = NotificationManager("firebase_credentials.json")

# ===================== CREATE INCIDENT =====================

@router.post("/api/v1/incidents/create", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_incident(
    request: IncidentCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new incident from prediction result
    
    - Saves incident to database
    - If violent, marks the incident as local-only
    - Sends notifications
    
    @param request: Incident creation request
    @param background_tasks: Background task handler
    @param current_user: Authenticated user
    @param db: Database session
    @return: Created incident details
    """
    
    try:
        logger.info(f"Creating incident for user {current_user['id']}: {request.prediction}")
        
        # Create incident record
        incident = Incident(
            user_id=current_user["id"],
            detection_type=request.detection_type.value,
            prediction=request.prediction,
            confidence=request.confidence,
            video_file_name=request.video_file_name,
            video_file_path=request.video_file_path,
            video_duration_seconds=request.video_duration_seconds,
            frame_count=request.frame_count,
            preprocessing_time_ms=request.preprocessing_time_ms,
            inference_time_ms=request.inference_time_ms,
            total_time_ms=request.total_time_ms,
            latitude=request.latitude,
            longitude=request.longitude,
            location_name=request.location_name,
            upload_status="PENDING"
        )
        
        db.add(incident)
        db.flush()  # Get incident ID
        
        incident_id = incident.id
        
        # Update user profile statistics
        user_profile = db.query(UserProfile).filter(
            UserProfile.user_id == current_user["id"]
        ).first()
        
        if user_profile:
            user_profile.total_incidents += 1
            if request.prediction == "VIOLENT":
                user_profile.total_videos_saved += 1
        
        db.commit()
        
        logger.info(f"✓ Incident created: ID={incident_id}, Prediction={request.prediction}")
        
        # If violent, this incident will be stored locally on the device.
        if request.prediction == "VIOLENT" and request.video_file_path:
            incident.upload_status = "LOCAL"
            db.commit()
            logger.info(f"Violent incident stored locally: {incident_id}")
        
        return {
            "success": True,
            "incident_id": incident_id,
            "message": "Incident created successfully",
            "prediction": request.prediction,
            "confidence": request.confidence
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating incident: {e}")
        raise HTTPException(status_code=500, detail="Error creating incident")


# ===================== GET STATISTICS =====================

@router.get("/api/v1/incidents/user/statistics", status_code=status.HTTP_200_OK)
async def get_incident_statistics(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get incident statistics for user
    
    @param current_user: Authenticated user
    @param db: Database session
    @return: Statistics
    """
    
    try:
        total = db.query(Incident).filter(
            Incident.user_id == current_user["id"]
        ).count()
        
        violent = db.query(Incident).filter(
            (Incident.user_id == current_user["id"]) &
            (Incident.prediction == "VIOLENT")
        ).count()
        
        non_violent = total - violent
        
        # Calculate average confidence
        from sqlalchemy import func
        avg_conf = db.query(func.avg(Incident.confidence)).filter(
            Incident.user_id == current_user["id"]
        ).scalar() or 0
        
        logger.info(f"Retrieved statistics for user {current_user['id']}")
        
        return {
            "total_incidents": total,
            "violent_incidents": violent,
            "non_violent_incidents": non_violent,
            "detection_rate": round((violent / total * 100), 2) if total > 0 else 0,
            "average_confidence": round(float(avg_conf), 4)
        }
        
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching statistics")

# ===================== LIST INCIDENTS =====================

@router.get("/api/v1/incidents/list", status_code=status.HTTP_200_OK)
async def list_incidents(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
    prediction: Optional[str] = None
):
    """
    List user's incidents with pagination
    
    @param current_user: Authenticated user
    @param db: Database session
    @param skip: Records to skip
    @param limit: Records per page
    @param prediction: Filter by prediction (VIOLENT/NONVIOLENT)
    @return: List of incidents
    """
    
    try:
        query = db.query(Incident).filter(
            Incident.user_id == current_user["id"]
        )
        
        if prediction:
            query = query.filter(Incident.prediction == prediction)
        
        total = query.count()
        incidents = query.order_by(
            Incident.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        logger.info(f"Listed {len(incidents)} incidents for user {current_user['id']}")
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "incidents": [
                {
                    "id": i.id,
                    "detection_type": i.detection_type,
                    "prediction": i.prediction,
                    "confidence": float(i.confidence),
                    "video_name": i.video_file_name,
                    "upload_status": i.upload_status,
                    "google_drive_link": i.video_google_drive_link,
                    "created_at": i.created_at.isoformat(),
                    "inference_time_ms": i.inference_time_ms,
                    "total_time_ms": i.total_time_ms
                }
                for i in incidents
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing incidents: {e}")
        raise HTTPException(status_code=500, detail="Error listing incidents")

# ===================== GET INCIDENT DETAILS =====================

@router.get("/api/v1/incidents/{incident_id}", status_code=status.HTTP_200_OK)
async def get_incident_details(
    incident_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific incident
    
    @param incident_id: Incident ID
    @param current_user: Authenticated user
    @param db: Database session
    @return: Detailed incident information
    """
    
    try:
        incident = db.query(Incident).filter(
            (Incident.id == incident_id) & 
            (Incident.user_id == current_user["id"])
        ).first()
        
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        
        logger.info(f"Retrieved incident details: {incident_id}")
        
        return {
            "id": incident.id,
            "detection_type": incident.detection_type,
            "prediction": incident.prediction,
            "confidence": float(incident.confidence),
            "video_name": incident.video_file_name,
            "video_path": incident.video_file_path,
            "video_url": None,
            "upload_status": incident.upload_status,
            "is_uploaded": incident.is_uploaded_to_drive,
            "frame_count": incident.frame_count,
            "duration_seconds": incident.video_duration_seconds,
            "preprocessing_time_ms": incident.preprocessing_time_ms,
            "inference_time_ms": incident.inference_time_ms,
            "total_time_ms": incident.total_time_ms,
            "latitude": incident.latitude,
            "longitude": incident.longitude,
            "location_name": incident.location_name,
            "is_reviewed": incident.is_reviewed_by_admin,
            "is_marked_police": incident.is_marked_for_police,
            "police_reference": incident.police_reference_number,
            "created_at": incident.created_at.isoformat(),
            "updated_at": incident.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting incident details: {e}")
        raise HTTPException(status_code=500, detail="Error fetching incident")

# ===================== DELETE INCIDENT =====================

@router.delete("/api/v1/incidents/{incident_id}", status_code=status.HTTP_200_OK)
async def delete_incident(
    incident_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an incident
    
    @param incident_id: Incident ID
    @param current_user: Authenticated user
    @param db: Database session
    @return: Success message
    """
    
    try:
        incident = db.query(Incident).filter(
            (Incident.id == incident_id) & 
            (Incident.user_id == current_user["id"])
        ).first()
        
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        
        # Delete incident record from database
        db.delete(incident)
        db.commit()
        
        logger.info(f"✓ Incident deleted: {incident_id}")
        
        return {"message": "Incident deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting incident: {e}")
        raise HTTPException(status_code=500, detail="Error deleting incident")
