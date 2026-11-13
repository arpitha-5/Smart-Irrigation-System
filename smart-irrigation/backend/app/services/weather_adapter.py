"""Weather adapter for the irrigation prediction workflow (Week 3-4).

A thin, read-only layer over the EXISTING weather stack. It adds no endpoint, table or API client:
  field lookup      -> registry_service.get_field_or_404
  live fetch+store  -> weather_service.get_weather_for_field (WeatherProvider -> OpenWeatherMap, weather_data table)
  validation        -> data_cleaning_service.clean_weather
  config / API key  -> app.config.Settings (OPENWEATHER_API_KEY, WEATHER_TIMEOUT_SECONDS, WEATHER_MOCK)

``get_field_weather`` never raises for weather problems. It returns a ``FieldWeatherResult`` whose ``status``
tells the caller whether a prediction is safe:
  ok           real, complete, fresh observation          -> usable_for_prediction = True
  stale        real observation older than max age        -> False
  mock         synthetic data (WEATHER_MOCK=true)         -> False unless allow_mock=True
  unavailable  nothing usable (timeout, no key, bad data) -> False, ``error`` explains why
Nothing is imputed: missing values are never replaced by defaults.

Live observation vs forecast: everything under ``observation`` is ``data_kind == "current_observation"``.
``forecast`` is always a separate block (``data_kind == "forecast"``). It is fetched from the OpenWeatherMap
5-day/3-hour forecast API only when the current observation is a fresh, real, live one, and it is
``available: False`` with a ``reason`` whenever it was not requested or could not be built. A missing forecast is
never turned into "0 mm expected" (see ``build_forecast_block`` and docs/scheduling_logic.md).
"""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.errors import AppError
from app.services import registry_service, weather_service
from app.services.data_cleaning_service import DataValidationError, clean_weather
from app.services.weather_service import FORECAST_STEP_HOURS, ProviderForecast, WeatherProvider

log = logging.getLogger("irrigation.weather_adapter")

STATUS_OK = "ok"
STATUS_STALE = "stale"
STATUS_MOCK = "mock"
STATUS_UNAVAILABLE = "unavailable"

ORIGIN_LIVE = "live_api"
ORIGIN_STORED = "stored_observation"

# PROPOSED defaults, to be confirmed by the team (docs/scheduling_logic.md section 4).
DEFAULT_MAX_OBSERVATION_AGE_MINUTES = 180.0
FUTURE_TOLERANCE_MINUTES = 5.0

# Canonical (unit-suffixed) observation names that callers may map model features onto.
OBSERVATION_FEATURES = ("temperature_c", "humidity_pct", "rainfall_last_1h_mm", "wind_speed_ms")

DEFAULT_FORECAST_WINDOW_HOURS = 24.0
FORECAST_SOURCE = "openweathermap_5day_3hour_forecast"

FORECAST_NOT_AVAILABLE: Dict[str, Any] = {
    "available": False,
    "data_kind": "forecast",
    "reason": "No forecast has been retrieved for this result.",
}


def _forecast_unavailable(reason: str, code: Optional[str] = None) -> Dict[str, Any]:
    block: Dict[str, Any] = {"available": False, "data_kind": "forecast", "reason": reason}
    if code:
        block["error_code"] = code
    return block


class WeatherNotUsableError(Exception):
    """Raised by FieldWeatherResult.to_feature_dict when the result must not be used for a prediction."""


@dataclass(frozen=True)
class WeatherObservation:
    """A real CURRENT observation. Units are in the attribute names; rainfall is mm in the last hour."""
    observed_at_utc: str
    fetched_at_utc: Optional[str]
    age_minutes: float
    temperature_c: float
    humidity_pct: float
    rainfall_last_1h_mm: float
    wind_speed_ms: Optional[float]
    condition: Optional[str]
    source: str
    is_mock: bool
    data_kind: str = "current_observation"


@dataclass
class FieldWeatherResult:
    field_id: str
    status: str
    usable_for_prediction: bool
    data_origin: Optional[str] = None                 # live_api | stored_observation
    observation: Optional[WeatherObservation] = None
    forecast: Dict[str, Any] = field(default_factory=lambda: dict(FORECAST_NOT_AVAILABLE))
    warnings: List[str] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None            # set when status == unavailable
    live_fetch_error: Optional[Dict[str, Any]] = None  # set when the live call failed (even if a stored row was used)
    retrieved_at_utc: str = ""
    max_age_minutes: float = DEFAULT_MAX_OBSERVATION_AGE_MINUTES
    data_kind: str = "current_observation"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_feature_dict(self, feature_map: Mapping[str, str]) -> Dict[str, float]:
        """Rename observation values to the ML model's feature names. NO unit conversion is done.

        ``feature_map`` maps model feature name -> canonical name in OBSERVATION_FEATURES, e.g.
        ``{"temperature": "temperature_c"}``. Raises WeatherNotUsableError if the weather is not usable or a
        requested value is missing, and ValueError for an unknown canonical name. Agree the mapping (and any unit
        conversion, e.g. rainfall mm/h vs a monthly mm feature) with the ML teammate first.
        """
        if not self.usable_for_prediction or self.observation is None:
            raise WeatherNotUsableError(f"Weather for field {self.field_id} is not usable (status={self.status}).")
        out: Dict[str, float] = {}
        for model_name, canonical in feature_map.items():
            if canonical not in OBSERVATION_FEATURES:
                raise ValueError(f"Unknown weather feature '{canonical}'. Choose from {OBSERVATION_FEATURES}.")
            value = getattr(self.observation, canonical)
            if value is None:
                raise WeatherNotUsableError(f"'{canonical}' is not available in the observation.")
            out[model_name] = value
        return out


# ── Helpers ───────────────────────────────────────────────────────────────────────────────────────

def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _iso(value: Any) -> Optional[str]:
    dt = _naive_utc(value)
    return dt.isoformat(timespec="seconds") if dt else None


def _opt_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _unavailable(field_id: str, code: str, message: str, now: datetime, max_age: float,
                 details: Any = None, warnings: Optional[List[str]] = None,
                 live_fetch_error: Optional[Dict[str, Any]] = None) -> FieldWeatherResult:
    return FieldWeatherResult(
        field_id=field_id, status=STATUS_UNAVAILABLE, usable_for_prediction=False,
        warnings=list(warnings or []), error={"code": code, "message": message, "details": details},
        live_fetch_error=live_fetch_error, retrieved_at_utc=now.isoformat(timespec="seconds"), max_age_minutes=max_age)


def _error_dict(exc: AppError) -> Dict[str, Any]:
    return {"code": exc.code, "message": exc.message, "details": exc.details}


def _safe_rollback(db: Session) -> None:
    try:
        db.rollback()
    except Exception:  # noqa: BLE001 - best effort only
        pass


def assess_weather_record(record: Any, *, field_id: str, origin: str, now: Optional[datetime] = None,
                          max_age_minutes: float = DEFAULT_MAX_OBSERVATION_AGE_MINUTES,
                          allow_mock: bool = False) -> FieldWeatherResult:
    """Validate one WeatherData-like record (missing/invalid values, future time, mock, staleness)."""
    now = now or _utc_now()
    observed = _naive_utc(getattr(record, "timestamp", None))
    if observed is None:
        return _unavailable(field_id, "weather_invalid_data", "Weather record has no valid observation time.",
                            now, max_age_minutes)
    try:
        cleaned = clean_weather(getattr(record, "temperature", None), getattr(record, "humidity", None),
                                getattr(record, "rainfall", None))
    except DataValidationError as exc:
        return _unavailable(field_id, "weather_invalid_data",
                            "Weather record has missing or implausible values; it was not used.",
                            now, max_age_minutes, details=[i.as_dict() for i in exc.issues])

    age = (now - observed).total_seconds() / 60.0
    if age < -FUTURE_TOLERANCE_MINUTES:
        return _unavailable(field_id, "weather_observation_in_future",
                            f"Observation time is {-age:.0f} min in the future; refusing to use it.", now, max_age_minutes)
    age = max(age, 0.0)

    is_mock = bool(getattr(record, "is_mock", False))
    obs = WeatherObservation(
        observed_at_utc=observed.isoformat(timespec="seconds"), fetched_at_utc=_iso(getattr(record, "fetched_at", None)),
        age_minutes=round(age, 1), temperature_c=cleaned.temperature, humidity_pct=cleaned.humidity,
        rainfall_last_1h_mm=cleaned.rainfall, wind_speed_ms=_opt_float(getattr(record, "wind_speed", None)),
        condition=getattr(record, "condition", None), source=str(getattr(record, "source", "unknown")), is_mock=is_mock)

    warnings: List[str] = []
    if origin == ORIGIN_STORED:
        warnings.append(f"Using a stored observation that is {age:.0f} min old, not a fresh API response.")
    if is_mock:
        status, usable = STATUS_MOCK, allow_mock
        warnings.append("Weather is SIMULATED (WEATHER_MOCK=true); it is not a real observation.")
    elif age > max_age_minutes:
        status, usable = STATUS_STALE, False
        warnings.append(f"Observation is {age:.0f} min old (limit {max_age_minutes:g} min); too stale to rely on.")
    else:
        status, usable = STATUS_OK, True
    return FieldWeatherResult(
        field_id=field_id, status=status, usable_for_prediction=usable, data_origin=origin, observation=obs,
        warnings=warnings, retrieved_at_utc=now.isoformat(timespec="seconds"), max_age_minutes=max_age_minutes)


def build_forecast_block(forecast: ProviderForecast, *, now: datetime,
                         window_hours: float = DEFAULT_FORECAST_WINDOW_HOURS) -> Dict[str, Any]:
    """Summarise a provider forecast into the scheduler's format, or say why it cannot be.

    Window: the forecast steps with ``now < step_time <= now + window_hours``. The window must be COMPLETELY and
    regularly covered (window_hours / 3 consecutive 3-hour steps); otherwise the block is unavailable rather than
    a partial sum that would understate rain. ``expected_rainfall_mm`` is the sum of the steps' rain volumes (mm of
    rain over the whole window, NOT mm/h); it is never reduced by ``pop``. Steps the provider reported without a
    ``rain`` value are counted as 0 mm only when the entry was otherwise complete; their number is reported in
    ``assumed_dry_steps``. Snow is not included. Provider ``dt`` is treated as the step time; whether a step's 3 h
    volume precedes or follows ``dt`` is not pinned down in the provider docs, so the first step may include up to
    3 h of rain that has already fallen (this can only make deferral more likely, never hide forecast rain).
    """
    step_h = forecast.step_hours
    needed = window_hours / step_h
    if window_hours <= 0 or needed != int(needed):
        raise ValueError(f"window_hours must be a positive multiple of {step_h}, got {window_hours!r}")
    needed = int(needed)
    end = now + timedelta(hours=window_hours)
    steps = sorted((st for st in forecast.steps if now < st.timestamp <= end), key=lambda st: st.timestamp)
    if len(steps) != needed:
        return _forecast_unavailable(
            f"Forecast covers only {len(steps) * step_h} h of the required {window_hours:g} h window; not used.",
            "forecast_window_incomplete")
    if any(b.timestamp - a.timestamp != timedelta(hours=step_h) for a, b in zip(steps, steps[1:])):
        return _forecast_unavailable("Forecast steps inside the window are not evenly spaced; not used.",
                                     "forecast_window_irregular")
    pops = [st.pop for st in steps if st.pop is not None]
    return {
        "available": True,
        "data_kind": "forecast",
        "window_hours": float(window_hours),
        "expected_rainfall_mm": round(sum(st.rain_mm for st in steps), 2),
        "unit": "mm",
        "source": FORECAST_SOURCE,
        "step_hours": step_h,
        "steps_used": len(steps),
        "assumed_dry_steps": sum(1 for st in steps if st.assumed_dry),
        "max_pop": max(pops) if pops else None,
        "window_start_utc": now.isoformat(timespec="seconds"),
        "window_end_utc": end.isoformat(timespec="seconds"),
        "last_step_utc": steps[-1].timestamp.isoformat(timespec="seconds"),
    }


def _fetch_forecast_block(prov: WeatherProvider, field_row: Any, now: datetime, window_hours: float) -> Dict[str, Any]:
    """Fetch + summarise the forecast. Never raises; any failure yields an unavailable block with the reason."""
    try:
        ratio = window_hours / FORECAST_STEP_HOURS
        if window_hours <= 0 or ratio != int(ratio):
            return _forecast_unavailable(
                f"forecast_window_hours must be a positive multiple of {FORECAST_STEP_HOURS}, got {window_hours!r}.",
                "forecast_window_invalid")
        forecast = prov.fetch_forecast(field_row.latitude, field_row.longitude, steps=int(ratio) + 1)
        return build_forecast_block(forecast, now=now, window_hours=window_hours)
    except AppError as exc:
        return _forecast_unavailable(f"Forecast could not be retrieved: {exc.message}", exc.code)
    except Exception as exc:  # noqa: BLE001 - a forecast problem must never break the prediction workflow
        log.error("Unexpected forecast failure: %s", type(exc).__name__)
        return _forecast_unavailable(f"Unexpected error while retrieving the forecast ({type(exc).__name__}).",
                                     "forecast_unexpected_error")


# ── Public API ────────────────────────────────────────────────────────────────────────────────────

def get_field_weather(
    db: Session,
    field_id: str,
    *,
    provider: Optional[WeatherProvider] = None,
    settings: Optional[Settings] = None,
    now: Optional[datetime] = None,
    max_age_minutes: float = DEFAULT_MAX_OBSERVATION_AGE_MINUTES,
    allow_stored_fallback: bool = True,
    allow_mock: bool = False,
    include_forecast: bool = True,
    forecast_window_hours: float = DEFAULT_FORECAST_WINDOW_HOURS,
) -> FieldWeatherResult:
    """Current weather (+ forecast) for a registered field, prepared for the prediction workflow. Never raises.

    field_id   existing field id (a string such as "F001"; ints are converted).
    provider   optional WeatherProvider (tests inject one with a mocked transport); default is built from settings.
    now        naive-UTC "current time" (injectable for tests).
    allow_stored_fallback  if the live call fails, consider the latest stored (real) observation; it still has to
                           pass the staleness check and is labelled data_origin='stored_observation'.
    include_forecast       also fetch the 3-hourly forecast for the next ``forecast_window_hours`` (a multiple of 3). It is
                           only requested after a fresh, real, LIVE current observation; otherwise ``forecast`` says why not.
    """
    now = _naive_utc(now) or _utc_now()
    field_id = str(field_id)
    try:
        field_row = registry_service.get_field_or_404(db, field_id)
    except AppError as exc:
        return _unavailable(field_id, exc.code, exc.message, now, max_age_minutes)
    except Exception as exc:  # noqa: BLE001 - the prediction workflow must not crash on weather problems
        log.error("Field lookup failed for %s: %s", field_id, type(exc).__name__)
        return _unavailable(field_id, "weather_unexpected_error",
                            f"Unexpected error while looking up the field ({type(exc).__name__}).", now, max_age_minutes)

    live_error: Optional[Dict[str, Any]] = None
    try:
        prov = provider or WeatherProvider(settings or get_settings())
        record, _created, _pw = weather_service.get_weather_for_field(db, field_row, prov)
        result = assess_weather_record(record, field_id=field_id, origin=ORIGIN_LIVE, now=now,
                                       max_age_minutes=max_age_minutes, allow_mock=allow_mock)
    except AppError as exc:
        live_error = _error_dict(exc)
    except Exception as exc:  # noqa: BLE001 - message omitted on purpose: it could contain request details
        log.error("Unexpected weather failure for field %s: %s", field_id, type(exc).__name__)
        _safe_rollback(db)
        live_error = {"code": "weather_unexpected_error",
                      "message": f"Unexpected error while retrieving weather ({type(exc).__name__}).", "details": None}
    else:
        if not include_forecast:
            result.forecast = _forecast_unavailable("Forecast not requested (include_forecast=False).", "forecast_not_requested")
        elif result.status == STATUS_OK and result.data_origin == ORIGIN_LIVE:
            result.forecast = _fetch_forecast_block(prov, field_row, now, forecast_window_hours)
        else:
            result.forecast = _forecast_unavailable(
                f"Forecast not requested: current weather is not a usable live observation (status={result.status}).",
                "forecast_not_requested")
        return result

    # Live fetch failed. Optionally fall back to the latest REAL stored observation (never to made-up values).
    if allow_stored_fallback:
        try:
            rows = weather_service.list_weather(db, field_id, 1)
        except Exception as exc:  # noqa: BLE001
            log.error("Stored weather lookup failed for %s: %s", field_id, type(exc).__name__)
            _safe_rollback(db)
            rows = []
        if rows:
            result = assess_weather_record(rows[0], field_id=field_id, origin=ORIGIN_STORED, now=now,
                                           max_age_minutes=max_age_minutes, allow_mock=allow_mock)
            result.live_fetch_error = live_error
            result.forecast = _forecast_unavailable("Forecast not requested: the live weather fetch failed.",
                                                    "forecast_not_requested")
            result.warnings.insert(0, f"Live weather fetch failed ({live_error['code']}); fell back to the latest stored observation.")
            return result
    return _unavailable(field_id, live_error["code"], live_error["message"], now, max_age_minutes,
                        details=live_error.get("details"), live_fetch_error=live_error)


__all__ = ["DEFAULT_FORECAST_WINDOW_HOURS", "DEFAULT_MAX_OBSERVATION_AGE_MINUTES", "build_forecast_block", "FieldWeatherResult", "OBSERVATION_FEATURES", "STATUS_MOCK",
           "STATUS_OK", "STATUS_STALE", "STATUS_UNAVAILABLE", "WeatherNotUsableError", "WeatherObservation",
           "assess_weather_record", "get_field_weather"]