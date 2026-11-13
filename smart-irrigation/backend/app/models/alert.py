"""One row per ongoing (or past) alert condition for a sensor in a field."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.farmer import utcnow


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        # The database itself refuses a second ACTIVE (open or acknowledged) alert
        # of the same type for the same sensor. Resolved alerts are not counted.
        Index(
            "uq_alert_one_active", "field_id", "sensor_id", "alert_type",
            unique=True,
            postgresql_where=text("status <> 'resolved'"),
            sqlite_where=text("status <> 'resolved'"),
        ),
        Index("ix_alert_field_created", "field_id", "created_at"),
        Index("ix_alert_status", "status"),
    )

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.field_id"))
    sensor_id: Mapped[str] = mapped_column(ForeignKey("sensors.sensor_id"))
    alert_type: Mapped[str] = mapped_column(String(30))      # drought | over_watering | sensor_failure
    severity: Mapped[str] = mapped_column(String(10))        # LOW | MEDIUM | HIGH | CRITICAL
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | acknowledged | resolved
    source: Mapped[str] = mapped_column(String(10), default="rule")  # rule | ml
    message: Mapped[str] = mapped_column(String(400))
    recommended_action: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
