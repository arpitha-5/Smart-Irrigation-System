"""Explainable farm intelligence endpoints built from stored telemetry."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Field as FieldModel, IrrigationSchedule, SensorReading
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

MOISTURE_RANGES = {
    "rice": (45.0, 65.0),
    "maize": (25.0, 42.0),
    "corn": (25.0, 42.0),
    "wheat": (28.0, 45.0),
    "tomato": (35.0, 50.0),
}
DEFAULT_MOISTURE_RANGE = (30.0, 55.0)
CROP_DAILY_MM = {
    "rice": 6.0,
    "maize": 4.0,
    "corn": 4.0,
    "wheat": 3.5,
    "tomato": 4.5,
}


class ReadingSnapshot(BaseModel):
    timestamp: datetime
    soil_moisture: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    rainfall: Optional[float] = None
    is_simulated: bool = False


class DigitalTwinField(BaseModel):
    field_id: str
    name: str
    crop_type: str
    area_hectares: Optional[float] = None
    health: str
    health_reason: str
    latest_reading: Optional[ReadingSnapshot] = None
    moisture_change: Optional[float] = None
    irrigation_status: str
    pending_water_liters: float = 0.0


class DigitalTwinResponse(BaseModel):
    generated_at: datetime
    live_fields: int
    fields_without_telemetry: int
    fields: list[DigitalTwinField]


class CropStressField(BaseModel):
    field_id: str
    field_name: str
    risk_score: float
    risk_level: str
    data_available: bool
    reasons: list[str]
    recommended_actions: list[str]
    latest_reading: Optional[ReadingSnapshot] = None


class CropStressResponse(BaseModel):
    generated_at: datetime
    fields: list[CropStressField]


class WaterBudgetRequest(BaseModel):
    available_water_liters: float = Field(..., gt=0, le=1_000_000_000)
    horizon_days: int = Field(7, ge=1, le=30)


class WaterAllocation(BaseModel):
    field_id: str
    field_name: str
    priority: str
    moisture_percent: Optional[float] = None
    estimated_demand_liters: float
    allocated_liters: float
    shortage_liters: float
    reason: str


class WaterBudgetResponse(BaseModel):
    generated_at: datetime
    available_water_liters: float
    estimated_demand_liters: float
    allocated_water_liters: float
    remaining_water_liters: float
    shortage_liters: float
    savings_vs_full_demand_percent: float
    assumptions: list[str]
    allocations: list[WaterAllocation]


def _farmer_fields(db: Session, user_id: int) -> list[FieldModel]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.models.farmer import Farmer

    farmer = db.query(Farmer).filter(Farmer.email == user.email).first()
    if not farmer:
        return []
    return db.query(FieldModel).filter(FieldModel.farmer_id == farmer.farmer_id).order_by(FieldModel.name).all()


def _latest_readings(db: Session, field_id: str, limit: int = 12) -> list[SensorReading]:
    return (
        db.query(SensorReading)
        .filter(SensorReading.field_id == field_id)
        .order_by(SensorReading.timestamp.desc())
        .limit(limit)
        .all()
    )


def _reading_snapshot(reading: Optional[SensorReading]) -> Optional[ReadingSnapshot]:
    return ReadingSnapshot.model_validate(reading, from_attributes=True) if reading else None


def _moisture_range(crop_type: str) -> tuple[float, float]:
    crop = crop_type.lower()
    for name, value in MOISTURE_RANGES.items():
        if name in crop:
            return value
    return DEFAULT_MOISTURE_RANGE


def _health(crop_type: str, moisture: Optional[float]) -> tuple[str, str]:
    if moisture is None:
        return "unknown", "No stored soil-moisture telemetry is available."
    minimum, maximum = _moisture_range(crop_type)
    if moisture < minimum - 6:
        return "critical", f"Soil moisture is {moisture:.1f}%, below the {minimum:.0f}% crop threshold."
    if moisture < minimum:
        return "moderate", f"Soil moisture is {moisture:.1f}%, below the {minimum:.0f}% optimal threshold."
    if moisture > maximum + 8:
        return "moderate", f"Soil moisture is {moisture:.1f}%, above the {maximum:.0f}% upper threshold."
    return "healthy", f"Soil moisture is within the {minimum:.0f}-{maximum:.0f}% crop range."


def _pending_schedule(db: Session, field_id: str) -> tuple[str, float]:
    schedules = (
        db.query(IrrigationSchedule)
        .filter(
            IrrigationSchedule.field_id == field_id,
            IrrigationSchedule.status == "pending",
        )
        .all()
    )
    if not schedules:
        return "not_scheduled", 0.0
    return "scheduled", sum(item.water_quantity_liters for item in schedules)


@router.get("/digital-twin", response_model=DigitalTwinResponse)
def digital_twin(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
) -> DigitalTwinResponse:
    fields = _farmer_fields(db, user_id)
    output: list[DigitalTwinField] = []
    for field in fields:
        readings = _latest_readings(db, field.field_id)
        latest = readings[0] if readings else None
        previous = readings[1] if len(readings) > 1 else None
        health, reason = _health(field.crop_type, latest.soil_moisture if latest else None)
        schedule_status, pending_liters = _pending_schedule(db, field.field_id)
        output.append(
            DigitalTwinField(
                field_id=field.field_id,
                name=field.name,
                crop_type=field.crop_type,
                area_hectares=field.area_hectares,
                health=health,
                health_reason=reason,
                latest_reading=_reading_snapshot(latest),
                moisture_change=(
                    round(latest.soil_moisture - previous.soil_moisture, 2)
                    if latest and previous and latest.soil_moisture is not None and previous.soil_moisture is not None
                    else None
                ),
                irrigation_status=schedule_status,
                pending_water_liters=round(pending_liters, 1),
            )
        )
    return DigitalTwinResponse(
        generated_at=datetime.utcnow(),
        live_fields=sum(item.latest_reading is not None for item in output),
        fields_without_telemetry=sum(item.latest_reading is None for item in output),
        fields=output,
    )


@router.get("/crop-stress", response_model=CropStressResponse)
def crop_stress(
    field_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
) -> CropStressResponse:
    fields = _farmer_fields(db, user_id)
    if field_id:
        fields = [field for field in fields if field.field_id == field_id]
    results: list[CropStressField] = []
    for field in fields:
        readings = _latest_readings(db, field.field_id)
        latest = readings[0] if readings else None
        reasons: list[str] = []
        actions: list[str] = []
        score = 0.0
        minimum, _ = _moisture_range(field.crop_type)
        if latest is None or latest.soil_moisture is None:
            reasons.append("Telemetry is unavailable, so stress cannot be assessed reliably.")
            actions.append("Check the field sensor connection before making an irrigation decision.")
            results.append(CropStressField(
                field_id=field.field_id, field_name=field.name, risk_score=0, risk_level="Low",
                data_available=False, reasons=reasons, recommended_actions=actions,
            ))
            continue
        moisture = latest.soil_moisture
        if moisture < minimum:
            deficit = minimum - moisture
            score += min(60.0, deficit * 4)
            reasons.append(f"Soil moisture is {moisture:.1f}%, {deficit:.1f} points below the crop threshold.")
            actions.append("Review the irrigation recommendation and inspect the sensor location.")
        if len(readings) >= 2 and readings[1].soil_moisture is not None and moisture < readings[1].soil_moisture:
            score += min(20.0, (readings[1].soil_moisture - moisture) * 2)
            reasons.append("The latest moisture reading is trending downward.")
        if latest.temperature is not None and latest.temperature >= 35:
            score += 10
            reasons.append(f"Temperature is elevated at {latest.temperature:.1f}°C.")
            actions.append("Check crop canopy and soil moisture again during the next monitoring interval.")
        if latest.humidity is not None and latest.humidity < 30:
            score += 10
            reasons.append(f"Relative humidity is low at {latest.humidity:.1f}%.")
        if latest.rainfall and latest.rainfall > 0:
            score = max(0, score - min(15, latest.rainfall))
            reasons.append(f"Recent rainfall ({latest.rainfall:.1f} mm) reduces immediate water-stress confidence.")
        score = round(min(100.0, score), 1)
        level = "Critical" if score >= 75 else "High" if score >= 50 else "Moderate" if score >= 25 else "Low"
        if not reasons:
            reasons.append("Recent telemetry does not show a strong crop-stress signal.")
        if not actions:
            actions.append("Continue monitoring and compare the next readings with this baseline.")
        results.append(CropStressField(
            field_id=field.field_id, field_name=field.name, risk_score=score, risk_level=level,
            data_available=True, reasons=reasons, recommended_actions=actions,
            latest_reading=_reading_snapshot(latest),
        ))
    return CropStressResponse(generated_at=datetime.utcnow(), fields=results)


@router.post("/water-budget", response_model=WaterBudgetResponse)
def water_budget(
    payload: WaterBudgetRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
) -> WaterBudgetResponse:
    fields = _farmer_fields(db, user_id)
    allocations: list[WaterAllocation] = []
    for field in fields:
        readings = _latest_readings(db, field.field_id, limit=1)
        latest = readings[0] if readings else None
        area = field.area_hectares or 0
        crop = field.crop_type.lower()
        daily_mm = next((value for name, value in CROP_DAILY_MM.items() if name in crop), 4.0)
        demand = area * 10_000 * daily_mm * payload.horizon_days
        moisture = latest.soil_moisture if latest else None
        minimum, _ = _moisture_range(field.crop_type)
        priority = "critical" if moisture is not None and moisture < minimum - 6 else "high" if moisture is not None and moisture < minimum else "normal"
        multiplier = 1.15 if priority == "critical" else 1.05 if priority == "high" else 1.0
        demand *= multiplier
        allocations.append(WaterAllocation(
            field_id=field.field_id, field_name=field.name, priority=priority,
            moisture_percent=moisture, estimated_demand_liters=round(demand, 1),
            allocated_liters=0, shortage_liters=0,
            reason="Priority is based on the latest stored soil moisture; missing telemetry is not treated as dry.",
        ))
    allocations.sort(key=lambda item: {"critical": 0, "high": 1, "normal": 2}[item.priority])
    remaining = payload.available_water_liters
    for item in allocations:
        item.allocated_liters = round(min(remaining, item.estimated_demand_liters), 1)
        item.shortage_liters = round(max(0, item.estimated_demand_liters - item.allocated_liters), 1)
        remaining -= item.allocated_liters
    demand = round(sum(item.estimated_demand_liters for item in allocations), 1)
    allocated = round(sum(item.allocated_liters for item in allocations), 1)
    return WaterBudgetResponse(
        generated_at=datetime.utcnow(),
        available_water_liters=payload.available_water_liters,
        estimated_demand_liters=demand,
        allocated_water_liters=allocated,
        remaining_water_liters=round(max(0, remaining), 1),
        shortage_liters=round(max(0, demand - allocated), 1),
        savings_vs_full_demand_percent=round(max(0, (1 - allocated / demand) * 100) if demand else 0, 1),
        assumptions=[
            "Demand uses crop-specific daily water depth multiplied by area (1 hectare = 10,000 m²).",
            "The horizon is a planning estimate, not a sensor measurement or guaranteed crop requirement.",
            "Critical and high moisture deficits receive a 15% and 5% planning uplift respectively.",
        ],
        allocations=allocations,
    )
