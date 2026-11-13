"""Irrigation scheduling rules (Week 3-4).

Takes the numerical irrigation depth predicted by the ML model plus weather and field context and returns
a documented recommendation. Full rules, units and limitations: docs/scheduling_logic.md.

Design rules
  * Pure Python, no database / HTTP / ML imports. It never calls the weather API and never loads a model.
  * The predicted quantity is never recategorised (no Low/Medium/High) and never modified. Rainfall is NOT
    subtracted from it: the rules only decide whether to apply the predicted depth now (IRRIGATE), hold it
    back (DEFER) or refuse to recommend anything (WITHHELD).
  * Nothing is fabricated: a missing/invalid prediction or unusable weather gives WITHHELD with a reason and
    ``recommended_irrigation_mm = None``. No default weather values are ever substituted.
  * Unit: millimetres of water depth over the field surface (1 mm = 1 L/m2). A volume in litres is only
    reported when a valid ``area_hectares`` is supplied (1 mm over 1 ha = 10,000 L).

The output is advisory and is not guaranteed to be agronomically correct.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from numbers import Real
from typing import Any, Dict, List, Mapping, Optional

# ── Public constants ──────────────────────────────────────────────────────────────────────────────

ACTION_IRRIGATE = "IRRIGATE"                    # apply the predicted depth now
ACTION_DEFER = "DEFER"                          # hold the predicted depth back because of rain; re-evaluate later
ACTION_NONE = "NO_IRRIGATION_NEEDED"            # the model predicted exactly 0 mm
ACTION_WITHHELD = "WITHHELD"                    # no recommendation can be made safely (see reason_codes)
ACTIONS = (ACTION_IRRIGATE, ACTION_DEFER, ACTION_NONE, ACTION_WITHHELD)

UNIT = "mm"
UNIT_BASIS = "depth of water over the field surface (1 mm = 1 L per m2)"
LITRES_PER_MM_PER_HECTARE = 10_000.0           # 1 mm * 10,000 m2

DISCLAIMER = (
    "Advisory output of documented, rule-based scheduling logic. It is not guaranteed to be agronomically "
    "correct. Verify soil, crop stage, emitter/flow rate and local conditions before applying water."
)

ASSUMPTIONS = (
    "predicted_irrigation_mm is a net irrigation DEPTH in millimetres for one irrigation event "
    "(target definition and unit still to be confirmed with the ML teammate).",
    "The prediction is not adjusted for rainfall by this module; rainfall only triggers a hold (DEFER).",
    "Weather rainfall is the provider's 'last hour' precipitation (mm); it says nothing about daily totals.",
    "Volume (litres) assumes the whole registered field area is irrigated uniformly with no efficiency losses.",
)

# Reason codes
PREDICTION_MISSING = "prediction_missing"
PREDICTION_INVALID = "prediction_invalid"
PREDICTION_NEGATIVE = "prediction_negative"
PREDICTION_IMPLAUSIBLE = "prediction_implausible"
FIELD_DATA_INVALID = "field_data_invalid"
PREDICTION_ZERO = "prediction_zero"
WEATHER_MISSING = "weather_missing"
WEATHER_MALFORMED = "weather_malformed"
WEATHER_UNAVAILABLE = "weather_unavailable"
WEATHER_STALE = "weather_stale"
WEATHER_MOCK = "weather_mock"
WEATHER_NOT_USABLE = "weather_not_usable"
WEATHER_VALUES_INVALID = "weather_values_invalid"
RAIN_NOW = "rain_in_last_hour"
FORECAST_RAIN = "forecast_rain"
NO_DEFERRAL_RULE_MET = "no_deferral_rule_met"


@dataclass(frozen=True)
class ScheduleConfig:
    """Tunable thresholds. Defaults are PROPOSALS for team review (see docs/scheduling_logic.md section 4)."""

    # Hold irrigation if at least this much rain fell in the last hour. 2.5 mm/h is the usual lower bound of
    # "moderate" rain intensity (light < 2.5 mm/h), i.e. rain heavy enough that irrigating would be wasteful.
    defer_if_rain_last_1h_mm: float = 2.5
    # Hold irrigation if the forecast expects at least this much rain inside the forecast window.
    defer_if_forecast_rain_mm: float = 10.0
    # Forecast windows longer than this are ignored (rain several days away should not delay today's water).
    max_forecast_window_hours: float = 24.0
    # Suggested re-run delay after a DEFER caused by current rain.
    reevaluate_after_rain_hours: float = 3.0
    # Predictions above this are treated as probable unit/model errors and withheld (not clipped).
    max_plausible_irrigation_mm: float = 100.0
    # Predictions below this get a "may not be practical to apply" warning (the value is still preserved).
    small_depth_warning_mm: float = 1.0

    def __post_init__(self) -> None:
        for name in ("defer_if_rain_last_1h_mm", "defer_if_forecast_rain_mm", "max_forecast_window_hours",
                     "reevaluate_after_rain_hours", "max_plausible_irrigation_mm", "small_depth_warning_mm"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"ScheduleConfig.{name} must be a positive finite number, got {value!r}.")


@dataclass
class IrrigationSchedule:
    field_id: Optional[str]
    action: str                                   # one of ACTIONS
    predicted_irrigation_mm: Optional[float]      # the model output, echoed unchanged (None if absent/invalid)
    recommended_irrigation_mm: Optional[float]    # = predicted when IRRIGATE; 0.0 when DEFER/NONE; None when WITHHELD
    unit: str = UNIT
    unit_basis: str = UNIT_BASIS
    volume: Optional[Dict[str, Any]] = None       # only when action == IRRIGATE and a valid area was supplied
    reasons: List[str] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    reevaluate_after_hours: Optional[float] = None
    weather_context: Dict[str, Any] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=lambda: list(ASSUMPTIONS))
    disclaimer: str = DISCLAIMER
    generated_at_utc: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Helpers ───────────────────────────────────────────────────────────────────────────────────────

def _read(obj: Any, key: str, default: Any = None) -> Any:
    """Read ``key`` from a Mapping or an object (adapter result, ORM row, pydantic model)."""
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _is_number(value: Any) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _num_or_none(value: Any) -> Optional[float]:
    return float(value) if _is_number(value) else None


def _check_prediction(value: Any):
    """Return (float_value, None, None) or (None, reason_code, message)."""
    if value is None:
        return None, PREDICTION_MISSING, "No irrigation prediction was supplied."
    if isinstance(value, bool) or not isinstance(value, Real):
        return None, PREDICTION_INVALID, f"Prediction must be a number (mm), got {type(value).__name__}."
    number = float(value)
    if not math.isfinite(number):
        return None, PREDICTION_INVALID, "Prediction is not a finite number."
    return number, None, None


def _observation_summary(obs: Any) -> Optional[Dict[str, Any]]:
    if obs is None:
        return None
    return {
        "observed_at_utc": _read(obs, "observed_at_utc"),
        "age_minutes": _num_or_none(_read(obs, "age_minutes")),
        "temperature_c": _num_or_none(_read(obs, "temperature_c")),
        "humidity_pct": _num_or_none(_read(obs, "humidity_pct")),
        "rainfall_last_1h_mm": _num_or_none(_read(obs, "rainfall_last_1h_mm")),
        "is_mock": bool(_read(obs, "is_mock", False)),
        "data_kind": "current_observation",
    }


def _forecast_summary(forecast: Any) -> Dict[str, Any]:
    """Normalised forecast block; ``usable`` is only True for a properly labelled forecast with valid numbers."""
    if forecast is None or not bool(_read(forecast, "available", False)):
        reason = _read(forecast, "reason") if forecast is not None else None
        return {"available": False, "usable": False, "data_kind": "forecast",
                "reason": reason or "No forecast data supplied."}
    kind = _read(forecast, "data_kind")
    window = _read(forecast, "window_hours")
    expected = _read(forecast, "expected_rainfall_mm")
    summary = {"available": True, "usable": False, "data_kind": kind, "window_hours": _num_or_none(window),
               "expected_rainfall_mm": _num_or_none(expected)}
    if kind != "forecast":
        summary["reason"] = "Ignored: data is not labelled data_kind='forecast' (forecasts must not be mixed with observations)."
    elif not _is_number(window) or float(window) <= 0 or not _is_number(expected) or float(expected) < 0:
        summary["reason"] = "Ignored: forecast window_hours / expected_rainfall_mm missing or invalid."
    else:
        summary["usable"] = True
    return summary


def _assess_weather(weather_data: Any) -> Dict[str, Any]:
    """Decide whether the weather input can support a recommendation. Never invents values."""
    ctx: Dict[str, Any] = {"status": None, "data_origin": None, "observation": None,
                           "forecast": _forecast_summary(None), "weather_warnings": []}
    if weather_data is None:
        return {"usable": False, "code": WEATHER_MISSING, "message": "No weather data was supplied.", "ctx": ctx}

    status = _read(weather_data, "status")
    obs = _read(weather_data, "observation")
    ctx.update(status=status, data_origin=_read(weather_data, "data_origin"),
               observation=_observation_summary(obs),
               forecast=_forecast_summary(_read(weather_data, "forecast")),
               weather_warnings=list(_read(weather_data, "warnings", None) or []))

    if not isinstance(status, str):
        return {"usable": False, "code": WEATHER_MALFORMED,
                "message": "weather_data has no 'status'; expected the output of weather_adapter.get_field_weather().",
                "ctx": ctx}
    if status == "stale":
        return {"usable": False, "code": WEATHER_STALE,
                "message": "Weather observation is too old to support a safe recommendation.", "ctx": ctx}
    if status == "mock":
        return {"usable": False, "code": WEATHER_MOCK,
                "message": "Weather is simulated (mock mode), not a real observation.", "ctx": ctx}
    if status == "unavailable":
        err = _read(weather_data, "error") or {}
        detail = _read(err, "code")
        return {"usable": False, "code": WEATHER_UNAVAILABLE,
                "message": "Weather is unavailable" + (f" ({detail})." if detail else "."), "ctx": ctx}
    if status != "ok" or _read(weather_data, "usable_for_prediction") is not True:
        return {"usable": False, "code": WEATHER_NOT_USABLE,
                "message": f"Weather status '{status}' is not marked usable_for_prediction.", "ctx": ctx}

    if obs is None or bool(_read(obs, "is_mock", False)):
        return {"usable": False, "code": WEATHER_MALFORMED,
                "message": "Weather status is ok but no real observation is present.", "ctx": ctx}
    if not _is_number(_read(obs, "rainfall_last_1h_mm")) or float(_read(obs, "rainfall_last_1h_mm")) < 0:
        return {"usable": False, "code": WEATHER_VALUES_INVALID,
                "message": "Observation rainfall_last_1h_mm is missing or invalid, so rain rules cannot be evaluated.",
                "ctx": ctx}
    return {"usable": True, "code": None, "message": None, "ctx": ctx}


def _volume(mm: float, area_hectares: Any) -> Optional[Dict[str, Any]]:
    if not _is_number(area_hectares) or float(area_hectares) <= 0:
        return None
    area = float(area_hectares)
    litres = mm * area * LITRES_PER_MM_PER_HECTARE
    return {
        "litres": round(litres, 1),
        "cubic_metres": round(litres / 1000.0, 3),
        "area_hectares": area,
        "basis": "1 mm over 1 ha = 10 m3 = 10,000 L; assumes the whole registered area is irrigated uniformly, "
                 "with no application-efficiency losses.",
    }


# ── Public API ────────────────────────────────────────────────────────────────────────────────────

def generate_irrigation_schedule(
    predicted_irrigation_mm: Any,
    weather_data: Any,
    field_data: Any,
    *,
    config: Optional[ScheduleConfig] = None,
    now: Optional[datetime] = None,
) -> IrrigationSchedule:
    """Return a scheduling recommendation. Never raises for bad data: it returns WITHHELD with reasons.

    predicted_irrigation_mm  model output (number, mm of depth). None / non-numeric / NaN / negative are rejected.
    weather_data             ``FieldWeatherResult`` from ``weather_adapter.get_field_weather`` or its ``to_dict()``.
    field_data               mapping or object with ``field_id`` (required) and ``area_hectares`` (optional).
    """
    cfg = config or ScheduleConfig()
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)

    weather = _assess_weather(weather_data)
    raw_field_id = _read(field_data, "field_id")
    field_id = str(raw_field_id) if isinstance(raw_field_id, (str, int)) and not isinstance(raw_field_id, bool) and str(raw_field_id).strip() else None

    result = IrrigationSchedule(
        field_id=field_id, action=ACTION_WITHHELD, predicted_irrigation_mm=None, recommended_irrigation_mm=None,
        weather_context=weather["ctx"], generated_at_utc=stamp.astimezone(timezone.utc).isoformat(timespec="seconds"),
        thresholds={"defer_if_rain_last_1h_mm": cfg.defer_if_rain_last_1h_mm,
                    "defer_if_forecast_rain_mm": cfg.defer_if_forecast_rain_mm,
                    "max_forecast_window_hours": cfg.max_forecast_window_hours,
                    "max_plausible_irrigation_mm": cfg.max_plausible_irrigation_mm},
    )

    def withhold(code: str, message: str) -> IrrigationSchedule:
        result.action, result.recommended_irrigation_mm = ACTION_WITHHELD, None
        result.reason_codes.append(code)
        result.reasons.append(message)
        return result

    # 1. Prediction must be a usable number. The echo is only set once it is valid.
    value, code, message = _check_prediction(predicted_irrigation_mm)
    if code:
        return withhold(code, message)
    result.predicted_irrigation_mm = value
    if value < 0:
        return withhold(PREDICTION_NEGATIVE, f"Predicted depth {value} mm is negative; not clipped to zero. "
                        "Agree with the ML teammate how negative regression output should be handled.")
    if value > cfg.max_plausible_irrigation_mm:
        return withhold(PREDICTION_IMPLAUSIBLE, f"Predicted depth {value} mm exceeds the plausibility ceiling of "
                        f"{cfg.max_plausible_irrigation_mm} mm; possible unit or model error. Not clipped.")

    # 2. Field context must identify the field.
    if field_id is None:
        return withhold(FIELD_DATA_INVALID, "field_data must provide a non-empty 'field_id'.")

    # 3. Exactly zero predicted: nothing to schedule, whatever the weather says.
    if value == 0:
        result.action, result.recommended_irrigation_mm = ACTION_NONE, 0.0
        result.reason_codes.append(PREDICTION_ZERO)
        result.reasons.append("The model predicts 0 mm of irrigation; no irrigation is scheduled.")
        if not weather["usable"]:
            result.warnings.append(f"Weather not used ({weather['code']}); it does not change a 0 mm prediction.")
        return result

    # 4. Weather gate: no usable observation, no recommendation (no defaults, no guesses).
    if not weather["usable"]:
        return withhold(weather["code"], weather["message"] + " No recommendation is made; the caller decides "
                        "whether to act on the raw model prediction.")
    result.warnings.extend(result.weather_context["weather_warnings"])
    obs = result.weather_context["observation"]
    forecast = result.weather_context["forecast"]
    rain_1h = obs["rainfall_last_1h_mm"]

    # 5. Rule R1: substantial rain in the last hour -> hold.
    if rain_1h >= cfg.defer_if_rain_last_1h_mm:
        result.action, result.recommended_irrigation_mm = ACTION_DEFER, 0.0
        result.reevaluate_after_hours = cfg.reevaluate_after_rain_hours
        result.reason_codes.append(RAIN_NOW)
        result.reasons.append(
            f"{rain_1h} mm of rain in the last hour (hold threshold {cfg.defer_if_rain_last_1h_mm} mm). "
            f"Irrigation is held; the predicted {value} mm is unchanged and should be re-evaluated in "
            f"~{cfg.reevaluate_after_rain_hours:g} h with fresh weather.")
        if not forecast["usable"]:
            result.warnings.append("Forecast not used: " + forecast.get("reason", "unavailable"))
        return result

    # 6. Rule R2: forecast rain inside the window -> hold (only a properly labelled, valid forecast counts).
    if forecast["usable"]:
        window, expected = forecast["window_hours"], forecast["expected_rainfall_mm"]
        if window <= cfg.max_forecast_window_hours and expected >= cfg.defer_if_forecast_rain_mm:
            result.action, result.recommended_irrigation_mm = ACTION_DEFER, 0.0
            result.reevaluate_after_hours = window
            result.reason_codes.append(FORECAST_RAIN)
            result.reasons.append(
                f"Forecast expects {expected} mm of rain within {window:g} h (hold threshold "
                f"{cfg.defer_if_forecast_rain_mm} mm). Irrigation is held; the predicted {value} mm is unchanged. "
                "Forecast rain is not guaranteed: re-evaluate after the window.")
            return result
        if window > cfg.max_forecast_window_hours:
            result.warnings.append(f"Forecast window {window:g} h exceeds {cfg.max_forecast_window_hours:g} h; forecast ignored.")
    else:
        result.warnings.append("Forecast not used: " + forecast.get("reason", "unavailable")
                               + " Decision is based on the current observation only.")

    # 7. No hold rule met: apply the model's depth exactly as predicted.
    result.action, result.recommended_irrigation_mm = ACTION_IRRIGATE, value
    result.reason_codes.append(NO_DEFERRAL_RULE_MET)
    result.reasons.append(f"No rain-based hold rule applies; apply the predicted {value} mm (depth).")
    if rain_1h > 0:
        result.warnings.append(f"Light rain ({rain_1h} mm in the last hour) is below the hold threshold; the predicted "
                               "depth was NOT reduced for it.")
    if value < cfg.small_depth_warning_mm:
        result.warnings.append(f"Predicted depth {value} mm is very small and may not be practical to apply.")
    result.volume = _volume(value, _read(field_data, "area_hectares"))
    if result.volume is None:
        result.warnings.append("No valid area_hectares for this field; depth reported in mm only, volume not computed.")
    return result


__all__ = ["ACTIONS", "ACTION_IRRIGATE", "ACTION_DEFER", "ACTION_NONE", "ACTION_WITHHELD", "IrrigationSchedule",
           "ScheduleConfig", "generate_irrigation_schedule"]
