from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.field import Field
from app.models.irrigation_log import IrrigationLog
from app.schemas.irrigation_log import IrrigationLogCreate, IrrigationLogOut
from app.services.registry_service import _next_id

router = APIRouter(prefix="/irrigation/logs", tags=["irrigation_logs"])


@router.post("", response_model=IrrigationLogOut, status_code=201)
def record_irrigation_log(payload: IrrigationLogCreate, db: Session = Depends(get_db)):
    """Record an actual irrigation event performed on a field."""
    field = db.get(Field, payload.field_id)
    if not field:
        raise HTTPException(status_code=404, detail=f"Field '{payload.field_id}' not found")

    log_id = _next_id(db, IrrigationLog, "log_id", "IRL")
    ts = payload.timestamp or datetime.utcnow()

    volume = payload.water_volume_litres
    if volume is None and field.area_hectares and payload.water_depth_mm > 0:
        volume = round(payload.water_depth_mm * field.area_hectares * 10_000.0, 1)
    elif volume is None:
        volume = round(payload.water_depth_mm * 10_000.0, 1)

    duration = payload.duration_minutes
    flow = payload.flow_rate_lpm or field.pump_flow_rate_lpm
    if duration is None and flow and flow > 0 and volume:
        duration = round(volume / flow, 1)

    record = IrrigationLog(
        log_id=log_id,
        field_id=payload.field_id,
        timestamp=ts,
        water_depth_mm=payload.water_depth_mm,
        water_volume_litres=volume,
        duration_minutes=duration,
        flow_rate_lpm=flow,
        source=payload.source,
        notes=payload.notes,
        is_demo=field.is_demo,
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=List[IrrigationLogOut])
def list_irrigation_logs(
    field_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List historical irrigation records for reporting and farm auditing."""
    stmt = select(IrrigationLog).order_by(IrrigationLog.timestamp.desc())
    if field_id:
        stmt = stmt.where(IrrigationLog.field_id == field_id)
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            stmt = stmt.where(IrrigationLog.timestamp >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            stmt = stmt.where(IrrigationLog.timestamp <= ed)
        except ValueError:
            pass
    stmt = stmt.limit(limit)
    return db.scalars(stmt).all()
