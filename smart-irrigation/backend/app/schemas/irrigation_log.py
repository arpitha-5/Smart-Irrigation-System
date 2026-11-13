from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.farmer import ID_PATTERN


class IrrigationLogCreate(BaseModel):
    field_id: str = Field(pattern=ID_PATTERN)
    timestamp: Optional[datetime] = None
    water_depth_mm: float = Field(..., gt=0)
    water_volume_litres: Optional[float] = Field(None, gt=0)
    duration_minutes: Optional[float] = Field(None, gt=0)
    flow_rate_lpm: Optional[float] = Field(None, gt=0)
    source: str = Field("farmer_manual", max_length=40)
    notes: Optional[str] = None


class IrrigationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: str
    field_id: str
    timestamp: datetime
    water_depth_mm: float
    water_volume_litres: float
    duration_minutes: Optional[float] = None
    flow_rate_lpm: Optional[float] = None
    source: str
    notes: Optional[str] = None
    is_demo: bool = False
    created_at: datetime
