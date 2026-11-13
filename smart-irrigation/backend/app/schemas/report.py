from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DailyReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: str
    avg_moisture: float
    avg_temperature: float
    total_rainfall_mm: float
    irrigation_water_used_liters: float
    alerts_triggered: int


class ReportsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_alerts: int
    open_alerts: int
    acknowledged_alerts: int
    resolved_alerts: int
    critical_alerts: int
    high_alerts: int

    total_fields: int
    high_risk_fields: int
    average_soil_moisture: Optional[float] = None
    water_usage_liters_today: float = 0.0
    estimated_water_saved_percent: float = 0.0
    forecast_24h_demand_mm: float = 0.0

    system_health_status: str = Field(
        default="OPTIMAL",
        description="Current health: OPTIMAL, ATTENTION_REQUIRED, or CRITICAL"
    )
    generated_at: datetime
