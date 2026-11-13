from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utcnow() -> datetime:
    """Naive UTC. All timestamps in this system are stored as naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Farmer(Base):
    __tablename__ = "farmers"

    farmer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(160))
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_language: Mapped[Optional[str]] = mapped_column(String(10), default="en")
    village: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    contact_method: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    fields: Mapped[List["Field"]] = relationship(back_populates="farmer")  # noqa: F821
