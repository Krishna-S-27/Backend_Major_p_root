from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class IncidentInReport(BaseModel):
    id: int
    prediction: str
    confidence: float
    detection_type: str
    location: Optional[str]
    emergency_response: bool
    created_at: datetime

    class Config:
        orm_mode = True


class ReportResponse(BaseModel):
    total_incidents: int
    violent_incidents: int
    non_violent_incidents: int
    violent_percentage: float
    average_confidence: float
    accuracy_rate: float
    incidents: List[IncidentInReport]
