from datetime import datetime, timedelta, timezone

from app.models import IrrigationSchedule
from app.models.irrigation_schedule import ScheduleStatus


def _schedule_payload(**overrides):
    payload = {
        "field_id": "F001",
        "recommended_date": "2026-10-10T06:00:00",
        "recommended_time": "06:00",
        "duration_minutes": 70,
        "water_quantity_liters": 3500,
        "reason": "Rice irrigation recommendation",
    }
    return {**payload, **overrides}


def test_identical_pending_schedule_is_rejected_but_separate_run_is_allowed(client, seeded):
    first = client.post("/irrigation/schedules", json=_schedule_payload())
    assert first.status_code == 201

    duplicate = client.post("/irrigation/schedules", json=_schedule_payload())
    assert duplicate.status_code == 409
    assert "identical pending schedule" in duplicate.json()["error"]["message"].lower()

    separate_run = client.post(
        "/irrigation/schedules",
        json=_schedule_payload(recommended_time="12:00", recommended_date="2026-10-10T12:00:00"),
    )
    assert separate_run.status_code == 201
    assert len(client.get("/irrigation/schedules", params={"field_id": "F001"}).json()) == 2


def test_completed_schedule_cannot_return_to_pending(client, seeded):
    created = client.post("/irrigation/schedules", json=_schedule_payload())
    schedule_id = created.json()["schedule_id"]
    completed = client.patch(
        f"/irrigation/schedules/{schedule_id}/status",
        json={"status": "completed"},
    )
    assert completed.status_code == 200

    patch_reopen = client.patch(
        f"/irrigation/schedules/{schedule_id}/status",
        json={"status": "pending"},
    )
    put_reopen = client.put(
        f"/irrigation/schedules/{schedule_id}",
        json={"status": "pending"},
    )
    assert patch_reopen.status_code == 409
    assert put_reopen.status_code == 409
    assert client.get("/irrigation/schedules", params={"field_id": "F001"}).json()[0]["status"] == "completed"


def test_recent_generated_duplicate_is_rejected(client, seeded, db, monkeypatch):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reason = "Current soil moisture is below the rice irrigation threshold."
    db.add(IrrigationSchedule(
        schedule_id="SCH_EXISTING",
        field_id="F001",
        recommended_date=now,
        recommended_time=now.strftime("%H:%M"),
        duration_minutes=70,
        water_quantity_liters=3500,
        reason=reason,
        status=ScheduleStatus.pending,
        created_at=now - timedelta(minutes=2),
    ))
    db.commit()
    monkeypatch.setattr(
        "app.routers.irrigation_schedules.recommend_irrigation",
        lambda **_: {
            "recommended_water_mm": 3500 / 150,
            "action": "IRRIGATE_IMMEDIATELY",
            "reason": reason,
        },
    )

    response = client.post("/irrigation/schedules/generate/F001")

    assert response.status_code == 409
    assert "last 15 minutes" in response.json()["error"]["message"]
    assert len(client.get("/irrigation/schedules", params={"field_id": "F001"}).json()) == 1
