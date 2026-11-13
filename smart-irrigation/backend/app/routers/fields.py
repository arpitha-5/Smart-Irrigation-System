from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Farmer, Field, User
from app.routers.auth import get_current_user, get_farmer_profiles_for_user
from app.schemas.combined import CombinedFieldData
from app.schemas.field import CropUpdate, FieldCreate, FieldDetail, FieldOut, FieldUpdate
from app.schemas.sensor import SensorOut
from app.services import combined_service, registry_service as registry
from app.services.security import get_optional_current_farmer

router = APIRouter(prefix="/fields", tags=["fields"])


@router.post("", response_model=FieldOut, status_code=201)
def create_field(
    body: FieldCreate,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farmer = registry.get_farmer_or_404(db, body.farmer_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    owned_farmer_ids = {
        profile.farmer_id for profile in get_farmer_profiles_for_user(db, user)
    }
    if farmer.farmer_id not in owned_farmer_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only register a field to a farmer profile linked to your account.",
        )
    return registry.create_field(db, body)


@router.get("", response_model=List[FieldOut])
def list_fields(
    farmer_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_farmer: Optional[Farmer] = Depends(get_optional_current_farmer),
):
    stmt = select(Field).order_by(Field.field_id)
    target_farmer = farmer_id or (current_farmer.farmer_id if current_farmer else None)
    if target_farmer:
        stmt = stmt.where(Field.farmer_id == target_farmer)
    return db.scalars(stmt).all()


@router.get("/{field_id}", response_model=FieldDetail)
def get_field(
    field_id: str,
    db: Session = Depends(get_db),
    current_farmer: Optional[Farmer] = Depends(get_optional_current_farmer),
):
    field = registry.get_field_or_404(db, field_id)
    if current_farmer and field.farmer_id != current_farmer.farmer_id and not field.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this field.",
        )
    return field


@router.put("/{field_id}", response_model=FieldOut)
def update_field(
    field_id: str,
    body: FieldUpdate,
    db: Session = Depends(get_db),
    current_farmer: Optional[Farmer] = Depends(get_optional_current_farmer),
):
    field = registry.get_field_or_404(db, field_id)
    if current_farmer and field.farmer_id != current_farmer.farmer_id and not field.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this field.",
        )
    return registry.update_field(db, field_id, body)


@router.delete("/{field_id}", status_code=204)
def delete_field(
    field_id: str,
    db: Session = Depends(get_db),
    current_farmer: Optional[Farmer] = Depends(get_optional_current_farmer),
):
    field = registry.get_field_or_404(db, field_id)
    if current_farmer and field.farmer_id != current_farmer.farmer_id and not field.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this field.",
        )
    registry.delete_field(db, field_id)


@router.put("/{field_id}/crop", response_model=FieldOut)
def assign_crop(field_id: str, body: CropUpdate, db: Session = Depends(get_db)):
    return registry.update_crop(db, field_id, body.crop_type)


@router.get("/{field_id}/sensors", response_model=List[SensorOut])
def field_sensors(field_id: str, db: Session = Depends(get_db)):
    return registry.get_field_or_404(db, field_id).sensors


@router.get("/{field_id}/combined", response_model=CombinedFieldData)
def combined(field_id: str, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    """Field + sensors + recent soil-moisture readings, each paired with the latest weather at/before it."""
    return combined_service.combined_field_data(db, field_id, limit)
