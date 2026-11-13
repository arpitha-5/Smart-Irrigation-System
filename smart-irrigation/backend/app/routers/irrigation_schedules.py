"""Irrigation schedule management endpoints."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.errors import AppError
from app.models import Field, IrrigationSchedule
from app.models.irrigation_schedule import ScheduleStatus as ModelScheduleStatus
from app.schemas.irrigation_schedule import (
    IrrigationScheduleCreate,
    IrrigationScheduleOut,
    IrrigationScheduleStatusUpdate,
    IrrigationScheduleUpdate,
    ScheduleStatus,
)
from app.services.irrigation_service import recommend_irrigation

router = APIRouter(prefix="/irrigation/schedules", tags=["irrigation_schedules"])

_TERMINAL_STATUSES = {
    ScheduleStatus.completed,
    ScheduleStatus.skipped,
    ScheduleStatus.cancelled,
}


def _reject_terminal_status_change(schedule: IrrigationSchedule, new_status: ScheduleStatus) -> None:
    current_status = ScheduleStatus(schedule.status)
    if current_status in _TERMINAL_STATUSES and new_status != current_status:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "schedule_status_terminal",
            f"Schedule '{schedule.schedule_id}' is {current_status.value} and cannot be changed to {new_status.value}.",
        )


def _is_recent_generated_duplicate(
    db: Session,
    field_id: str,
    reason: str,
    duration_minutes: float,
    water_quantity_liters: float,
    now: datetime,
) -> bool:
    recent_cutoff = now - timedelta(minutes=15)
    existing = db.scalars(
        select(IrrigationSchedule).where(
            IrrigationSchedule.field_id == field_id,
            IrrigationSchedule.status.in_([ModelScheduleStatus.pending, ModelScheduleStatus.completed]),
            IrrigationSchedule.created_at >= recent_cutoff,
        )
    )
    normalized_reason = reason.strip().casefold()
    return any(
        (schedule.reason or "").strip().casefold() == normalized_reason
        and schedule.duration_minutes == duration_minutes
        and schedule.water_quantity_liters == water_quantity_liters
        for schedule in existing
    )


@router.get("", response_model=List[IrrigationScheduleOut])
def list_schedules(
    field_id: Optional[str] = None,
    status_filter: Optional[ScheduleStatus] = Query(None, alias="status"),
    start_date: Optional[datetime] = Query(None, description="Start filter for recommended_date"),
    end_date: Optional[datetime] = Query(None, description="End filter for recommended_date"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retrieve irrigation schedules with optional field, status, or date range filtering."""
    stmt = select(IrrigationSchedule)
    if field_id:
        stmt = stmt.where(IrrigationSchedule.field_id == field_id)
    if status_filter:
        stmt = stmt.where(IrrigationSchedule.status == status_filter)
    if start_date:
        stmt = stmt.where(IrrigationSchedule.recommended_date >= start_date)
    if end_date:
        stmt = stmt.where(IrrigationSchedule.recommended_date <= end_date)
    stmt = stmt.order_by(desc(IrrigationSchedule.recommended_date), desc(IrrigationSchedule.created_at)).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=IrrigationScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: IrrigationScheduleCreate, db: Session = Depends(get_db)):
    """Manually or rule-based create an irrigation schedule."""
    # Ensure field exists
    field = db.get(Field, payload.field_id)
    if not field:
        raise HTTPException(status_code=404, detail=f"Field '{payload.field_id}' does not exist.")

    duplicate = db.scalar(
        select(IrrigationSchedule).where(
            IrrigationSchedule.field_id == payload.field_id,
            IrrigationSchedule.status == ModelScheduleStatus.pending,
            IrrigationSchedule.recommended_date == payload.recommended_date,
            IrrigationSchedule.recommended_time == payload.recommended_time,
            IrrigationSchedule.duration_minutes == payload.duration_minutes,
            IrrigationSchedule.water_quantity_liters == payload.water_quantity_liters,
        )
    )
    if duplicate is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "duplicate_schedule",
            f"An identical pending schedule already exists ('{duplicate.schedule_id}').",
        )

    sched = IrrigationSchedule(
        schedule_id=f"SCH_{uuid.uuid4().hex[:12].upper()}",
        field_id=payload.field_id,
        recommended_date=payload.recommended_date,
        recommended_time=payload.recommended_time,
        duration_minutes=payload.duration_minutes,
        water_quantity_liters=payload.water_quantity_liters,
        priority=payload.priority or "normal",
        reason=payload.reason or "Scheduled irrigation recommendation",
        status=ScheduleStatus.pending,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.post("/generate/{field_id}", response_model=IrrigationScheduleOut, status_code=status.HTTP_201_CREATED)
def generate_schedule_for_field(field_id: str, db: Session = Depends(get_db)):
    """Generate and persist an irrigation schedule based on latest FAO-56 agro recommendations."""
    field = db.get(Field, field_id)
    if not field:
        raise HTTPException(status_code=404, detail=f"Field '{field_id}' does not exist.")

    rec = recommend_irrigation(db=db, field_id=field_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Determine liters: area_hectares * recommended_water_mm * 10,000 L/ha-mm
    hectares = field.area_hectares or 1.0
    rec_mm = rec.get("recommended_water_mm", 10.0)
    water_liters = max(100.0, round(hectares * rec_mm * 100.0, 1))
    duration_mins = max(15.0, round((water_liters / 50.0), 1))  # Approx pump rate

    priority_map = {
        "IRRIGATE_IMMEDIATELY": "high",
        "IRRIGATE_LIGHT": "medium",
        "MAINTAIN_MONITORING": "low",
        "DEFER_DUE_TO_RAIN": "low",
    }
    action = rec.get("action", "MAINTAIN_MONITORING")
    reason = rec.get("reason", "FAO-56 Irrigation Recommendation")
    if _is_recent_generated_duplicate(
        db, field_id, reason, duration_mins, water_liters, now
    ):
        raise AppError(
            status.HTTP_409_CONFLICT,
            "duplicate_schedule",
            "A matching irrigation recommendation was already created for this field in the last 15 minutes.",
        )

    sched = IrrigationSchedule(
        schedule_id=f"SCH_{uuid.uuid4().hex[:12].upper()}",
        field_id=field_id,
        recommended_date=now,
        recommended_time=now.strftime("%H:%M"),
        duration_minutes=duration_mins,
        water_quantity_liters=water_liters,
        priority=priority_map.get(action, "normal"),
        reason=reason,
        status=ScheduleStatus.pending,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.patch("/{schedule_id}/status", response_model=IrrigationScheduleOut)
def update_schedule_status(
    schedule_id: str,
    update: IrrigationScheduleStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update status of a schedule (e.g. pending -> completed or skipped or cancelled)."""
    sched = db.get(IrrigationSchedule, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' does not exist.")

    _reject_terminal_status_change(sched, update.status)
    sched.status = update.status
    sched.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.put("/{schedule_id}", response_model=IrrigationScheduleOut)
def update_schedule(
    schedule_id: str,
    payload: IrrigationScheduleUpdate,
    db: Session = Depends(get_db),
):
    """Edit an existing irrigation schedule (time, duration, volume, reason)."""
    sched = db.get(IrrigationSchedule, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' does not exist.")

    if payload.status is not None:
        _reject_terminal_status_change(sched, payload.status)

    if payload.recommended_date is not None:
        sched.recommended_date = payload.recommended_date
    if payload.recommended_time is not None:
        sched.recommended_time = payload.recommended_time
    if payload.duration_minutes is not None:
        sched.duration_minutes = payload.duration_minutes
    if payload.water_quantity_liters is not None:
        sched.water_quantity_liters = payload.water_quantity_liters
    if payload.priority is not None:
        sched.priority = payload.priority
    if payload.reason is not None:
        sched.reason = payload.reason
    if payload.status is not None:
        sched.status = payload.status

    sched.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_or_delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
):
    """Delete or cancel a schedule record."""
    sched = db.get(IrrigationSchedule, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' does not exist.")

    db.delete(sched)
    db.commit()
    return None
