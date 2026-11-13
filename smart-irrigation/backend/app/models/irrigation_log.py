from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.farmer import utcnow


class IrrigationLog(Base):
    __tablename__ = "irrigation_logs"

    log_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("fields.field_id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    water_depth_mm: Mapped[float] = mapped_column(Float)
    water_volume_litres: Mapped[float] = mapped_column(Float)
    duration_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flow_rate_lpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="farmer_manual")  # farmer_manual, sensor_detected, scheduled
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    field: Mapped["Field"] = relationship(back_populates="irrigation_logs")  # noqa: F821
