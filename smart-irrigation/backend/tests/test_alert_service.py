from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers every table, including the new ones)
from app.database.base import Base
from app.models.alert import Alert
from app.models.farmer import Farmer
from app.models.field import Field
from app.models.field_threshold import FieldThreshold
from app.models.sensor import Sensor
from app.services import alert_service
from app.services.rule_engine import AlertType, RuleAlert, Severity

NOW = datetime(2026, 11, 20, 12, 0, 0)
ALL_TYPES = {AlertType.DROUGHT, AlertType.OVER_WATERING, AlertType.SENSOR_FAILURE}


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


def drought(severity=Severity.MEDIUM):
    return RuleAlert(AlertType.DROUGHT, severity, "Soil is dry.", "Irrigate soon.", value=25.0, threshold=30.0)


def sensor_failure(severity=Severity.MEDIUM):
    return RuleAlert(AlertType.SENSOR_FAILURE, severity, "Sensor problem.", "Check the sensor.")


def sync(db, found, now=NOW, managed=ALL_TYPES):
    return alert_service.sync_alerts(db, "FLD1", "S1", found, now, managed)


def all_alerts(db):
    return list(db.scalars(select(Alert)))


def test_default_thresholds_when_none_saved(db):
    t = alert_service.get_thresholds(db, "FLD1")
    assert (t.min_moisture, t.max_moisture) == (30.0, 70.0)


def test_saved_thresholds_are_used(db):
    db.add(FieldThreshold(field_id="FLD1", min_moisture=25, max_moisture=65))
    db.commit()
    t = alert_service.get_thresholds(db, "FLD1")
    assert (t.min_moisture, t.max_moisture) == (25, 65)
    assert t.critical_margin == 10.0 and t.sensor_silent_minutes == 60


def test_new_alert_is_created(db):
    changes = sync(db, [drought()])
    assert [c.kind for c in changes] == ["new"]
    stored = all_alerts(db)
    assert len(stored) == 1 and stored[0].status == "open" and stored[0].alert_type == "drought"


def test_same_condition_does_not_create_a_duplicate(db):
    sync(db, [drought()])
    changes = sync(db, [drought()], now=NOW + timedelta(minutes=5))
    assert [c.kind for c in changes] == ["repeat"]
    stored = all_alerts(db)
    assert len(stored) == 1 and stored[0].occurrence_count == 2


def test_getting_worse_is_reported_as_escalation(db):
    sync(db, [drought(Severity.MEDIUM)])
    changes = sync(db, [drought(Severity.CRITICAL)])
    assert [c.kind for c in changes] == ["escalated"]
    assert all_alerts(db)[0].severity == "CRITICAL"


def test_alert_resolves_when_condition_clears(db):
    sync(db, [drought()])
    changes = sync(db, [], now=NOW + timedelta(hours=1))
    assert [c.kind for c in changes] == ["resolved"]
    stored = all_alerts(db)[0]
    assert stored.status == "resolved" and stored.resolved_at is not None


def test_problem_coming_back_creates_a_new_alert(db):
    sync(db, [drought()])
    sync(db, [])
    sync(db, [drought()])
    stored = all_alerts(db)
    assert len(stored) == 2
    assert sorted(a.status for a in stored) == ["open", "resolved"]


def test_acknowledged_alert_is_not_duplicated(db):
    sync(db, [drought()])
    alert = all_alerts(db)[0]
    alert.status = "acknowledged"
    db.commit()
    changes = sync(db, [drought()])
    assert [c.kind for c in changes] == ["repeat"]
    assert len(all_alerts(db)) == 1


def test_types_not_managed_by_a_check_are_left_alone(db):
    sync(db, [drought()])
    sync(db, [], managed={AlertType.SENSOR_FAILURE})   # e.g. the "sensor went silent" check
    assert all_alerts(db)[0].status == "open"


def test_two_alerts_of_the_same_type_are_merged(db):
    changes = sync(db, [sensor_failure(Severity.MEDIUM), sensor_failure(Severity.HIGH)])
    assert [c.kind for c in changes] == ["new"]
    stored = all_alerts(db)
    assert len(stored) == 1 and stored[0].severity == "HIGH"


def test_database_refuses_two_active_alerts_of_the_same_type(db):
    for _ in range(2):
        db.add(Alert(field_id="FLD1", sensor_id="S1", alert_type="drought",
                     severity="HIGH", status="open", message="x"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_database_refuses_invalid_thresholds(db):
    db.add(FieldThreshold(field_id="FLD1", min_moisture=70, max_moisture=30))
    with pytest.raises(IntegrityError):
        db.commit()
