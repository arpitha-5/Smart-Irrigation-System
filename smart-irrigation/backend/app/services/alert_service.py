"""Stores alerts and prevents duplicates for the same ongoing condition.

This module talks to the database but never sends notifications.
It tells the caller what changed, so the notification dispatcher can decide
whom to notify (only NEW or ESCALATED alerts need a message).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.field_threshold import FieldThreshold
from app.services.rule_engine import AlertType, RuleAlert, Thresholds

# Used only when a farmer has not saved limits for a field yet.
DEFAULT_THRESHOLDS = Thresholds(min_moisture=30.0, max_moisture=70.0)

ACTIVE_STATUSES = ("open", "acknowledged")
_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass
class AlertChange:
    alert: Alert
    kind: str   # "new" | "escalated" | "repeat" | "resolved"


def get_thresholds(db: Session, field_id: str) -> Thresholds:
    row = db.get(FieldThreshold, field_id)
    if row is None:
        return DEFAULT_THRESHOLDS
    return Thresholds(
        min_moisture=row.min_moisture,
        max_moisture=row.max_moisture,
        critical_margin=row.critical_margin,
        sensor_silent_minutes=row.sensor_silent_minutes,
    )


def _merge_same_type(found: Iterable[RuleAlert]) -> Dict[str, RuleAlert]:
    """If several alerts have the same type, keep the most severe one."""
    merged: Dict[str, RuleAlert] = {}
    for ra in found:
        key = ra.alert_type.value
        if key not in merged or _RANK[ra.severity.value] > _RANK[merged[key].severity.value]:
            merged[key] = ra
    return merged


def sync_alerts(db: Session, field_id: str, sensor_id: str, found: Iterable[RuleAlert],
                now: datetime, managed_types: Set[AlertType]) -> List[AlertChange]:
    """Bring the stored alerts in line with what the rules found just now.

    found          -- alerts the rules produced for this sensor right now
    managed_types  -- the alert types this check is responsible for. Active alerts of
                      these types that are no longer found get RESOLVED. Other types
                      are left alone (a silence check must not resolve a drought alert).
    """
    changes: List[AlertChange] = []
    merged = _merge_same_type(found)
    active = db.scalars(
        select(Alert).where(
            Alert.field_id == field_id,
            Alert.sensor_id == sensor_id,
            Alert.status.in_(ACTIVE_STATUSES),
        )
    ).all()
    by_type = {a.alert_type: a for a in active}

    for key, ra in merged.items():
        existing = by_type.get(key)
        if existing is None:
            alert = Alert(
                field_id=field_id, sensor_id=sensor_id, alert_type=key,
                severity=ra.severity.value, status="open", source="rule",
                message=ra.message[:400], recommended_action=ra.recommended_action[:300],
                value=ra.value, threshold=ra.threshold,
                occurrence_count=1, created_at=now, last_seen_at=now,
            )
            db.add(alert)
            changes.append(AlertChange(alert, "new"))
        else:
            escalated = _RANK[ra.severity.value] > _RANK[existing.severity]
            existing.severity = ra.severity.value
            existing.message = ra.message[:400]
            existing.value = ra.value
            existing.threshold = ra.threshold
            existing.last_seen_at = now
            existing.occurrence_count += 1
            changes.append(AlertChange(existing, "escalated" if escalated else "repeat"))

    managed_keys = {t.value for t in managed_types}
    for key, existing in by_type.items():
        if key in managed_keys and key not in merged:
            existing.status = "resolved"
            existing.resolved_at = now
            changes.append(AlertChange(existing, "resolved"))

    db.commit()
    return changes
