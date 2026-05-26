from datetime import datetime, timedelta, time
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database_models import Incident


def get_incidents_for_today(db: Session, user_id: int) -> List[Incident]:
    today = datetime.now().date()
    return db.query(Incident).filter(
        Incident.user_id == user_id,
        func.date(Incident.created_at) == today
    ).all()


def get_incidents_for_week(db: Session, user_id: int) -> List[Incident]:
    week_ago = datetime.now() - timedelta(days=7)
    return db.query(Incident).filter(
        Incident.user_id == user_id,
        Incident.created_at >= week_ago
    ).all()


def get_incidents_for_month(db: Session, user_id: int) -> List[Incident]:
    month_ago = datetime.now() - timedelta(days=30)
    return db.query(Incident).filter(
        Incident.user_id == user_id,
        Incident.created_at >= month_ago
    ).all()


def get_incidents_for_date_range(
    db: Session,
    user_id: int,
    date_from: datetime,
    date_to: datetime
) -> List[Incident]:
    start_date = datetime.combine(date_from.date(), time.min)
    end_date = datetime.combine(date_to.date(), time.max)
    return db.query(Incident).filter(
        Incident.user_id == user_id,
        Incident.created_at >= start_date,
        Incident.created_at <= end_date
    ).all()


def calculate_report_statistics(incidents: List[Incident]) -> dict:
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
    avg_confidence = sum(confidence_scores) / total if total > 0 else 0.0
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
