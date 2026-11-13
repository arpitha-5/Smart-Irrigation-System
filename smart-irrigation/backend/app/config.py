"""Application settings, read from environment variables / backend/.env."""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    database_url: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    postgres_host: Optional[str] = None
    postgres_port: Optional[int] = None
    postgres_db: Optional[str] = None
    app_env: str = "development"
    app_version: str = "0.2.0"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"

    openweather_api_key: Optional[str] = None
    openweather_base_url: str = "https://api.openweathermap.org/data/2.5/weather"
    openweather_geocode_url: str = "https://api.openweathermap.org/geo/1.0/direct"
    # 5-day / 3-hour FORECAST endpoint (distinct from openweather_base_url, which is CURRENT weather).
    openweather_forecast_url: str = "https://api.openweathermap.org/data/2.5/forecast"
    weather_timeout_seconds: float = 5.0
    weather_mock: bool = False

    # Sensor timestamps further in the future than this are rejected.
    sensor_future_tolerance_seconds: int = 300

    # Trained irrigation model (scripts/train_irrigation_model.py). Disable to force the rule-based engine only.
    irrigation_ml_enabled: bool = True
    irrigation_models_dir: Optional[str] = None   # default: <backend>/models
    # Local time zone offset for irrigation windows (India = 5.5). The field's real time zone is not stored.
    irrigation_utc_offset_hours: float = 5.5

    mqtt_enabled: bool = False
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "irrigation/sensors/#"
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_client_id: str = "smart-irrigation-backend"

    # Sarvam AI API for Indic Language Dynamic Translation, TTS and STT
    sarvam_api_key: Optional[str] = None
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_translate_model: str = "sarvam-translate:v1"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_stt_model: str = "saaras:v2"

    # Authentication & JWT
    jwt_secret_key: str = "agripulse-secret-jwt-key-2026-production-ready"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 10080  # 7 days

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    @field_validator("openweather_api_key", "mqtt_username", "mqtt_password", "sarvam_api_key", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @model_validator(mode="after")
    def _resolve_database_url(self):
        if not self.database_url:
            user = self.postgres_user or "irrigation"
            password = self.postgres_password or "irrigation"
            host = self.postgres_host or "localhost"
            port = self.postgres_port or 5433
            db = self.postgres_db or "irrigation"
            self.database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
        return self

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def weather_configured(self) -> bool:
        return bool(self.openweather_api_key)

    @property
    def sarvam_configured(self) -> bool:
        return bool(self.sarvam_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()