from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: int
    field_id: str
    sensor_id: str
    alert_type: str
    severity: str
    status: str
    source: str = "rule"
    message: str
    recommended_action: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    occurrence_count: int = 1
    created_at: datetime
    last_seen_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime] = None


class AlertStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(acknowledged|resolved|open)$")


class NotificationTestRequest(BaseModel):
    channel: str = Field(default="WHATSAPP", description="SMS, WHATSAPP, EMAIL, or WEB_PUSH")
    recipient: str = Field(..., description="Phone number or email address (e.g., +918074599664)")
    title: Optional[str] = "AgriPulse Crop Advisory"
    message: str = "AgriPulse Alert: Soil moisture dropped to 21% in North Plot. Drip irrigation scheduled."
