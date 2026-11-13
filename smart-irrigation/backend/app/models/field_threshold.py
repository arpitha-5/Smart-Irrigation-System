"""Per-field soil-moisture limits chosen by the farmer (one row per field)."""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.farmer import utcnow


class FieldThreshold(Base):
    __tablename__ = "field_thresholds"
    __table_args__ = (
        CheckConstraint(
            "min_moisture >= 0 AND max_moisture <= 100 AND min_moisture < max_moisture",
            name="ck_threshold_range",
        ),
        CheckConstraint("critical_margin > 0", name="ck_threshold_margin"),
        CheckConstraint("sensor_silent_minutes > 0", name="ck_threshold_silent"),
    )

    field_id: Mapped[str] = mapped_column(ForeignKey("fields.field_id"), primary_key=True)
    min_moisture: Mapped[float] = mapped_column(Float)
    max_moisture: Mapped[float] = mapped_column(Float)
    critical_margin: Mapped[float] = mapped_column(Float, default=10.0)
    sensor_silent_minutes: Mapped[int] = mapped_column(Integer, default=60)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
