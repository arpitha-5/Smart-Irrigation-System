from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers every table)
from app.database.base import Base
from app.models.alert import Alert
from app.models.farmer import Farmer
from app.models.field import Field
from app.models.field_threshold import FieldThreshold
from app.models.sensor import Sensor
from app.models.sensor_reading import SensorReading
from app.services import alert_runner

NOW = datetime(2026, 11, 20, 12, 0, 0)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    session.add(Farmer(farmer_id="FM1", name="Test Farmer"))
    session.add(Field(field_id="FLD1", farmer_id="FM1", name="Field A", crop_type="Rice"))
    session.add(Sensor(sensor_id="S1", field_id="FLD1"))
    session.commit()
    yield session
    session.close()


def make_reading(db, moisture, mtype="soil_moisture", flags=None, minute=0):
    reading = SensorReading(
        sensor_id="S1", field_id="FLD1", timestamp=NOW + timedelta(minutes=minute),
        soil_moisture=moisture, measurement_type=mtype, quality_flags=flags,
    )
    db.add(reading)
    db.commit()
    return reading


def set_sensor(db, **changes):
    sensor = db.get(Sensor, "S1")
    for key, value in changes.items():
        setattr(sensor, key, value)
    db.commit()


def alerts(db):
    return list(db.scalars(select(Alert)))


def test_dry_reading_creates_a_drought_alert(db):
    changes = alert_runner.process_reading(db, make_reading(db, 20), now=NOW)
    assert [c.kind for c in changes] == ["new"]
    stored = alerts(db)
    assert stored[0].alert_type == "drought" and stored[0].severity == "CRITICAL"


def test_wet_reading_creates_an_over_watering_alert(db):
    alert_runner.process_reading(db, make_reading(db, 85), now=NOW)
    assert alerts(db)[0].alert_type == "over_watering"


def test_each_fields_own_limits_are_respected(db):
    db.add(FieldThreshold(field_id="FLD1", min_moisture=25, max_moisture=65))
    db.commit()
    assert alert_runner.process_reading(db, make_reading(db, 28), now=NOW) == []
    assert alerts(db) == []


def test_repeated_dry_readings_do_not_duplicate(db):
    alert_runner.process_reading(db, make_reading(db, 25, minute=0), now=NOW)
    changes = alert_runner.process_reading(db, make_reading(db, 24, minute=10), now=NOW + timedelta(minutes=10))
    assert [c.kind for c in changes] == ["repeat"]
    assert len(alerts(db)) == 1


def test_recovery_resolves_the_alert(db):
    alert_runner.process_reading(db, make_reading(db, 20), now=NOW)
    changes = alert_runner.process_reading(db, make_reading(db, 50, minute=10), now=NOW + timedelta(minutes=10))
    assert [c.kind for c in changes] == ["resolved"]
    assert alerts(db)[0].status == "resolved"


def test_temperature_reading_does_not_clear_a_drought_alert(db):
    alert_runner.process_reading(db, make_reading(db, 20), now=NOW)
    temperature = make_reading(db, None, mtype="temperature", minute=10)
    alert_runner.process_reading(db, temperature, now=NOW + timedelta(minutes=10))
    assert alerts(db)[0].status == "open"


def test_out_of_order_reading_is_ignored(db):
    old = make_reading(db, 20, flags="out_of_order")
    assert alert_runner.process_reading(db, old, now=NOW) == []
    assert alerts(db) == []


def test_silent_sensor_gets_a_failure_alert(db):
    set_sensor(db, last_seen_at=NOW - timedelta(hours=3))
    changes = alert_runner.check_silent_sensors(db, now=NOW)
    assert [c.kind for c in changes] == ["new"]
    assert alerts(db)[0].alert_type == "sensor_failure"


def test_silence_check_does_not_duplicate(db):
    set_sensor(db, last_seen_at=NOW - timedelta(hours=3))
    alert_runner.check_silent_sensors(db, now=NOW)
    changes = alert_runner.check_silent_sensors(db, now=NOW + timedelta(minutes=15))
    assert [c.kind for c in changes] == ["repeat"]
    assert len(alerts(db)) == 1


def test_sensor_recovers_when_data_arrives(db):
    set_sensor(db, last_seen_at=NOW - timedelta(hours=3))
    alert_runner.check_silent_sensors(db, now=NOW)
    changes = alert_runner.process_reading(db, make_reading(db, 50, minute=5), now=NOW + timedelta(minutes=5))
    assert [c.kind for c in changes] == ["resolved"]
    assert alerts(db)[0].status == "resolved"


def test_new_sensor_gets_time_before_a_failure_alert(db):
    set_sensor(db, last_seen_at=None, created_at=NOW - timedelta(minutes=10))
    assert alert_runner.check_silent_sensors(db, now=NOW) == []


def test_sensor_that_never_reports_is_flagged_after_the_grace_period(db):
    set_sensor(db, last_seen_at=None, created_at=NOW - timedelta(hours=2))
    changes = alert_runner.check_silent_sensors(db, now=NOW)
    assert [c.kind for c in changes] == ["new"]


def test_inactive_sensor_is_ignored(db):
    set_sensor(db, last_seen_at=NOW - timedelta(hours=3), status="inactive")
    assert alert_runner.check_silent_sensors(db, now=NOW) == []


def test_ingestion_creates_the_alert(db):
    from app.config import get_settings
    from app.schemas.sensor_reading import SensorReadingIn
    from app.services import sensor_service

    payload = SensorReadingIn(sensor_id="S1", soil_moisture=20.0)
    sensor_service.ingest_reading(db, payload, get_settings())
    stored = alerts(db)
    assert len(stored) == 1 and stored[0].alert_type == "drought"


def test_alert_check_failure_never_breaks_ingestion(db, monkeypatch):
    from app.config import get_settings
    from app.schemas.sensor_reading import SensorReadingIn
    from app.services import sensor_service

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(alert_runner, "process_reading", boom)
    payload = SensorReadingIn(sensor_id="S1", soil_moisture=20.0)
    reading, _ = sensor_service.ingest_reading(db, payload, get_settings())
    assert reading.reading_id is not None
