"""
Report generation endpoints for Violence Detection App
"""

from datetime import datetime, timedelta, time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.database_models import Incident
from app.models import ReportResponse

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def calculate_statistics(incidents: List[Incident]) -> dict:
    """Calculate report statistics from a list of incidents."""
    total = len(incidents)
    if total == 0:
        return {
            "total_incidents": 0,
            "violent_incidents": 0,
            "non_violent_incidents": 0,
            "violent_percentage": 0.0,
            "average_confidence": 0.0,
            "accuracy_rate": 0.0,
        }

    violent = len([i for i in incidents if i.prediction == "VIOLENT"])
    non_violent = len([i for i in incidents if i.prediction == "NONVIOLENT"])
    confidence_scores = [float(i.confidence or 0.0) for i in incidents]
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    violent_percentage = (violent / total * 100) if total > 0 else 0.0
    high_confidence = len([i for i in incidents if float(i.confidence or 0.0) > 0.8])
    accuracy_rate = (high_confidence / total * 100) if total > 0 else 0.0

    return {
        "total_incidents": total,
        "violent_incidents": violent,
        "non_violent_incidents": non_violent,
        "violent_percentage": round(violent_percentage, 2),
        "average_confidence": round(avg_confidence, 3),
        "accuracy_rate": round(accuracy_rate, 2),
    }


def serialize_incident(incident: Incident) -> dict:
    return {
        "id": incident.id,
        "detection_type": incident.detection_type,
        "prediction": incident.prediction,
        "confidence": float(incident.confidence or 0.0),
        "location": incident.location_name,
        "emergency_response": bool(incident.is_marked_for_police),
        "timestamp": incident.created_at,
    }


def build_report_response(incidents: List[Incident]) -> ReportResponse:
    stats = calculate_statistics(incidents)
    incident_records = [serialize_incident(i) for i in incidents]
    return ReportResponse(**stats, incidents=incident_records)


@router.get("/daily", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_daily_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get today's incident report."""
    today = datetime.now().date()
    incidents = db.query(Incident).filter(
        Incident.user_id == current_user["id"],
        func.date(Incident.created_at) == today
    ).all()
    return build_report_response(incidents)


@router.get("/weekly", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_weekly_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get the last 7 days incident report."""
    week_ago = datetime.now() - timedelta(days=7)
    incidents = db.query(Incident).filter(
        Incident.user_id == current_user["id"],
        Incident.created_at >= week_ago
    ).all()
    return build_report_response(incidents)


@router.get("/monthly", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_monthly_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get the last 30 days incident report."""
    month_ago = datetime.now() - timedelta(days=30)
    incidents = db.query(Incident).filter(
        Incident.user_id == current_user["id"],
        Incident.created_at >= month_ago
    ).all()
    return build_report_response(incidents)


@router.get("/custom", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_custom_report(
    date_from: str,
    date_to: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get incident report for a custom date range."""
    try:
        start_date = datetime.strptime(date_from, "%Y-%m-%d")
        end_date = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )

    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to must be the same or after date_from"
        )

    start_date = datetime.combine(start_date.date(), time.min)
    end_date = datetime.combine(end_date.date(), time.max)

    incidents = db.query(Incident).filter(
        Incident.user_id == current_user["id"],
        Incident.created_at >= start_date,
        Incident.created_at <= end_date
    ).all()
    return build_report_response(incidents)
