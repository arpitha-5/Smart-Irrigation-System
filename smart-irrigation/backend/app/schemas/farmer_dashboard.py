"""Pydantic schema for farmer dashboard response.

All fields are optional where a value may not be calculable (e.g., no sensor data).
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

class WeatherSummary(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    rainfall: Optional[float] = None
    wind_speed: Optional[float] = None
    condition: Optional[str] = None
    source: Optional[str] = None
    is_mock: Optional[bool] = None
    timestamp: Optional[datetime] = None

class BaselineComparison(BaseModel):
    traditional_flood_liters: Optional[float] = None
    actual_liters: Optional[float] = None
    completed_schedule_volume_estimate_liters: Optional[float] = None
    water_saved_liters: Optional[float] = None
    water_saved_percent: Optional[float] = None
    is_estimated: bool = True
    baseline_description: str

class FieldWaterUsage(BaseModel):
    field_id: str
    field_name: str
    actual_liters: Optional[float] = None
    completed_schedule_volume_estimate_liters: Optional[float] = None
    planned_liters: float


class FieldCondition(BaseModel):
    field_id: str
    action: str
    urgency: str
    reason: str
    soil_moisture: Optional[float] = None
    sensor_timestamp: Optional[datetime] = None
    is_simulated: bool = False


class WaterAnalytics(BaseModel):
    daily_consumption_liters: Optional[float] = None
    weekly_consumption_liters: Optional[float] = None
    monthly_consumption_liters: Optional[float] = None
    daily_schedule_volume_estimate_liters: Optional[float] = None
    weekly_schedule_volume_estimate_liters: Optional[float] = None
    monthly_schedule_volume_estimate_liters: Optional[float] = None
    volume_basis: str = "unavailable"
    efficiency_score: Optional[float] = None
    field_breakdown: List[FieldWaterUsage] = []
    baseline_comparison: BaselineComparison

class AlertItem(BaseModel):
    id: str
    type: str  # low_moisture, excess_moisture, heavy_rainfall, sensor_offline, schedule_reminder, schedule_completed
    severity: str  # critical, warning, info
    title: str
    message: str
    field_id: Optional[str] = None
    field_name: Optional[str] = None
    recommended_action: str
    timestamp: datetime

class FarmerDashboardResponse(BaseModel):
    farmer_name: Optional[str] = None
    farmer_email: Optional[str] = None
    total_fields: int
    fields_needing_irrigation: int
    field_conditions: List[FieldCondition] = []
    average_soil_moisture: Optional[float] = None
    total_water_used_liters: Optional[float] = None
    completed_schedule_volume_estimate_liters: Optional[float] = None
    weather_summary: Optional[WeatherSummary] = None
    water_analytics: Optional[WaterAnalytics] = None
