"""Weather integration (OpenWeatherMap current-weather API and 5-day/3-hour forecast API).

Layers kept separate:
  WeatherProvider  - the only code that talks to the external API; returns normalised values or raises AppError
  store_weather    - persistence
  get_weather_for_field - orchestration used by the router

Current observations and forecasts are different data: fetch_current() -> ProviderWeather (stored, observed),
fetch_forecast() -> ProviderForecast (never stored here, predicted). They are never mixed.

Nothing is ever made up: on any failure an AppError is raised and nothing is stored.
The API key is read from settings (env var) and is never logged or returned.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models import Field, WeatherData
from app.services.data_cleaning_service import DataValidationError, clean_weather


@dataclass
class ProviderWeather:
    timestamp: datetime  # naive UTC observation time
    temperature: float
    humidity: float
    rainfall: float
    # Display-only extras (not stored, not part of the Week-1 contract)
    description: Optional[str] = None
    feels_like: Optional[float] = None
    wind_speed: Optional[float] = None  # m/s
    provider_latitude: Optional[float] = None
    provider_longitude: Optional[float] = None
    provider_city: Optional[str] = None
    provider_country: Optional[str] = None


FORECAST_STEP_HOURS = 3
# Same plausibility ceiling clean_weather() applies to rainfall (mm). Larger values are treated as invalid data.
FORECAST_MAX_STEP_RAIN_MM = 500.0


@dataclass
class ForecastStep:
    """One 3-hour step of the OpenWeatherMap 5-day forecast (``list[]`` entry)."""
    timestamp: datetime            # naive UTC, the provider's ``dt`` for this step
    rain_mm: float                 # rain volume of the step in mm (provider ``rain.3h``)
    pop: Optional[float] = None    # probability of precipitation, 0..1 (provider ``pop``)
    assumed_dry: bool = False      # True only when the provider omitted ``rain`` (see _parse_forecast_step)


@dataclass
class ProviderForecast:
    steps: List[ForecastStep]      # ascending by timestamp, unique timestamps
    step_hours: int = FORECAST_STEP_HOURS


def _finite_number(v) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if f == f and f not in (float("inf"), float("-inf")) else None


class WeatherProvider:
    def __init__(self, settings: Settings, transport: Optional[httpx.BaseTransport] = None):
        self._settings = settings
        self._transport = transport  # injected by automated tests only
        self.last_payload: Optional[dict] = None  # raw provider JSON of the latest call (for --debug; never contains the key)
        self.last_forecast_payload: Optional[dict] = None  # same, for the latest forecast call

    def _request(self, url: str, latitude: float, longitude: float, extra_params: Optional[dict] = None) -> httpx.Response:
        """Validated GET to an OpenWeatherMap endpoint. Shared by current weather and forecast so the key,
        timeout, error mapping and "never log the key" rules are identical. Raises AppError on any failure."""
        if latitude is None or longitude is None:
            raise AppError(422, "coordinates_missing", "Latitude and longitude must both be provided.")
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            raise AppError(422, "coordinates_invalid",
                           f"Coordinates ({latitude}, {longitude}) are invalid. Latitude must be in [-90, 90] and longitude in [-180, 180].")
        s = self._settings
        if not s.openweather_api_key:
            raise AppError(503, "weather_not_configured",
                           "OPENWEATHER_API_KEY is not set; weather cannot be fetched.")
        params = {"lat": latitude, "lon": longitude, "units": "metric", "appid": s.openweather_api_key}
        if extra_params:
            params.update(extra_params)
        try:
            with httpx.Client(timeout=s.weather_timeout_seconds, transport=self._transport) as client:
                resp = client.get(url, params=params)
        except httpx.TimeoutException:
            raise AppError(503, "weather_timeout", "Weather provider did not respond in time. Try again later.")
        except httpx.RequestError as exc:  # message intentionally omitted: it can contain the request URL (and key)
            raise AppError(503, "weather_unavailable", f"Weather provider unreachable ({type(exc).__name__}).")

        if resp.status_code in (401, 403):
            raise AppError(502, "weather_auth_failed",
                           f"Weather provider refused the request (HTTP {resp.status_code}). "
                           "Check OPENWEATHER_API_KEY (new keys can take a while to activate) and that the host is not blocked by a firewall/proxy.")
        if resp.status_code == 429:
            raise AppError(503, "weather_rate_limited", "Weather provider rate limit reached. Try again later.")
        if resp.status_code >= 400:
            raise AppError(502, "weather_provider_error", f"Weather provider returned HTTP {resp.status_code}.")
        return resp

    def fetch_current(self, latitude: float, longitude: float) -> ProviderWeather:
        resp = self._request(self._settings.openweather_base_url, latitude, longitude)
        try:
            self.last_payload = resp.json()
        except ValueError:
            self.last_payload = None
        return self.parse(resp)

    def fetch_forecast(self, latitude: float, longitude: float, steps: int = 9) -> ProviderForecast:
        """5-day / 3-hour FORECAST (``/data/2.5/forecast``). ``steps`` limits the number of 3-hour entries requested
        (provider ``cnt``); 9 entries = 27 h, enough to cover a 24 h window whatever the phase of the 3-hour grid."""
        resp = self._request(self._settings.openweather_forecast_url, latitude, longitude, {"cnt": int(steps)})
        try:
            self.last_forecast_payload = resp.json()
        except ValueError:
            self.last_forecast_payload = None
        return self.parse_forecast(resp)

    @staticmethod
    def parse(resp: httpx.Response) -> ProviderWeather:
        try:
            data = resp.json()
        except ValueError:
            raise AppError(502, "weather_bad_response", "Weather provider returned invalid JSON.")
        if not isinstance(data, dict):
            raise AppError(502, "weather_bad_response", "Weather provider returned an unexpected payload.")

        main = data.get("main") if isinstance(data.get("main"), dict) else {}
        temperature, humidity, dt = main.get("temp"), main.get("humidity"), data.get("dt")
        missing: List[str] = [n for n, v in (("temperature", temperature), ("humidity", humidity), ("timestamp", dt)) if v is None]

        # OpenWeatherMap omits the "rain" object when there is no precipitation, so absence = 0 mm.
        # If it is present, "1h" (mm in last hour) is used; a lone "3h" is averaged to mm/h.
        rain = data.get("rain")
        if rain is None:
            rainfall = 0.0
        elif isinstance(rain, dict) and rain.get("1h") is not None:
            rainfall = rain["1h"]
        elif isinstance(rain, dict) and rain.get("3h") is not None:
            try:
                rainfall = float(rain["3h"]) / 3
            except (TypeError, ValueError):
                rainfall = None
        else:
            rainfall = None
        if rainfall is None:
            missing.append("rainfall")

        if missing:
            raise AppError(502, "weather_incomplete_data", "Weather provider response is missing required values.",
                           [{"field": m, "code": "missing_value"} for m in missing])
        try:
            cleaned = clean_weather(temperature, humidity, rainfall)
            observed = datetime.fromtimestamp(float(dt), tz=timezone.utc).replace(tzinfo=None)
        except DataValidationError as exc:
            raise AppError(502, "weather_invalid_data", "Weather provider returned implausible values; discarded.",
                           [i.as_dict() for i in exc.issues])
        except (TypeError, ValueError, OverflowError, OSError):
            raise AppError(502, "weather_invalid_data", "Weather provider returned an invalid observation time.")
        weather_list = data.get("weather")
        description = weather_list[0].get("description") if isinstance(weather_list, list) and weather_list and isinstance(weather_list[0], dict) else None
        wind = data.get("wind") if isinstance(data.get("wind"), dict) else {}
        coord = data.get("coord") if isinstance(data.get("coord"), dict) else {}
        sys_dict = data.get("sys") if isinstance(data.get("sys"), dict) else {}

        def _num(v):
            return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        return ProviderWeather(
            observed, cleaned.temperature, cleaned.humidity, cleaned.rainfall,
            description=description, feels_like=_num(main.get("feels_like")), wind_speed=_num(wind.get("speed")),
            provider_latitude=_num(coord.get("lat")),
            provider_longitude=_num(coord.get("lon")),
            provider_city=str(data["name"]) if data.get("name") else None,
            provider_country=str(sys_dict["country"]) if sys_dict.get("country") else None,
        )


    @staticmethod
    def parse_forecast(resp: httpx.Response) -> ProviderForecast:
        """Parse a 5-day/3-hour forecast response. Any invalid step discards the whole forecast: nothing is skipped,
        interpolated or defaulted. Error codes: forecast_bad_response, forecast_incomplete_data, forecast_invalid_data."""
        try:
            data = resp.json()
        except ValueError:
            raise AppError(502, "forecast_bad_response", "Forecast provider returned invalid JSON.")
        if not isinstance(data, dict) or not isinstance(data.get("list"), list):
            raise AppError(502, "forecast_bad_response",
                           "Forecast response has no 'list' of forecast steps (check OPENWEATHER_FORECAST_URL).")
        if not data["list"]:
            raise AppError(502, "forecast_incomplete_data", "Forecast response contains no steps.")
        steps: List[ForecastStep] = []
        issues: List[dict] = []
        for i, item in enumerate(data["list"]):
            step, problems = _parse_forecast_step(item)
            if step is not None:
                steps.append(step)
            issues.extend({"index": i, "field": f, "code": c} for f, c in problems)
        if issues:
            code = "forecast_incomplete_data" if all(x["code"] == "missing_value" for x in issues) else "forecast_invalid_data"
            raise AppError(502, code, "Forecast response has missing or invalid values; discarded.", issues[:10])
        steps.sort(key=lambda st: st.timestamp)
        if len({st.timestamp for st in steps}) != len(steps):
            raise AppError(502, "forecast_invalid_data", "Forecast response contains duplicate step times; discarded.")
        return ProviderForecast(steps)


def _parse_forecast_step(item) -> Tuple[Optional[ForecastStep], List[Tuple[str, str]]]:
    """Validate one forecast entry. Returns (step, []) or (None, [(field, problem_code), ...]).

    Precipitation rules (OpenWeatherMap 5-day forecast, metric units):
      * ``rain.3h`` = rain volume of the 3-hour step in mm. ``snow`` is ignored (not rainfall).
      * The provider OMITS ``rain`` when no rain is expected. An omitted ``rain`` is accepted as a dry step ONLY if the
        entry carries a valid ``pop`` (so it is a complete entry, not a truncated one); it is then flagged
        ``assumed_dry`` so callers can see it. Without a valid ``pop`` the entry is invalid.
      * ``rain`` present but without a usable numeric ``3h`` (null, wrong type, negative, NaN, > ceiling) is invalid.
    """
    if not isinstance(item, dict):
        return None, [("step", "invalid_value")]
    problems: List[Tuple[str, str]] = []

    ts: Optional[datetime] = None
    dt = item.get("dt")
    if dt is None:
        problems.append(("timestamp", "missing_value"))
    else:
        f = _finite_number(dt)
        try:
            if f is None:
                raise ValueError
            ts = datetime.fromtimestamp(f, tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OverflowError, OSError):
            problems.append(("timestamp", "invalid_value"))

    pop: Optional[float] = None
    pop_ok = False
    if item.get("pop") is not None:
        pop = _finite_number(item["pop"])
        if pop is None or not (0.0 <= pop <= 1.0):
            problems.append(("pop", "invalid_value"))
            pop = None
        else:
            pop_ok = True

    rain_mm: Optional[float] = None
    assumed_dry = False
    if "rain" not in item:
        if pop_ok:
            rain_mm, assumed_dry = 0.0, True
        else:
            problems.append(("rainfall", "missing_value"))
    else:
        rain = item["rain"]
        if not isinstance(rain, dict) or rain.get("3h") is None:
            problems.append(("rainfall", "missing_value"))
        else:
            rain_mm = _finite_number(rain["3h"])
            if rain_mm is None or not (0.0 <= rain_mm <= FORECAST_MAX_STEP_RAIN_MM):
                problems.append(("rainfall", "invalid_value"))
                rain_mm = None

    if problems:
        return None, problems
    return ForecastStep(ts, rain_mm, pop, assumed_dry), []


def store_weather(db: Session, field_id: str, w: ProviderWeather, source: str = "openweathermap", is_mock: bool = False) -> Tuple[WeatherData, bool]:
    """Insert; if we already hold this (field, observation time) return the existing row and update fetched_at."""
    # First, check if this observation already exists to avoid unnecessary IntegrityError rollbacks
    existing = db.scalar(
        select(WeatherData).where(WeatherData.field_id == field_id, WeatherData.timestamp == w.timestamp)
    )
    if existing is not None:
        existing.fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return existing, False

    record = WeatherData(
        field_id=field_id, timestamp=w.timestamp, temperature=w.temperature,
        humidity=w.humidity, rainfall=w.rainfall, source=source, is_mock=is_mock,
        wind_speed=w.wind_speed, condition=w.description,
    )
    db.add(record)
    try:
        db.commit()
        return record, True
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(WeatherData).where(WeatherData.field_id == field_id, WeatherData.timestamp == w.timestamp))
        if existing is None:
            raise
        existing.fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return existing, False


def mock_observation(field: Field) -> ProviderWeather:
    """Clearly labelled synthetic weather for UI/demo only. Never presented as live API data."""
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    return ProviderWeather(
        timestamp=now,
        temperature=28.0,
        humidity=62.0,
        rainfall=0.0,
        description="simulated clear sky (mock)",
        feels_like=29.0,
        wind_speed=2.5,
    )


def get_weather_for_field(db: Session, field: Field, provider: WeatherProvider) -> Tuple[WeatherData, bool, ProviderWeather]:
    if field.latitude is None or field.longitude is None:
        raise AppError(422, "field_location_missing",
                       f"Field '{field.field_id}' has no latitude/longitude configured; weather cannot be requested.")
    if not (-90.0 <= field.latitude <= 90.0 and -180.0 <= field.longitude <= 180.0):
        raise AppError(422, "field_coordinates_invalid",
                       f"Field '{field.field_id}' has invalid coordinates ({field.latitude}, {field.longitude}). Latitude must be in [-90, 90] and longitude in [-180, 180].")
    if provider._settings.weather_mock:
        pw = mock_observation(field)
        rec, created = store_weather(db, field.field_id, pw, source="mock", is_mock=True)
        return rec, created, pw
    pw = provider.fetch_current(field.latitude, field.longitude)
    rec, created = store_weather(db, field.field_id, pw)
    return rec, created, pw


def list_all_weather(db: Session, field_id: Optional[str], limit: int) -> List[WeatherData]:
    stmt = select(WeatherData).order_by(WeatherData.timestamp.desc()).limit(limit)
    if field_id:
        stmt = stmt.where(WeatherData.field_id == field_id)
    return list(db.scalars(stmt))


def list_weather(db: Session, field_id: str, limit: int) -> List[WeatherData]:
    stmt = select(WeatherData).where(WeatherData.field_id == field_id).order_by(WeatherData.timestamp.desc()).limit(limit)
    return list(db.scalars(stmt))