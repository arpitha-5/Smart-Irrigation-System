from datetime import datetime, timedelta

from app.models import Farmer, Field, IrrigationSchedule, SensorReading, User
from app.routers.auth import get_current_user
from app.models.irrigation_schedule import ScheduleStatus


def test_auth_me_returns_linked_farmer_id_and_creates_legacy_profile(client, db):
    user = User(full_name="Legacy Farmer", email="legacy@example.test", hashed_password="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    client.app.dependency_overrides[get_current_user] = lambda: user.id

    response = client.get("/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["farmer_id"]
    assert payload["farmer_profiles"] == [{
        "farmer_id": payload["farmer_id"],
        "name": "Legacy Farmer",
        "email": user.email,
        "phone": None,
    }]
    assert db.get(Farmer, payload["farmer_id"]).email == user.email


def test_dashboard_does_not_infer_irrigation_or_water_without_records(client, db):
    user = User(full_name="Farmer One", email="farmer@example.test", hashed_password="unused")
    farmer = Farmer(farmer_id="FR001", name=user.full_name, email=user.email)
    db.add_all([user, farmer])
    db.flush()
    db.add(Field(
        field_id="F001",
        farmer_id=farmer.farmer_id,
        name="North Field",
        crop_type="Rice",
        area_hectares=1,
    ))
    db.commit()
    db.refresh(user)
    client.app.dependency_overrides[get_current_user] = lambda: user.id

    response = client.get("/farmers/me/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_fields"] == 1
    assert payload["fields_needing_irrigation"] == 0
    assert payload["field_conditions"] == [{
        "field_id": "F001",
        "action": "NO_SENSOR_DATA",
        "urgency": "NONE",
        "reason": "No soil-moisture sensor reading is available for this field.",
        "soil_moisture": None,
        "sensor_timestamp": None,
        "is_simulated": False,
    }]
    assert payload["average_soil_moisture"] is None
    assert payload["total_water_used_liters"] is None
    assert payload["water_analytics"]["daily_consumption_liters"] is None
    assert payload["water_analytics"]["efficiency_score"] is None
    assert payload["weather_summary"] is None


def test_dashboard_uses_only_soil_moisture_telemetry_for_irrigation_status(client, seeded, db):
    farmer = db.get(Farmer, "FR001")
    user = User(full_name=farmer.name, email="telemetry@example.test", hashed_password="unused")
    farmer.email = user.email
    db.add(user)
    db.add_all([
        SensorReading(
            sensor_id="SM001",
            field_id="F001",
            timestamp=datetime(2026, 10, 7, 10, 0),
            measurement_type="soil_moisture",
            soil_moisture=30,
            value=30,
            is_simulated=False,
        ),
        SensorReading(
            sensor_id="SM001",
            field_id="F001",
            timestamp=datetime(2026, 10, 7, 11, 0),
            measurement_type="humidity",
            soil_moisture=None,
            value=65,
            is_simulated=False,
        ),
        SensorReading(
            sensor_id="SM001",
            field_id="F001",
            timestamp=datetime(2026, 10, 7, 12, 0),
            measurement_type="soil_moisture",
            soil_moisture=5,
            value=5,
            is_simulated=True,
        ),
    ])
    db.commit()
    db.refresh(user)
    client.app.dependency_overrides[get_current_user] = lambda: user.id

    response = client.get("/farmers/me/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["field_conditions"][0]["soil_moisture"] == 30
    assert payload["field_conditions"][0]["sensor_timestamp"] == "2026-10-07T10:00:00"
    assert payload["field_conditions"][0]["is_simulated"] is False
    assert payload["average_soil_moisture"] == 30


def test_dashboard_deduplicates_exact_completed_schedules_and_labels_volume_as_estimate(client, db):
    user = User(full_name="Schedule Farmer", email="schedule@example.test", hashed_password="unused")
    farmer = Farmer(farmer_id="FR010", name=user.full_name, email=user.email)
    db.add_all([user, farmer])
    db.flush()
    db.add(Field(
        field_id="F010",
        farmer_id=farmer.farmer_id,
        name="East Paddy",
        crop_type="Rice",
        area_hectares=1,
    ))
    db.flush()
    now = datetime.utcnow()
    first_date = now - timedelta(hours=1)
    for schedule_id, scheduled_date, scheduled_time in (
        ("SCH_DUP1", first_date, "06:00"),
        ("SCH_DUP2", first_date, "06:00"),
        ("SCH_SEPARATE", first_date + timedelta(hours=2), "08:00"),
    ):
        db.add(IrrigationSchedule(
            schedule_id=schedule_id,
            field_id="F010",
            recommended_date=scheduled_date,
            recommended_time=scheduled_time,
            duration_minutes=70,
            water_quantity_liters=3500,
            reason="Rice irrigation",
            status=ScheduleStatus.completed,
        ))
    db.commit()
    db.refresh(user)
    client.app.dependency_overrides[get_current_user] = lambda: user.id

    response = client.get("/farmers/me/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_water_used_liters"] is None
    assert payload["completed_schedule_volume_estimate_liters"] == 7000
    analytics = payload["water_analytics"]
    assert analytics["volume_basis"] == "completed_schedule_estimates"
    assert analytics["daily_schedule_volume_estimate_liters"] == 7000
    assert analytics["daily_consumption_liters"] is None
    comparison = analytics["baseline_comparison"]
    assert comparison["actual_liters"] is None
    assert comparison["completed_schedule_volume_estimate_liters"] == 7000
    assert comparison["traditional_flood_liters"] == 1_000_000
    assert comparison["water_saved_liters"] == 993_000
    assert comparison["is_estimated"] is True
    assert analytics["field_breakdown"][0]["completed_schedule_volume_estimate_liters"] == 7000
