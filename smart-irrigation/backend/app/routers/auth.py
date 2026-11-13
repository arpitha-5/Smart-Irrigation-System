"""Authentication Router: Signup, Login, and Current User Profile.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.crop import Crop
from app.models.farmer import Farmer, utcnow
from app.models.field import Field
from app.models.user import User
from app.schemas.farmer import FarmerLoginRequest, FarmerOut, FarmerRegisterRequest, FarmerUpdate, TokenResponse
from app.schemas.field import FieldOut
from app.services.registry_service import _next_id
from app.services.security import create_access_token, decode_access_token, get_current_farmer, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])
log = logging.getLogger("irrigation.router.auth")


def get_current_user(
    authorization: Optional[str] = Header(None, convert_underscores=False),
    db: Session = Depends(get_db),
) -> int:
    """Extracts authenticated user ID from Authorization Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = str(payload.get("sub", ""))
    if sub.isdigit():
        return int(sub)

    farmer = db.get(Farmer, sub)
    target_email = farmer.email if (farmer and farmer.email) else f"{sub.lower()}@agripulse.local"
    user = db.query(User).filter(User.email == target_email).first()
    if user:
        return user.id
    user = User(
        full_name=farmer.name if farmer else "Farmer",
        email=target_email,
        hashed_password="linked_farmer_account",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.id


def get_farmer_profiles_for_user(db: Session, user: User) -> List[Farmer]:
    from uuid import uuid4

    farmers = db.query(Farmer).filter(Farmer.email == user.email).order_by(Farmer.farmer_id).all()
    if farmers:
        return farmers

    farmer = Farmer(
        farmer_id=uuid4().hex[:32],
        name=user.full_name or "Farmer",
        email=user.email,
        is_demo=False,
    )
    db.add(farmer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        farmers = db.query(Farmer).filter(Farmer.email == user.email).order_by(Farmer.farmer_id).all()
        if farmers:
            return farmers
        log.exception("Failed to create farmer profile for authenticated user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load your farmer profile. Please retry.",
        )
    db.refresh(farmer)
    return [farmer]


def _convert_area_to_hectares(area: Optional[float], unit: Optional[str]) -> Optional[float]:
    if area is None or area <= 0:
        return None
    unit_lower = (unit or "hectares").lower().strip()
    if unit_lower in ("acres", "acre"):
        return round(area * 0.404686, 3)
    if unit_lower in ("sq_meters", "sqm", "m2", "square_metres", "square_meters"):
        return round(area * 0.0001, 4)
    return round(area, 3)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_farmer(payload: FarmerRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new farmer account, default field, soil profile, and crop in a safe transaction."""
    # Check for existing email or phone
    clean_email = payload.email.strip().lower()
    clean_phone = payload.phone.strip()

    existing_farmer = db.scalar(
        select(Farmer).where(
            or_(
                Farmer.email == clean_email,
                Farmer.phone == clean_phone,
            )
        )
    )
    if existing_farmer:
        if existing_farmer.email == clean_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists. Please log in.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this mobile number already exists. Please log in.",
        )

    # 1. Create Farmer
    farmer_id = _next_id(db, Farmer, "farmer_id", "FR")
    pwd_hash = hash_password(payload.password)

    farmer = Farmer(
        farmer_id=farmer_id,
        name=payload.name.strip(),
        phone=clean_phone,
        email=clean_email,
        password_hash=pwd_hash,
        preferred_language=payload.preferred_language or "en",
        state=payload.state,
        district=payload.district,
        village=payload.village,
        age=payload.age,
        contact_method=payload.contact_method,
        is_demo=False,
    )
    db.add(farmer)
    db.flush()

    # 2. Create Initial Field if field name / area provided
    field_title = payload.field_name or payload.farm_name or f"{payload.name}'s Field"
    area_ha = _convert_area_to_hectares(payload.area, payload.area_unit)
    crop_name = (payload.crop_type or "Rice").strip().title()

    field_id = _next_id(db, Field, "field_id", "F")
    field = Field(
        field_id=field_id,
        farmer_id=farmer.farmer_id,
        name=field_title,
        field_name=field_title,
        area_hectares=area_ha if area_ha is not None else 1.0,
        soil_type=payload.soil_type or "Loamy",
        soil_ph=payload.soil_ph,
        irrigation_method=payload.irrigation_method or "Drip",
        pump_flow_rate_lpm=payload.pump_flow_rate_lpm,
        crop_type=crop_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_name=payload.location_name or payload.village or payload.district or payload.state,
        city=payload.district,
        state=payload.state,
        is_demo=False,
    )
    db.add(field)
    db.flush()

    # 3. Create initial Crop record
    crop_date = None
    if payload.planting_date:
        try:
            crop_date = datetime.fromisoformat(payload.planting_date).date()
        except Exception:
            crop_date = None

    crop_id = _next_id(db, Crop, "crop_id", "CR")
    crop = Crop(
        crop_id=crop_id,
        field_id=field.field_id,
        crop_type=crop_name,
        variety=payload.crop_variety,
        planting_date=crop_date,
        growth_stage=payload.growth_stage or "vegetative",
        is_demo=False,
    )
    db.add(crop)

    # Commit entire onboarding transaction
    db.commit()
    db.refresh(farmer)

    # 4. Generate JWT
    token = create_access_token(
        data={"sub": farmer.farmer_id, "name": farmer.name, "email": farmer.email}
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        farmer=FarmerOut.model_validate(farmer),
    )


@router.post("/login", response_model=TokenResponse)
def login_farmer(payload: FarmerLoginRequest, db: Session = Depends(get_db)):
    """Authenticates a farmer using email or mobile number and returns a signed JWT."""
    ident = payload.email_or_phone.strip().lower()
    farmer = db.scalar(
        select(Farmer).where(
            or_(
                Farmer.email == ident,
                Farmer.phone == ident,
                Farmer.name == ident,
            )
        )
    )

    if not farmer or not verify_password(payload.password, farmer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/mobile number or password. Please check your credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={"sub": farmer.farmer_id, "name": farmer.name, "email": farmer.email}
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        farmer=FarmerOut.model_validate(farmer),
    )


@router.get("/me")
def get_current_user_profile(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the authenticated farmer's profile, linked farmer profiles, and fields."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        farmer = db.get(Farmer, str(user_id))
        if not farmer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        f_out = FarmerOut.model_validate(farmer).model_dump()
        return {
            **f_out,
            "id": 1,
            "full_name": farmer.name,
            "email": farmer.email,
            "phone": farmer.phone,
            "farmer_id": farmer.farmer_id,
            "farmer": f_out,
            "fields": [FieldOut.model_validate(f) for f in farmer.fields],
            "farmer_profiles": [
                {
                    "farmer_id": farmer.farmer_id,
                    "name": farmer.name,
                    "email": farmer.email,
                    "phone": farmer.phone,
                }
            ],
        }

    farmers = get_farmer_profiles_for_user(db, user)
    primary_farmer = farmers[0]
    f_out = FarmerOut.model_validate(primary_farmer).model_dump()

    return {
        **f_out,
        "id": user.id,
        "full_name": user.full_name or primary_farmer.name,
        "email": user.email,
        "phone": primary_farmer.phone,
        "farmer_id": primary_farmer.farmer_id,
        "farmer": f_out,
        "fields": [FieldOut.model_validate(f) for f in primary_farmer.fields],
        "farmer_profiles": [
            {
                "farmer_id": profile.farmer_id,
                "name": profile.name,
                "email": profile.email,
                "phone": profile.phone,
            }
            for profile in farmers
        ],
    }


@router.patch("/profile")
@router.put("/profile")
def update_farmer_profile(
    payload: FarmerUpdate,
    current_farmer: Farmer = Depends(get_current_farmer),
    db: Session = Depends(get_db),
):
    """Updates the authenticated farmer's profile fields."""
    data = payload.model_dump(exclude_unset=True)
    for field, val in data.items():
        if hasattr(current_farmer, field) and val is not None:
            setattr(current_farmer, field, val)
    current_farmer.updated_at = utcnow()
    db.commit()
    db.refresh(current_farmer)
    f_out = FarmerOut.model_validate(current_farmer).model_dump()
    return {
        **f_out,
        "full_name": current_farmer.name,
    }

