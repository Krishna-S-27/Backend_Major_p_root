from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.repository.incident_repository import (
    calculate_report_statistics,
    get_incidents_for_date_range,
    get_incidents_for_month,
    get_incidents_for_today,
    get_incidents_for_week,
)
from app.schemas.report import IncidentInReport, ReportResponse

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def build_incident_report_item(incident) -> IncidentInReport:
    return IncidentInReport(
        id=incident.id,
        prediction=incident.prediction,
        confidence=float(incident.confidence or 0.0),
        detection_type=incident.detection_type,
        location=getattr(incident, "location_name", None) or getattr(incident, "location", None),
        emergency_response=bool(getattr(incident, "is_marked_for_police", False) or getattr(incident, "emergency_response", False)),
        created_at=incident.created_at,
    )


def build_report_response(incidents, user_id: int) -> ReportResponse:
    stats = calculate_report_statistics(incidents)
    incident_items = [build_incident_report_item(i) for i in incidents]
    return ReportResponse(**stats, incidents=incident_items)


@router.get("/daily", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_daily_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    incidents = get_incidents_for_today(db, current_user["id"])
    return build_report_response(incidents, current_user["id"])


@router.get("/weekly", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_weekly_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    incidents = get_incidents_for_week(db, current_user["id"])
    return build_report_response(incidents, current_user["id"])


@router.get("/monthly", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_monthly_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    incidents = get_incidents_for_month(db, current_user["id"])
    return build_report_response(incidents, current_user["id"])


@router.get("/custom", response_model=ReportResponse, status_code=status.HTTP_200_OK)
def get_custom_report(
    date_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    date_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
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

    incidents = get_incidents_for_date_range(db, current_user["id"], start_date, end_date)
    return build_report_response(incidents, current_user["id"])
