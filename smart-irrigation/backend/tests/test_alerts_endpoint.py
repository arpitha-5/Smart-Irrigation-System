import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.models.alert import Alert
from app.models.farmer import Farmer
from app.models.field import Field
from app.models.sensor import Sensor


def test_alerts_endpoint_empty(client: TestClient):
    res = client.get("/alerts")
    assert res.status_code == 200
    assert res.json() == []


def test_alerts_crud_and_status_transitions(client: TestClient, db):
    # Setup test farmer, field, sensor, and alert
    farmer = Farmer(farmer_id="FMR101", name="Ramesh Kumar", phone="+919876543210")
    field = Field(field_id="FLD101", farmer_id="FMR101", name="North Field", crop_type="Rice")
    sensor = Sensor(sensor_id="SNS101", field_id="FLD101")
    db.add_all([farmer, field, sensor])
    db.commit()

    alert = Alert(
        field_id="FLD101",
        sensor_id="SNS101",
        alert_type="drought",
        severity="CRITICAL",
        status="open",
        message="Soil moisture has dropped critically low (18%).",
        recommended_action="Irrigate immediately.",
        value=18.0,
        threshold=25.0,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    alert_id = alert.alert_id

    # 1. Test List Alerts
    res = client.get("/alerts")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["alert_id"] == alert_id
    assert data[0]["severity"] == "CRITICAL"
    assert data[0]["status"] == "open"

    # 2. Test Filters
    res_filtered = client.get("/alerts?field_id=FLD101&severity=CRITICAL")
    assert res_filtered.status_code == 200
    assert len(res_filtered.json()) == 1

    res_no_match = client.get("/alerts?field_id=FLD999")
    assert res_no_match.status_code == 200
    assert len(res_no_match.json()) == 0

    # 3. Test Get Alert Detail
    res_get = client.get(f"/alerts/{alert_id}")
    assert res_get.status_code == 200
    assert res_get.json()["alert_id"] == alert_id

    # 4. Test Acknowledge Alert
    res_ack = client.patch(f"/alerts/{alert_id}/acknowledge")
    assert res_ack.status_code == 200
    ack_data = res_ack.json()
    assert ack_data["status"] == "acknowledged"
    assert ack_data["acknowledged_at"] is not None

    # 5. Test Resolve Alert
    res_res = client.patch(f"/alerts/{alert_id}/resolve")
    assert res_res.status_code == 200
    res_data = res_res.json()
    assert res_data["status"] == "resolved"
    assert res_data["resolved_at"] is not None

    # 6. Cannot acknowledge an already resolved alert
    res_ack_again = client.patch(f"/alerts/{alert_id}/acknowledge")
    assert res_ack_again.status_code == 400


def test_alerts_notify_endpoint(client: TestClient):
    payload = {
        "channel": "WHATSAPP",
        "recipient": "+918074599664",
        "title": "AgriPulse Crop Advisory",
        "message": "Immediate irrigation advised for Rice plot.",
    }
    res = client.post("/alerts/notify", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("success", "warning")
    assert data["channel"] == "WHATSAPP"
    assert data["recipient"] == "+918074599664"
