from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.alert import Alert
from app.models.farmer import utcnow
from app.schemas.alert import AlertOut, AlertStatusUpdate, NotificationTestRequest
from app.services.notification_worker import NotificationWorker
from app.services.security import decode_access_token

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _optional_user_id(authorization: Optional[str] = Header(None, convert_underscores=False)) -> Optional[int]:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_access_token(token)
        if isinstance(payload, dict):
            sub = payload.get("sub")
            try:
                return int(sub)
            except (ValueError, TypeError):
                return None
        elif isinstance(payload, int):
            return payload
    return None


@router.get("", response_model=List[AlertOut])
def list_alerts(
    field_id: Optional[str] = Query(None, description="Filter by field ID"),
    sensor_id: Optional[str] = Query(None, description="Filter by sensor ID"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type: drought, over_watering, sensor_failure"),
    severity: Optional[str] = Query(None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    alert_status: Optional[str] = Query(None, alias="status", description="Filter by status: open, acknowledged, resolved"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List alerts with optional multi-criteria filtering and pagination."""
    stmt = select(Alert).order_by(Alert.created_at.desc())

    if field_id:
        stmt = stmt.where(Alert.field_id == field_id)
    if sensor_id:
        stmt = stmt.where(Alert.sensor_id == sensor_id)
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    if severity:
        stmt = stmt.where(Alert.severity == severity.upper())
    if alert_status:
        stmt = stmt.where(Alert.status == alert_status.lower())

    stmt = stmt.offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Retrieve details of a specific alert."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")
    return alert


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(_optional_user_id),
):
    """Mark an open alert as acknowledged."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")

    if alert.status == "resolved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot acknowledge an already resolved alert")

    alert.status = "acknowledged"
    alert.acknowledged_at = utcnow()
    if user_id is not None:
        alert.acknowledged_by_user_id = user_id

    db.commit()
    db.refresh(alert)
    return alert


@router.patch("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """Mark an alert as resolved."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")

    alert.status = "resolved"
    alert.resolved_at = utcnow()

    db.commit()
    db.refresh(alert)
    return alert


@router.post("/notify")
def test_dispatch_notification(req: NotificationTestRequest):
    """Test dispatches an alert notification across SMS, WhatsApp, Email, or Web Push (Option B & C)."""
    worker = NotificationWorker()
    channel = req.channel.upper()
    try:
        if channel == "SMS":
            worker._send_sms(req.recipient, req.message)
        elif channel in ("WHATSAPP", "WA"):
            worker._send_whatsapp(req.recipient, req.message)
        elif channel == "EMAIL":
            worker._send_email(req.recipient, req.title or "AgriPulse Crop Advisory", req.message)
        elif channel in ("WEB_PUSH", "PUSH"):
            worker._send_web_push(req.recipient, req.title or "AgriPulse Crop Advisory", req.message)
        else:
            worker._send_sms(req.recipient, req.message)

        return {
            "status": "success",
            "channel": channel,
            "recipient": req.recipient,
            "message": req.message,
            "dispatched_at": utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "status": "warning",
            "channel": channel,
            "recipient": req.recipient,
            "message": req.message,
            "error": str(e),
            "dispatched_at": utcnow().isoformat(),
        }
