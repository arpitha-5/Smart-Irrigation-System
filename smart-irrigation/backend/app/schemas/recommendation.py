from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CropRecommendationRequest(BaseModel):
    N: float = Field(..., ge=0.0, le=200.0, description="Nitrogen ratio in soil (kg/ha)")
    P: float = Field(..., ge=0.0, le=200.0, description="Phosphorus ratio in soil (kg/ha)")
    K: float = Field(..., ge=0.0, le=250.0, description="Potassium ratio in soil (kg/ha)")
    temperature: float = Field(..., ge=-10.0, le=60.0, description="Ambient temperature (°C)")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Relative humidity (%)")
    ph: float = Field(..., ge=0.0, le=14.0, description="Soil pH level (0-14)")
    rainfall: float = Field(..., ge=0.0, le=500.0, description="Rainfall (mm)")
    soil_moisture: Optional[float] = Field(None, ge=0.0, le=100.0, description="Optional soil moisture (%)")


class CropCandidate(BaseModel):
    crop: str
    probability: float
    confidence_pct: float


class CropRecommendationResponse(BaseModel):
    recommended_crop: str
    confidence: float
    top_candidates: List[CropCandidate]
    agronomic_explanation: str
    input_parameters: Dict[str, float]
    model_metadata: Dict[str, Any]
    limitations: str


class CropModelMetricsResponse(BaseModel):
    model_name: str
    algorithm: str
    train_samples: int
    test_samples: int
    test_accuracy: float
    macro_f1: float
    feature_names: List[str]
    feature_importances: Dict[str, float]
    trained_at: str
    notes: List[str]


class IrrigationRecommendationRequest(BaseModel):
    field_id: Optional[str] = None
    crop_type: Optional[str] = None
    growth_stage: Optional[str] = Field("vegetative", description="seedling, vegetative, flowering, maturity")
    soil_moisture: Optional[float] = Field(None, ge=0.0, le=100.0)
    temperature: Optional[float] = Field(None, ge=-20.0, le=60.0)
    recent_rainfall_mm: Optional[float] = Field(0.0, ge=0.0)
    forecast_rainfall_mm: Optional[float] = Field(0.0, ge=0.0)
    # Optional, used only to turn the depth into time slots (duration = depth / rate).
    irrigation_method: Optional[str] = Field(None, description="drip, sprinkler or flood")
    application_rate_mm_per_hour: Optional[float] = Field(None, gt=0.0, le=100.0)
    flow_rate_lpm: Optional[float] = Field(None, gt=0.0, description="Pump flow rate in litres per minute (LPM)")


class MLPredictionRequest(BaseModel):
    """Direct input to the ML irrigation model (no database needed)."""
    crop_type: str
    days_after_sowing: float = Field(ge=0.0, le=400.0)
    soil_moisture: float = Field(ge=0.0, le=100.0)
    soil_moisture_change_24h: Optional[float] = Field(None, ge=-100.0, le=100.0)
    rain_forecast_next24h_mm: Optional[float] = Field(None, ge=0.0, le=500.0)


class ScheduleInputInfo(BaseModel):
    """Provenance of the water depth handed to the scheduler."""
    predicted_irrigation_mm: Optional[float] = None
    unit: str = "mm"
    source: str  # "ml_model", "rule_based_recommendation" or "rule_based_emergency_override"
    is_ml_prediction: bool  # True only when the trained ML model produced the depth
    recommendation_engine: Optional[str] = None
    note: str


class IrrigationScheduleResponse(BaseModel):
    """Output of irrigation_scheduler.generate_irrigation_schedule (IrrigationSchedule.to_dict())."""
    model_config = ConfigDict(extra="allow")  # new scheduler fields pass through instead of being dropped

    field_id: Optional[str] = None
    action: str  # IRRIGATE, DEFER, NO_IRRIGATION_NEEDED, WITHHELD
    predicted_irrigation_mm: Optional[float] = None  # the input depth, echoed unchanged
    recommended_irrigation_mm: Optional[float] = None  # = input when IRRIGATE; 0.0 for DEFER / NONE; None if WITHHELD
    unit: str = "mm"
    unit_basis: str = ""
    volume: Optional[Dict[str, Any]] = None  # only for IRRIGATE with a valid field area
    reasons: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    reevaluate_after_hours: Optional[float] = None
    weather_context: Dict[str, Any] = Field(default_factory=dict)
    thresholds: Dict[str, float] = Field(default_factory=dict)
    assumptions: List[str] = Field(default_factory=list)
    disclaimer: str = ""
    generated_at_utc: str = ""


class IrrigationRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    action: str  # IRRIGATE_IMMEDIATELY, IRRIGATE_LIGHT, MAINTAIN_MONITORING, DEFER_DUE_TO_RAIN
    recommended_water_mm: float
    urgency: str  # HIGH, MODERATE, LOW, NONE
    reason: str
    factors_evaluated: Dict[str, Any]
    recommendation_engine: str
    sensor_freshness: str
    limitations: str
    # Additive, optional (None when no registered field is available). Existing clients can ignore these.
    irrigation_schedule: Optional[IrrigationScheduleResponse] = None
    schedule_input: Optional[ScheduleInputInfo] = None
    scheduling_note: Optional[str] = None
    # Additive, optional (Milestone 2). ml_prediction explains whether the trained model produced the depth or why not;
    # irrigation_plan holds time slots; alerts holds the rule-based emergency / warning alerts.
    ml_prediction: Optional[Dict[str, Any]] = None
    irrigation_plan: Optional[Dict[str, Any]] = None
    alerts: Optional[Dict[str, Any]] = None
    scheduling_recommendation: Optional[Dict[str, Any]] = None

    # Multilingual translation fields (Sarvam AI integration)
    translated_reason: Optional[str] = None
    translated_action: Optional[str] = None
    translated_urgency: Optional[str] = None
    translated_limitations: Optional[str] = None
    translated_scheduling_note: Optional[str] = None
    language: Optional[str] = None
    language_code: Optional[str] = None
