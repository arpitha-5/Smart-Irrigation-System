import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database.init_db import init_db
from app.database.session import get_engine
from app.errors import register_error_handlers
from app.routers import (
    alerts,
    assistant,
    auth,
    crops,
    data_quality,
    demo,
    farmer_dashboard,
    farmers,
    fields,
    intelligence,
    irrigation_logs,
    irrigation_schedules,
    recommendations,
    reports,
    sarvam,
    sensors,
    system,
    weather,
)
from app.services.mqtt_service import start_mqtt_background

log = logging.getLogger("irrigation")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    try:
        hypertables = init_db(get_engine())
        log.info("Database ready (TimescaleDB hypertables: %s)", hypertables)
    except Exception as exc:
        log.warning("Database startup notice: %s", exc)
    try:
        start_mqtt_background(settings)
    except Exception as exc:
        log.warning("MQTT startup notice: %s", exc)
    yield


settings = get_settings()
app = FastAPI(
    title="Smart Irrigation - Milestone 1",
    version=settings.app_version,
    lifespan=lifespan,
)
register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(farmers.router)
app.include_router(fields.router)
app.include_router(crops.router)
app.include_router(sensors.router)
app.include_router(weather.router)
app.include_router(data_quality.router)
app.include_router(demo.router)
app.include_router(recommendations.router)
app.include_router(sarvam.router)
app.include_router(irrigation_logs.router)
app.include_router(reports.router)
app.include_router(alerts.router)
app.include_router(assistant.router)
app.include_router(farmer_dashboard.router)
app.include_router(irrigation_schedules.router)
app.include_router(intelligence.router)
