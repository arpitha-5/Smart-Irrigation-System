"""End to end: trained ML depth -> weather-aware scheduler -> alerts -> time-slot plan, through the real FastAPI app.

Same approach as test_irrigation_schedule_integration.py: only the HTTP transport is faked (conftest blocks real HTTP).
A field gets ML recommendations only when it has a crop record WITH a planting date and a soil-moisture value; the
``seeded`` fixture has neither, which is why the older tests still see the rule-based 35 mm.
Needs the shipped model in backend/models (tests skip if it is absent).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services import irrigation_service, ml_irrigation_service
from tests.test_irrigation_schedule_integration import CURRENT_OK, forecast_payload, post, routed, weather  # noqa: F401


@pytest.fixture(autouse=True)
def _need_model():
    ml_irrigation_service.reset_predictor_cache()
    if ml_irrigation_service.get_predictor() is None:
        pytest.skip("no trained model in backend/models (run scripts/train_irrigation_model.py)")
    yield
    ml_irrigation_service.reset_predictor_cache()


def _utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def grow(client, days_after_sowing=60, crop="rice"):
    planted = (_utcnow_naive().date() - timedelta(days=days_after_sowing)).isoformat()
    res = client.post("/crops", json={"field_id": "F001", "crop_type": crop, "planting_date": planted})
    assert res.status_code in (200, 201), res.text


def reading(client, value, hours_ago=1.0):
    ts = (_utcnow_naive() - timedelta(hours=hours_ago)).replace(microsecond=0).isoformat()
    res = client.post("/sensor/readings", json={"sensor_id": "SM001", "timestamp": ts, "soil_moisture": value, "is_simulated": True})
    assert res.status_code in (200, 201), res.text


def get_reco(client):
    res = client.get("/recommendations/irrigation/F001")
    assert res.status_code == 200, res.text
    return res.json()


def test_trained_model_supplies_the_depth_when_it_can(client, seeded, weather):
    weather(routed(forecast=forecast_payload(0.0)))
    grow(client)
    reading(client, 17.0)
    data = get_reco(client)
    ml, inp, sch = data["ml_prediction"], data["schedule_input"], data["irrigation_schedule"]
    assert ml["available"] is True and ml["inputs"]["moisture_source"] == "sensor"
    assert inp["source"] == "ml_model" and inp["is_ml_prediction"] is True
    assert inp["predicted_irrigation_mm"] == ml["depth_mm"] == sch["predicted_irrigation_mm"]
    assert sch["action"] == "IRRIGATE" and abs(sch["volume"]["litres"] - ml["depth_mm"] * 1.5 * 10000) < 1
    assert data["action"] in {"IRRIGATE_IMMEDIATELY", "IRRIGATE_LIGHT"}                # existing engine output still present
    assert data["irrigation_plan"]["status"] == "SCHEDULED"
    assert abs(data["irrigation_plan"]["total_depth_mm"] - ml["depth_mm"]) < 0.1


def test_emergency_alert_and_immediate_plan_when_soil_is_critically_dry(client, seeded, weather):
    weather(routed(forecast=forecast_payload(0.0)))
    grow(client)
    reading(client, 10.0)
    data = get_reco(client)
    assert data["alerts"]["is_emergency"] is True and data["alerts"]["level"] == "EMERGENCY"
    assert "DROUGHT_EMERGENCY" in [a["code"] for a in data["alerts"]["alerts"]]
    assert data["irrigation_schedule"]["action"] == "IRRIGATE"
    plan = data["irrigation_plan"]
    assert plan["emergency"] is True and plan["slots"][0]["window"] == "IMMEDIATE"
    assert plan["rate_assumed"] is True and any("ASSUMED" in w for w in plan["warnings"])


def test_emergency_is_not_raised_when_heavy_rain_is_forecast_but_warning_remains(client, seeded, weather):
    weather(routed(forecast=forecast_payload(2.0)))                       # 8 steps x 2 mm = 16 mm in 24 h
    grow(client)
    reading(client, 10.0)
    data = get_reco(client)
    assert data["alerts"]["level"] == "WARNING" and not data["alerts"]["is_emergency"]
    assert data["irrigation_schedule"]["action"] in {"DEFER", "NO_IRRIGATION_NEEDED"}
    assert data["irrigation_plan"]["status"] == "NO_PLAN"


def test_emergency_alert_survives_weather_failure(client, seeded, weather):
    weather(routed(current_status=500, forecast_status=500))
    grow(client)
    reading(client, 10.0)
    data = get_reco(client)
    assert data["alerts"]["is_emergency"] is True                            # alerts do not depend on weather
    assert data["irrigation_schedule"]["action"] == "WITHHELD"
    assert data["irrigation_plan"]["status"] == "NO_PLAN"


def test_missing_planting_date_falls_back_to_rules_and_says_why(client, seeded, weather):
    weather()
    res = post(client)                                                        # the original reference request
    data = res.json()
    assert data["recommended_water_mm"] == 35.0 and data["schedule_input"]["source"] == "rule_based_recommendation"
    assert data["schedule_input"]["is_ml_prediction"] is False
    assert data["ml_prediction"]["available"] is False and "days_after_sowing" in data["ml_prediction"]["reason"]
    assert data["irrigation_schedule"]["volume"]["litres"] == 525000.0       # unchanged from before ML existed


def test_unsupported_crop_falls_back_to_rules(client, seeded, weather):
    weather()
    grow(client, crop="banana")
    reading(client, 17.0)
    data = get_reco(client)
    assert data["ml_prediction"]["available"] is False and "not supported" in data["ml_prediction"]["reason"]
    assert data["schedule_input"]["is_ml_prediction"] is False


def test_stale_reading_is_not_fed_to_the_model(client, seeded, weather):
    weather()
    grow(client)
    reading(client, 17.0, hours_ago=40.0)
    data = get_reco(client)
    assert data["ml_prediction"]["available"] is False and "40 h old" in data["ml_prediction"]["reason"]
    assert "SENSOR_STALE" in [a["code"] for a in data["alerts"]["alerts"]]


def test_ml_can_be_switched_off(client, seeded, weather, monkeypatch):
    weather()
    grow(client)
    reading(client, 17.0)
    monkeypatch.setattr(ml_irrigation_service, "get_predictor", lambda *a, **k: None)
    data = get_reco(client)
    assert data["ml_prediction"]["available"] is False and data["schedule_input"]["source"] == "rule_based_recommendation"


def test_critical_soil_with_a_no_irrigate_model_uses_the_rule_based_safety_net(client, seeded, weather, monkeypatch):
    weather(routed(forecast=forecast_payload(0.0)))
    grow(client)
    reading(client, 10.0)
    real = ml_irrigation_service.get_predictor()

    class SaysNo:
        def predict(self, raw):
            p = real.predict(raw)
            p.irrigate, p.depth_mm = False, 0.0
            return p
    monkeypatch.setattr(ml_irrigation_service, "get_predictor", lambda *a, **k: SaysNo())
    data = get_reco(client)
    assert data["schedule_input"]["source"] == "rule_based_emergency_override" and data["ml_prediction"]["overridden_by"] == "emergency_alert"
    assert data["irrigation_schedule"]["action"] == "IRRIGATE" and data["alerts"]["is_emergency"]


def test_alerts_work_without_a_registered_field(client, seeded):
    res = client.post("/recommendations/irrigation", json={"crop_type": "rice", "growth_stage": "vegetative", "soil_moisture": 15.0})
    data = res.json()
    assert data["irrigation_schedule"] is None and data["alerts"]["is_emergency"] is True


def test_irrigation_method_sets_the_duration(client, seeded, weather):
    weather(routed(forecast=forecast_payload(0.0)))
    grow(client)
    reading(client, 17.0)
    res = post(client, soil_moisture=None, irrigation_method="drip")
    plan = res.json()["irrigation_plan"]
    assert plan["rate_mm_per_hour"] == 3.0 and plan["rate_assumed"] is False


def test_model_serving_endpoints(client):
    info = client.get("/recommendations/irrigation-model").json()
    assert info["loaded"] is True and info["version"] and "SYNTHETIC" in info["trained_on"] and info["holdout_metrics"]["roc_auc"] > 0.5
    ok = client.post("/recommendations/irrigation/ml-predict", json={"crop_type": "rice", "days_after_sowing": 60, "soil_moisture": 15.0}).json()
    assert ok["available"] is True and ok["depth_mm"] > 0 and ok["unit"] == "mm"
    bad = client.post("/recommendations/irrigation/ml-predict", json={"crop_type": "banana", "days_after_sowing": 60, "soil_moisture": 15.0})
    assert bad.status_code == 200 and bad.json()["available"] is False
    assert client.post("/recommendations/irrigation/ml-predict", json={"crop_type": "rice", "days_after_sowing": 60, "soil_moisture": 150}).status_code == 422


def test_openapi_lists_the_new_fields_as_optional(client):
    schema = client.get("/openapi.json").json()["components"]["schemas"]["IrrigationRecommendationResponse"]
    assert {"ml_prediction", "irrigation_plan", "alerts"} <= set(schema["properties"])
    assert not ({"ml_prediction", "irrigation_plan", "alerts"} & set(schema.get("required", [])))
