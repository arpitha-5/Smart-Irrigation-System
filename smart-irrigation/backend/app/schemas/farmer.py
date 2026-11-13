from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ID_PATTERN = r"^[A-Za-z0-9_-]{1,32}$"
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"


class FarmerCreate(BaseModel):
    farmer_id: Optional[str] = Field(None, pattern=ID_PATTERN, description="Optional; auto-generated (FR001...) if omitted")
    name: str = Field(min_length=1, max_length=120)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=160)
    preferred_language: Optional[str] = Field("en", max_length=10)
    village: Optional[str] = Field(None, max_length=120)
    district: Optional[str] = Field(None, max_length=120)
    state: Optional[str] = Field(None, max_length=120)
    age: Optional[int] = Field(None, ge=18, le=120)
    contact_method: Optional[str] = Field(None, max_length=40)


class FarmerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=160)
    preferred_language: Optional[str] = Field(None, max_length=10)
    village: Optional[str] = Field(None, max_length=120)
    district: Optional[str] = Field(None, max_length=120)
    state: Optional[str] = Field(None, max_length=120)
    age: Optional[int] = Field(None, ge=18, le=120)
    contact_method: Optional[str] = Field(None, max_length=40)


class FarmerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    farmer_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    preferred_language: Optional[str] = "en"
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    age: Optional[int] = None
    contact_method: Optional[str] = None
    is_demo: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None


class FarmerLoginRequest(BaseModel):
    email_or_phone: str = Field(..., min_length=3, max_length=160)
    password: str = Field(..., min_length=4)


class FarmerRegisterRequest(BaseModel):
    # Step 1: Account
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., max_length=160)
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)

    # Step 2: Profile
    preferred_language: str = Field("en", max_length=10)
    state: Optional[str] = Field(None, max_length=120)
    district: Optional[str] = Field(None, max_length=120)
    village: Optional[str] = Field(None, max_length=120)
    age: Optional[int] = Field(None, ge=18, le=120)
    contact_method: Optional[str] = Field(None, max_length=40)

    # Step 3: Farm & Field Details
    farm_name: Optional[str] = Field(None, max_length=120)
    field_name: Optional[str] = Field(None, max_length=120)
    area: Optional[float] = Field(None, gt=0)
    area_unit: Optional[str] = Field("hectares", max_length=20)  # acres, hectares, sq_meters
    soil_type: Optional[str] = Field("Loamy", max_length=60)
    soil_ph: Optional[float] = Field(None, ge=0, le=14)
    irrigation_method: Optional[str] = Field("Drip", max_length=40)
    pump_flow_rate_lpm: Optional[float] = Field(None, gt=0)

    # Crop details
    crop_type: Optional[str] = Field("Rice", max_length=80)
    crop_variety: Optional[str] = Field(None, max_length=80)
    planting_date: Optional[str] = Field(None, max_length=30)
    growth_stage: Optional[str] = Field("vegetative", max_length=40)

    # Step 4: Location
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_name: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def _handle_aliases(cls, values):
        if isinstance(values, dict):
            if "name" not in values and "full_name" in values:
                values["name"] = values["full_name"]
        return values

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(EMAIL_REGEX, clean):
            raise ValueError("Invalid email format.")
        return clean

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        clean = re.sub(r"[^\d+]", "", v.strip())
        digits = re.sub(r"[^\d]", "", clean)
        if len(digits) < 10:
            raise ValueError("Phone number must contain at least 10 digits.")
        return clean


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    farmer: FarmerOut
