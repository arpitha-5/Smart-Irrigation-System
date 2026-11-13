"""Comprehensive tests for Irrigation Scheduling and Multilingual PDF/CSV Report Generation.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.irrigation_service import _calculate_irrigation_duration, _determine_recommended_window
from tests.test_irrigation_schedule_integration import CURRENT_OK, forecast_payload, routed, weather  # noqa: F401


def test_calculate_irrigation_duration_with_flow_rate():
    # depth = 25 mm, area = 2.0 ha -> volume = 25 * 2.0 * 10,000 = 500,000 litres
    # flow_rate = 500 LPM -> duration = 500,000 / 500 = 1,000 minutes
    vol, dur, dur_fmt, status = _calculate_irrigation_duration(25.0, 2.0, 500.0)
    assert vol == 500000.0
    assert dur == 1000.0
    assert "16 hr 40 min" == dur_fmt
    assert status == "configured"


def test_calculate_irrigation_duration_missing_flow_rate():
    vol, dur, dur_fmt, status = _calculate_irrigation_duration(20.0, 1.5, None)
    assert vol == 300000.0
    assert dur is None
    assert dur_fmt == "Flow rate not configured"
    assert status == "not_configured"


def test_calculate_irrigation_duration_missing_area():
    vol, dur, dur_fmt, status = _calculate_irrigation_duration(20.0, None, 250.0)
    assert vol is None
    assert dur is None
    assert dur_fmt == "Field area not configured"
    assert status == "configured"


def test_calculate_irrigation_duration_zero_water():
    vol, dur, dur_fmt, status = _calculate_irrigation_duration(0.0, 1.5, 250.0)
    assert vol == 0.0
    assert dur == 0.0
    assert dur_fmt == "0 min"


def test_determine_recommended_window_emergency():
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    rec_date, window, start_t, end_t, reason = _determine_recommended_window(
        action="IRRIGATE_IMMEDIATELY",
        depth_mm=30.0,
        is_emergency=True,
        now_local=now,
        duration_min=90.0,
        weather=None,
    )
    assert "Immediate" in window
    assert "EMERGENCY" in reason


def test_determine_recommended_window_morning_afternoon():
    # Morning hour (07:00)
    now_morning = datetime(2026, 10, 10, 7, 0, tzinfo=timezone.utc)
    rec_date, window, start_t, end_t, reason = _determine_recommended_window(
        action="IRRIGATE",
        depth_mm=25.0,
        is_emergency=False,
        now_local=now_morning,
        duration_min=60.0,
        weather=None,
    )
    assert "Morning" in window
    assert "evaporation" in reason

    # Midday hour (13:00) -> evening recommended
    now_noon = datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc)
    rec_date, window, start_t, end_t, reason = _determine_recommended_window(
        action="IRRIGATE",
        depth_mm=25.0,
        is_emergency=False,
        now_local=now_noon,
        duration_min=60.0,
        weather=None,
    )
    assert "Evening" in window


def test_irrigation_logs_api_crud(client, seeded):
    field_id = seeded["field"]
    # Create an irrigation log
    payload = {
        "field_id": field_id,
        "water_depth_mm": 18.5,
        "duration_minutes": 90.0,
        "flow_rate_lpm": 200.0,
        "source": "manual",
        "notes": "Evening drip cycle after sensor alert",
    }
    resp = client.post("/irrigation/logs", json=payload)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["field_id"] == field_id
    assert created["water_depth_mm"] == 18.5
    # Volume: 18.5 mm * 1.5 ha * 10,000 = 277,500 L
    assert created["water_volume_litres"] == 277500.0

    # Retrieve irrigation logs
    get_resp = client.get(f"/irrigation/logs?field_id={field_id}")
    assert get_resp.status_code == 200
    logs = get_resp.json()
    assert len(logs) >= 1
    assert logs[0]["water_depth_mm"] == 18.5


def test_reports_summary_endpoint(client, seeded, weather):
    weather(routed(forecast=forecast_payload(0.0)))
    field_id = seeded["field"]
    resp = client.get(f"/reports/fields/{field_id}/summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["field_id"] == field_id
    assert data["field_name"] == "North Paddy"
    assert data["farmer_name"] == "Harini"
    assert "ml_water_requirement_mm" in data
    assert "recommended_date" in data
    assert "recommended_time_window" in data
    assert "scheduling_reason" in data


def test_reports_pdf_download_multilingual(client, seeded, weather):
    weather(routed(forecast=forecast_payload(0.0)))
    field_id = seeded["field"]
    for lang in ["en", "te", "hi", "ta", "kn"]:
        resp = client.get(f"/reports/fields/{field_id}/pdf?lang={lang}")
        assert resp.status_code == 200, f"Failed for {lang}: {resp.text}"
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF"), f"Invalid PDF header for {lang}"
        assert len(resp.content) > 10000, f"PDF too small for {lang}: {len(resp.content)} bytes"


def test_reports_csv_download(client, seeded, weather):
    weather(routed(forecast=forecast_payload(0.0)))
    field_id = seeded["field"]
    resp = client.get(f"/reports/fields/{field_id}/csv")
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    # Check UTF-8 BOM
    assert resp.content.startswith(b"\xef\xbb\xbf")
    text = resp.content.decode("utf-8-sig")
    assert "North Paddy" in text
    assert "Harini" in text
    assert "AI ML IRRIGATION PREDICTION" in text
    assert "Recommended Time Window" in text
