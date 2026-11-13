"""Agricultural intelligence and explainable irrigation recommendation routers."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.recommendation import (
    CropModelMetricsResponse,
    CropRecommendationRequest,
    CropRecommendationResponse,
    IrrigationRecommendationRequest,
    IrrigationRecommendationResponse,
    MLPredictionRequest,
)
from app.services.irrigation_service import attach_irrigation_schedule, recommend_irrigation
from app.services import ml_irrigation_service
from app.services.ml_crop_service import get_crop_recommender

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/crop", response_model=CropRecommendationResponse)
def recommend_crop_endpoint(payload: CropRecommendationRequest):
    recommender = get_crop_recommender()
    result = recommender.predict(
        N=payload.N,
        P=payload.P,
        K=payload.K,
        temperature=payload.temperature,
        humidity=payload.humidity,
        ph=payload.ph,
        rainfall=payload.rainfall,
        soil_moisture=payload.soil_moisture,
    )
    return result


@router.get("/crop/metrics", response_model=CropModelMetricsResponse)
def get_crop_metrics_endpoint():
    recommender = get_crop_recommender()
    return recommender.get_metrics()


from typing import Optional
from app.services import sarvam_service

@router.post("/irrigation", response_model=IrrigationRecommendationResponse)
async def recommend_irrigation_endpoint(
    payload: IrrigationRecommendationRequest,
    lang: Optional[str] = None,
    db: Session = Depends(get_db)
):
    result = recommend_irrigation(
        db=db,
        field_id=payload.field_id,
        crop_type=payload.crop_type,
        growth_stage=payload.growth_stage,
        soil_moisture=payload.soil_moisture,
        temperature=payload.temperature,
        recent_rainfall_mm=payload.recent_rainfall_mm,
        forecast_rainfall_mm=payload.forecast_rainfall_mm,
    )
    scheduled = attach_irrigation_schedule(
        db, result, payload.field_id,
        manual_soil_moisture=payload.soil_moisture,
        irrigation_method=payload.irrigation_method,
        application_rate_mm_per_hour=payload.application_rate_mm_per_hour,
        flow_rate_lpm=payload.flow_rate_lpm,
    )
    if lang and lang.strip().lower() not in ("en", "en-in"):
        # Translate dynamic recommendation using Sarvam AI
        try:
            import asyncio
            translated = await asyncio.wait_for(sarvam_service.translate_recommendation(scheduled, lang), timeout=5.0)
            return translated
        except Exception:
            return scheduled
    return scheduled


@router.get("/irrigation/{field_id}", response_model=IrrigationRecommendationResponse)
async def get_field_irrigation_recommendation(
    field_id: str,
    lang: Optional[str] = None,
    db: Session = Depends(get_db)
):
    result = recommend_irrigation(db=db, field_id=field_id)
    scheduled = attach_irrigation_schedule(db, result, field_id)
    if lang and lang.strip().lower() not in ("en", "en-in"):
        try:
            import asyncio
            translated = await asyncio.wait_for(sarvam_service.translate_recommendation(scheduled, lang), timeout=5.0)
            return translated
        except Exception:
            return scheduled
    return scheduled


@router.get("/irrigation-model")
def get_irrigation_model_info():
    """Status, version, evaluation summary and limitations of the trained irrigation model (model serving metadata)."""
    return ml_irrigation_service.model_info()


@router.post("/irrigation/ml-predict")
def ml_predict_irrigation(payload: MLPredictionRequest):
    """Run the trained model directly on supplied features (no database or weather lookup)."""
    predictor = ml_irrigation_service.get_predictor()
    if predictor is None:
        info = ml_irrigation_service.model_info()
        return {"available": False, "reason": info.get("error") or info.get("fallback")}
    return predictor.predict(payload.model_dump()).to_dict()
