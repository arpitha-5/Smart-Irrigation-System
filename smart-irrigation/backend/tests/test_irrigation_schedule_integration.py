"""Integration of irrigation_scheduler into POST /recommendations/irrigation and GET /recommendations/irrigation/{id}.

The real chain runs end to end: recommend_irrigation (rule based) -> weather_adapter.get_field_weather ->
irrigation_scheduler.generate_irrigation_schedule -> FastAPI/Pydantic serialisation.
Only the HTTP transport is faked (httpx.MockTransport); conftest blocks every real request.

Reference request used below (deterministic, rule based): rice, flowering, soil moisture 15 % ->
the existing engine recommends 35.0 mm (its cap) with action IRRIGATE_IMMEDIATELY. Field F001 has 1.5 ha, so 35 mm
is 35 * 1.5 * 10,000 = 525,000 L.
"""
import calendar
import json
from datetime import datetime, timedelta

import httpx
import pytest

from app.config import Settings
from app.models import Field
from app.services import irrigation_service
from app.services.weather_adapter import get_field_weather as real_get_field_weather
from app.services.weather_service import WeatherProvider

KEY = "SECRET-TEST-KEY-123"
OBSERVED = datetime(2026, 10, 7, 10, 30, 0)
NOW = OBSERVED + timedelta(minutes=10)
FIRST_STEP = datetime(2026, 10, 7, 12, 0, 0)  # first 3 h step after NOW; steps 0..7 are inside the 24 h window

CURRENT_OK = {"coord": {"lon": 78.4867, "lat": 17.385}, "dt": calendar.timegm(OBSERVED.timetuple()),
              "main": {"temp": 29.0, "humidity": 68}, "rain": {"1h": 0.4}, "wind": {"speed": 3.5},
              "weather": [{"description": "light rain"}]}

POST_DEFICIT = {"field_id": "F001", "crop_type": "rice", "growth_stage": "flowering", "soil_moisture": 15.0,
                "temperature": 32.0, "recent_rainfall_mm": 0.0, "forecast_rainfall_mm": 0.0}


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────

def _ts(dt):
    return calendar.timegm(dt.timetuple())


def forecast_payload(rain_per_step):
    """9 steps; the 9th (outside the 24 h window) carries 50 mm that must never influence the decision."""
    def step(i, rain):
        d = {"dt": _ts(FIRST_STEP + timedelta(hours=3 * i)), "main": {"temp": 28.0}, "pop": 0.3}
        if rain is not None:
            d["rain"] = {"3h": rain}
        return d
    return {"cod": "200", "cnt": 9, "list": [step(i, rain_per_step) for i in range(8)] + [step(8, 50.0)]}


def routed(current=CURRENT_OK, forecast=None, current_status=200, forecast_status=200):
    def handler(req):
        if req.url.path.endswith("/forecast"):
            if forecast_status != 200:
                return httpx.Response(forecast_status, json={"message": "x"})
            return httpx.Response(200, json=forecast if forecast is not None else forecast_payload(0.5))
        if current_status != 200:
            return httpx.Response(current_status, json={"message": "x"})
        return httpx.Response(200, json=current)
    return handler


@pytest.fixture()
def weather(monkeypatch):
    """Install a fake-transport weather provider behind the REAL adapter. Returns a configure(...) function."""
    state = {"calls": []}

    def configure(handler=None, key=KEY, now=NOW, **settings_kw):
        handler = handler or routed()

        def wrapped(request):
            state["calls"].append(request.url.path)
            return handler(request)

        s = Settings(openweather_api_key=key, openweather_base_url="https://owm.test/weather",
                     openweather_forecast_url="https://owm.test/forecast", **settings_kw)
        prov = WeatherProvider(s, httpx.MockTransport(wrapped))
        monkeypatch.setattr(irrigation_service, "get_field_weather",
                            lambda db, field_id, **kw: real_get_field_weather(db, field_id, provider=prov, now=now, **kw))
        return state["calls"]

    return configure


def post(client, **overrides):
    return client.post("/recommendations/irrigation", json={**POST_DEFICIT, **overrides})


# ── valid weather ─────────────────────────────────────────────────────────────────────────────────

def test_valid_weather_irrigates_and_computes_volume_from_the_field_model(client, seeded, weather):
    calls = weather(routed(forecast=forecast_payload(0.5)))           # 0.4 mm/h now, 4 mm forecast in 24 h
    res = post(client)
    assert res.status_code == 200
    data = res.json()

    # existing recommendation untouched
    assert data["action"] == "IRRIGATE_IMMEDIATELY" and data["urgency"] == "HIGH"
    assert data["recommended_water_mm"] == 35.0
    assert data["recommendation_engine"].startswith("Rule-based")

    sch = data["irrigation_schedule"]
    assert sch["field_id"] == "F001"                                    # Field.field_id
    assert sch["action"] == "IRRIGATE" and sch["reason_codes"] == ["no_deferral_rule_met"]
    assert sch["predicted_irrigation_mm"] == 35.0 and sch["recommended_irrigation_mm"] == 35.0
    # light rain (0.4 mm/h) is NOT subtracted from the depth
    assert sch["unit"] == "mm"
    assert sch["volume"]["area_hectares"] == 1.5                        # Field.area_hectares
    assert sch["volume"]["litres"] == 525000.0 and sch["volume"]["cubic_metres"] == 525.0
    # observed and forecast rain stay separate and correctly labelled
    ctx = sch["weather_context"]
    assert ctx["observation"]["data_kind"] == "current_observation" and ctx["observation"]["rainfall_last_1h_mm"] == 0.4
    assert ctx["forecast"]["data_kind"] == "forecast" and ctx["forecast"]["usable"] is True
    assert ctx["forecast"]["expected_rainfall_mm"] == 4.0 and ctx["forecast"]["window_hours"] == 24.0
    assert calls == ["/weather", "/forecast"]                           # adapter used once, nothing else
    assert KEY not in json.dumps(data)


def test_schedule_input_states_the_depth_is_rule_based_not_ml(client, seeded, weather):
    weather()
    inp = post(client).json()["schedule_input"]
    assert inp["source"] == "rule_based_recommendation" and inp["is_ml_prediction"] is False
    assert inp["predicted_irrigation_mm"] == 35.0 and inp["unit"] == "mm"
    assert "not from a trained ML model" in inp["note"]
    assert inp["recommendation_engine"].startswith("Rule-based")


def test_get_endpoint_also_returns_the_schedule(client, seeded, weather):
    weather(routed(forecast=forecast_payload(0.5)))
    res = client.get("/recommendations/irrigation/F001")
    assert res.status_code == 200
    data = res.json()
    assert {"action", "recommended_water_mm", "urgency", "reason", "factors_evaluated", "recommendation_engine",
            "sensor_freshness", "limitations"} <= set(data)
    assert data["irrigation_schedule"]["field_id"] == "F001"
    assert data["irrigation_schedule"]["predicted_irrigation_mm"] == data["recommended_water_mm"]


# ── rainfall / forecast deferral ──────────────────────────────────────────────────────────────────

def test_observed_rain_defers_without_changing_the_prediction(client, seeded, weather):
    weather(routed(current=dict(CURRENT_OK, rain={"1h": 6.0}), forecast=forecast_payload(0.0)))
    data = post(client).json()
    sch = data["irrigation_schedule"]
    assert sch["action"] == "DEFER" and sch["reason_codes"] == ["rain_in_last_hour"]
    assert sch["predicted_irrigation_mm"] == 35.0                       # echoed, NOT reduced by the 6 mm
    assert sch["recommended_irrigation_mm"] == 0.0
    assert sch["reevaluate_after_hours"] == 3.0 and sch["volume"] is None
    assert data["recommended_water_mm"] == 35.0                         # top-level recommendation unchanged


def test_forecast_rain_defers_and_is_labelled_as_forecast(client, seeded, weather):
    weather(routed(forecast=forecast_payload(2.0)))                     # 8 steps x 2 mm = 16 mm >= 10 mm threshold
    sch = post(client).json()["irrigation_schedule"]
    assert sch["action"] == "DEFER" and sch["reason_codes"] == ["forecast_rain"]
    assert sch["predicted_irrigation_mm"] == 35.0 and sch["recommended_irrigation_mm"] == 0.0
    assert sch["reevaluate_after_hours"] == 24.0
    assert sch["weather_context"]["forecast"]["expected_rainfall_mm"] == 16.0
    assert sch["weather_context"]["observation"]["rainfall_last_1h_mm"] == 0.4   # observed rain not mixed in


def test_rain_beyond_the_forecast_window_does_not_defer(client, seeded, weather):
    weather(routed(forecast=forecast_payload(0.0)))                     # 50 mm sits in the 9th step, outside 24 h
    assert post(client).json()["irrigation_schedule"]["action"] == "IRRIGATE"


def test_forecast_failure_is_not_treated_as_zero_rain(client, seeded, weather):
    weather(routed(forecast_status=500))
    sch = post(client).json()["irrigation_schedule"]
    assert sch["action"] == "IRRIGATE"                                  # decided on the observation alone
    fc = sch["weather_context"]["forecast"]
    assert fc["available"] is False and fc["usable"] is False
    assert fc.get("expected_rainfall_mm") is None                       # no 0 mm substituted
    assert any(w.startswith("Forecast not used") for w in sch["warnings"])


# ── unavailable / stale / mock weather ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kwargs,code", [
    (dict(handler=routed(current_status=500)), "weather_unavailable"),      # provider error, no stored fallback
    (dict(key=None), "weather_unavailable"),                                # API key not configured
])
def test_unavailable_weather_withholds_but_keeps_the_recommendation(client, seeded, weather, kwargs, code):
    weather(**kwargs)
    res = post(client)
    assert res.status_code == 200
    data = res.json()
    sch = data["irrigation_schedule"]
    assert sch["action"] == "WITHHELD" and sch["reason_codes"] == [code]
    assert sch["recommended_irrigation_mm"] is None and sch["volume"] is None
    assert sch["predicted_irrigation_mm"] == 35.0
    assert sch["weather_context"]["observation"] is None               # nothing fabricated
    assert data["action"] == "IRRIGATE_IMMEDIATELY" and data["recommended_water_mm"] == 35.0


def test_stale_weather_withholds(client, seeded, weather):
    weather(now=OBSERVED + timedelta(hours=5))                         # observation is 5 h old, limit is 3 h
    sch = post(client).json()["irrigation_schedule"]
    assert sch["action"] == "WITHHELD" and sch["reason_codes"] == ["weather_stale"]
    assert sch["recommended_irrigation_mm"] is None and sch["volume"] is None


def test_mock_weather_withholds(client, seeded, weather):
    calls = weather(weather_mock=True, now=None)                       # mock rows are stamped with the real clock
    sch = post(client).json()["irrigation_schedule"]
    assert sch["action"] == "WITHHELD" and sch["reason_codes"] == ["weather_mock"]
    assert sch["recommended_irrigation_mm"] is None
    assert calls == []                                                 # mock mode never calls the API


# ── zero water quantity ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("overrides,expected_action", [
    ({"soil_moisture": 95.0}, "MAINTAIN_MONITORING"),                  # soil already above the target
    ({"recent_rainfall_mm": 25.0}, "DEFER_DUE_TO_RAIN"),               # existing engine defers -> 0 mm
])
def test_zero_water_quantity_never_produces_an_irrigation_action(client, seeded, weather, overrides, expected_action):
    weather(routed(forecast=forecast_payload(0.0)))                    # dry weather: nothing to hold back for
    data = post(client, **overrides).json()
    assert data["action"] == expected_action and data["recommended_water_mm"] == 0.0
    sch = data["irrigation_schedule"]
    assert sch["action"] == "NO_IRRIGATION_NEEDED" and sch["reason_codes"] == ["prediction_zero"]
    assert sch["recommended_irrigation_mm"] == 0.0 and sch["volume"] is None
    assert sch["action"] != "IRRIGATE"


def test_zero_water_with_unavailable_weather_stays_no_irrigation(client, seeded, weather):
    weather(routed(current_status=500))
    sch = post(client, soil_moisture=95.0).json()["irrigation_schedule"]
    assert sch["action"] == "NO_IRRIGATION_NEEDED"
    assert any("Weather not used" in w for w in sch["warnings"])


# ── field area ────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("area", [None, 0.0, -2.0])
def test_missing_or_invalid_field_area_gives_depth_without_volume(client, db, seeded, weather, area):
    row = db.get(Field, "F001")
    row.area_hectares = area
    db.commit()
    weather(routed(forecast=forecast_payload(0.5)))
    sch = post(client).json()["irrigation_schedule"]
    assert sch["action"] == "IRRIGATE" and sch["recommended_irrigation_mm"] == 35.0
    assert sch["volume"] is None                                       # no volume invented
    assert any("No valid area_hectares" in w for w in sch["warnings"])


# ── backward compatibility / safety ───────────────────────────────────────────────────────────────

def test_request_without_field_id_still_works_and_explains_why_there_is_no_schedule(client, seeded, weather):
    calls = weather()
    payload = {k: v for k, v in POST_DEFICIT.items() if k != "field_id"}
    res = client.post("/recommendations/irrigation", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "IRRIGATE_IMMEDIATELY" and data["recommended_water_mm"] == 35.0
    assert data["irrigation_schedule"] is None and data["schedule_input"] is None
    assert "field_id" in data["scheduling_note"]
    assert calls == []                                                 # no weather lookup without a field


def test_unknown_field_keeps_existing_behaviour_without_a_schedule(client, seeded, weather):
    calls = weather()
    res = client.get("/recommendations/irrigation/DOES_NOT_EXIST")
    assert res.status_code == 200                                      # as before the integration
    data = res.json()
    assert data["irrigation_schedule"] is None and "not registered" in data["scheduling_note"]
    assert calls == []


def test_minimal_legacy_payload_is_still_accepted(client, seeded, weather):
    weather()
    assert client.post("/recommendations/irrigation", json={}).status_code == 200
    assert client.post("/recommendations/irrigation", json={"field_id": "F001"}).status_code == 200


def test_unexpected_scheduling_failure_never_breaks_the_recommendation(client, seeded, monkeypatch):
    def explode(*a, **k):
        raise RuntimeError(f"secret {KEY}")
    monkeypatch.setattr(irrigation_service, "get_field_weather", explode)
    res = post(client)
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "IRRIGATE_IMMEDIATELY" and data["recommended_water_mm"] == 35.0
    assert data["irrigation_schedule"] is None and "RuntimeError" in data["scheduling_note"]
    assert KEY not in json.dumps(data)                                 # exception text is not leaked


def test_attach_does_not_alter_existing_recommendation_values(db, seeded, weather):
    weather()
    base = irrigation_service.recommend_irrigation(db=db, field_id="F001", crop_type="rice",
                                                   growth_stage="flowering", soil_moisture=15.0)
    merged = irrigation_service.attach_irrigation_schedule(db, base, "F001")
    assert {k: merged[k] for k in base} == base
    assert set(merged) - set(base) == {"irrigation_schedule", "schedule_input", "scheduling_note",
                                       "ml_prediction", "irrigation_plan", "alerts",
                                       "scheduling_recommendation"}      # Milestone 2 additions


def test_openapi_documents_the_new_fields_and_keeps_existing_ones(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    props = schemas["IrrigationRecommendationResponse"]["properties"]
    assert {"irrigation_schedule", "schedule_input", "scheduling_note"} <= set(props)
    assert {"action", "recommended_water_mm", "urgency", "reason", "factors_evaluated", "recommendation_engine",
            "sensor_freshness", "limitations"} <= set(props)
    required = set(schemas["IrrigationRecommendationResponse"]["required"])
    assert not ({"irrigation_schedule", "schedule_input", "scheduling_note"} & required)   # additive, optional
    assert {"IrrigationScheduleResponse", "ScheduleInputInfo"} <= set(schemas)
