"""
Admin routes for dashboard and management
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.auth import get_current_admin_user
from app.database_models import User, Incident

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

@router.get("/dashboard")
async def get_dashboard(
    current_user: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get admin dashboard statistics
    
    @param current_user: Current admin user
    @param db: Database session
    @return: Dashboard statistics
    """
    
    try:
        total_users = db.query(User).count()
        total_incidents = db.query(Incident).count()
        violent_incidents = db.query(Incident).filter(
            Incident.prediction == "VIOLENT"
        ).count()
        pending_uploads = db.query(Incident).filter(
            Incident.upload_status == "PENDING"
        ).count()
        pending_reviews = db.query(Incident).filter(
            Incident.is_reviewed_by_admin == False
        ).count()
        
        avg_confidence = db.query(func.avg(Incident.confidence)).scalar() or 0
        
        logger.info(f"Admin {current_user['id']} accessed dashboard")
        
        return {
            "total_users": total_users,
            "total_incidents": total_incidents,
            "violent_incidents": violent_incidents,
            "non_violent_incidents": total_incidents - violent_incidents,
            "pending_uploads": pending_uploads,
            "pending_reviews": pending_reviews,
            "average_confidence": round(float(avg_confidence), 4)
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error fetching dashboard")

@router.get("/users")
async def get_all_users(
    current_user: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20
):
    """
    Get all users
    
    @param current_user: Current admin user
    @param db: Database session
    @param skip: Records to skip
    @param limit: Records to return
    @return: List of users
    """
    
    try:
        users = db.query(User).offset(skip).limit(limit).all()
        total = db.query(User).count()
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "phone": u.phone,
                    "emergency_phone": u.emergency_phone,
                    "emergency_email": u.emergency_email,
                    "drive_folder_id": u.drive_folder_id,
                    "role": u.role,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat()
                }
                for u in users
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Error fetching users")

@router.post("/incidents/{incident_id}/review")
async def review_incident(
    incident_id: int,
    admin_notes: str,
    current_user: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Review and mark incident as reviewed
    
    @param incident_id: Incident ID
    @param admin_notes: Admin review notes
    @param current_user: Current admin user
    @param db: Database session
    @return: Success message
    """
    
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        incident.is_reviewed_by_admin = True
        incident.admin_id = current_user["id"]
        incident.admin_notes = admin_notes
        
        db.commit()
        
        logger.info(f"Admin {current_user['id']} reviewed incident {incident_id}")
        
        return {"message": "Incident reviewed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error reviewing incident: {e}")
        raise HTTPException(status_code=500, detail="Error reviewing incident")

@router.post("/incidents/{incident_id}/mark-police")
async def mark_for_police(
    incident_id: int,
    police_reference: str,
    current_user: dict = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Mark incident for police report
    
    @param incident_id: Incident ID
    @param police_reference: Police reference number
    @param current_user: Current admin user
    @param db: Database session
    @return: Success message
    """
    
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        incident.is_marked_for_police = True
        incident.police_reference_number = police_reference
        
        db.commit()
        
        logger.info(f"Incident {incident_id} marked for police")
        
        return {"message": "Incident marked for police"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error marking for police: {e}")
        raise HTTPException(status_code=500, detail="Error marking incident")
