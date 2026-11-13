"""Unit tests for app.services.irrigation_scheduler.

Pure logic: no database, no HTTP, no ML model, no network. Weather inputs are hand-built dictionaries that follow
the documented FieldWeatherResult.to_dict() contract (docs/scheduling_logic.md section 2).
"""
import json
import math
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.irrigation_scheduler import (
    ACTION_DEFER, ACTION_IRRIGATE, ACTION_NONE, ACTION_WITHHELD, ACTIONS,
    ScheduleConfig, generate_irrigation_schedule,
)

NOW = datetime(2026, 10, 7, 10, 40, tzinfo=timezone.utc)
FIELD = {"field_id": "F001", "crop_type": "Rice", "area_hectares": 2.0}


def make_weather(rain_1h=0.0, status="ok", forecast=None, **overrides):
    w = {
        "field_id": "F001", "status": status, "usable_for_prediction": status == "ok",
        "data_kind": "current_observation", "data_origin": "live_api",
        "observation": {"observed_at_utc": "2026-10-07T10:30:00", "age_minutes": 10.0, "temperature_c": 29.0,
                        "humidity_pct": 68.0, "rainfall_last_1h_mm": rain_1h, "wind_speed_ms": 3.5,
                        "is_mock": False, "data_kind": "current_observation"},
        "forecast": forecast or {"available": False, "data_kind": "forecast", "reason": "not implemented"},
        "warnings": [], "error": None,
    }
    w.update(overrides)
    return w


def forecast(expected_mm, window_h=24, kind="forecast"):
    return {"available": True, "data_kind": kind, "window_hours": window_h, "expected_rainfall_mm": expected_mm}


def schedule(pred=20.0, weather=None, field=FIELD, **kw):
    return generate_irrigation_schedule(pred, make_weather() if weather is None else weather, field, now=NOW, **kw)


# ── Valid prediction + weather ────────────────────────────────────────────────────────────────────

def test_valid_inputs_recommend_predicted_depth_unchanged():
    s = schedule(20.0)
    assert s.action == ACTION_IRRIGATE
    assert s.predicted_irrigation_mm == 20.0 and s.recommended_irrigation_mm == 20.0
    assert s.unit == "mm" and "depth" in s.unit_basis
    assert s.field_id == "F001" and s.generated_at_utc == "2026-10-07T10:40:00+00:00"
    assert s.reason_codes == ["no_deferral_rule_met"]
    assert s.disclaimer and s.assumptions


def test_fractional_prediction_is_preserved_exactly():
    s = schedule(12.3456)
    assert s.recommended_irrigation_mm == 12.3456


def test_action_is_never_a_low_medium_high_category():
    for pred in (0.0, 5.0, 50.0, None, -1.0):
        s = schedule(pred)
        assert s.action in ACTIONS
        assert s.action.lower() not in {"low", "medium", "high"}


def test_volume_is_computed_from_area_and_documented():
    s = schedule(20.0, field={"field_id": "F001", "area_hectares": 2.0})
    # 20 mm over 2 ha = 20 * 2 * 10,000 L = 400,000 L = 400 m3
    assert s.volume["litres"] == 400_000.0 and s.volume["cubic_metres"] == 400.0
    assert s.volume["area_hectares"] == 2.0 and "10,000" in s.volume["basis"]
    assert s.recommended_irrigation_mm == 20.0  # depth stays the primary quantity


@pytest.mark.parametrize("area", [None, 0, -1.5, "abc", float("nan"), True])
def test_no_volume_without_valid_area(area):
    s = schedule(20.0, field={"field_id": "F001", "area_hectares": area})
    assert s.action == ACTION_IRRIGATE and s.recommended_irrigation_mm == 20.0
    assert s.volume is None
    assert any("volume not computed" in w for w in s.warnings)


def test_field_and_weather_accepted_as_objects():
    class Result:  # attribute-style access, like the adapter's dataclass
        status, usable_for_prediction, data_origin, warnings, error = "ok", True, "live_api", [], None
        observation = SimpleNamespace(observed_at_utc="x", age_minutes=5.0, temperature_c=30.0, humidity_pct=50.0,
                                      rainfall_last_1h_mm=0.0, is_mock=False)
        forecast = {"available": False, "data_kind": "forecast"}
    s = generate_irrigation_schedule(15.0, Result(), SimpleNamespace(field_id="F009", area_hectares=1.0), now=NOW)
    assert s.action == ACTION_IRRIGATE and s.field_id == "F009" and s.volume["litres"] == 150_000.0


def test_integer_field_id_is_accepted_and_stringified():
    assert schedule(10.0, field={"field_id": 7}).field_id == "7"


def test_result_is_json_serialisable():
    json.dumps(schedule(20.0, weather=make_weather(forecast=forecast(3.0))).to_dict())
    json.dumps(schedule(None).to_dict())


def test_small_depth_warning_keeps_value():
    s = schedule(0.4)
    assert s.action == ACTION_IRRIGATE and s.recommended_irrigation_mm == 0.4
    assert any("very small" in w for w in s.warnings)


# ── Rainfall rules ────────────────────────────────────────────────────────────────────────────────

def test_heavy_recent_rain_defers_and_preserves_prediction():
    s = schedule(20.0, weather=make_weather(rain_1h=6.0))
    assert s.action == ACTION_DEFER
    assert s.predicted_irrigation_mm == 20.0 and s.recommended_irrigation_mm == 0.0
    assert s.reason_codes == ["rain_in_last_hour"] and s.reevaluate_after_hours == 3.0
    assert "20" in s.reasons[0] and s.volume is None


def test_light_rain_does_not_reduce_prediction():
    s = schedule(20.0, weather=make_weather(rain_1h=1.0))
    assert s.action == ACTION_IRRIGATE
    assert s.recommended_irrigation_mm == 20.0, "rainfall must never be subtracted from the predicted depth"
    assert any("NOT reduced" in w for w in s.warnings)


def test_rain_threshold_boundary_is_inclusive():
    assert schedule(20.0, weather=make_weather(rain_1h=2.5)).action == ACTION_DEFER
    assert schedule(20.0, weather=make_weather(rain_1h=2.49)).action == ACTION_IRRIGATE


def test_custom_threshold_changes_decision():
    cfg = ScheduleConfig(defer_if_rain_last_1h_mm=0.5)
    assert schedule(20.0, weather=make_weather(rain_1h=1.0), config=cfg).action == ACTION_DEFER


def test_forecast_rain_above_threshold_defers():
    s = schedule(20.0, weather=make_weather(forecast=forecast(15.0, 24)))
    assert s.action == ACTION_DEFER and s.reason_codes == ["forecast_rain"]
    assert s.predicted_irrigation_mm == 20.0 and s.recommended_irrigation_mm == 0.0
    assert s.reevaluate_after_hours == 24


def test_forecast_rain_below_threshold_does_not_defer_or_reduce():
    s = schedule(20.0, weather=make_weather(forecast=forecast(4.0, 24)))
    assert s.action == ACTION_IRRIGATE and s.recommended_irrigation_mm == 20.0


def test_forecast_window_too_long_is_ignored():
    s = schedule(20.0, weather=make_weather(forecast=forecast(50.0, 72)))
    assert s.action == ACTION_IRRIGATE
    assert any("forecast ignored" in w for w in s.warnings)


def test_unavailable_forecast_is_reported_not_assumed():
    s = schedule(20.0)
    assert s.action == ACTION_IRRIGATE
    assert s.weather_context["forecast"]["available"] is False
    assert any("Forecast not used" in w for w in s.warnings)


def test_forecast_not_labelled_as_forecast_is_ignored():
    # Live observations and forecasts must stay distinguishable: mislabelled data cannot trigger a hold.
    s = schedule(20.0, weather=make_weather(forecast=forecast(50.0, 24, kind="current_observation")))
    assert s.action == ACTION_IRRIGATE
    assert s.weather_context["forecast"]["usable"] is False


@pytest.mark.parametrize("bad", [{"available": True, "data_kind": "forecast", "window_hours": 24},
                                 {"available": True, "data_kind": "forecast", "window_hours": 24, "expected_rainfall_mm": -3},
                                 {"available": True, "data_kind": "forecast", "window_hours": 0, "expected_rainfall_mm": 30},
                                 {"available": True, "data_kind": "forecast", "window_hours": 24, "expected_rainfall_mm": "lots"}])
def test_invalid_forecast_values_are_ignored(bad):
    s = schedule(20.0, weather=make_weather(forecast=bad))
    assert s.action == ACTION_IRRIGATE and s.weather_context["forecast"]["usable"] is False


def test_current_rain_takes_precedence_over_forecast():
    s = schedule(20.0, weather=make_weather(rain_1h=5.0, forecast=forecast(30.0)))
    assert s.reason_codes == ["rain_in_last_hour"]


# ── Missing / invalid prediction ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pred,code", [
    (None, "prediction_missing"),
    ("12.5", "prediction_invalid"), ("", "prediction_invalid"), ([20.0], "prediction_invalid"),
    (True, "prediction_invalid"), (float("nan"), "prediction_invalid"), (math.inf, "prediction_invalid"),
    (-0.5, "prediction_negative"),
    (250.0, "prediction_implausible"),
])
def test_bad_prediction_is_withheld_not_replaced(pred, code):
    s = schedule(pred)
    assert s.action == ACTION_WITHHELD and s.reason_codes == [code]
    assert s.recommended_irrigation_mm is None and s.volume is None
    assert s.reasons


def test_negative_prediction_is_not_clipped_to_zero():
    s = schedule(-0.2)
    assert s.action == ACTION_WITHHELD and s.predicted_irrigation_mm == -0.2
    assert s.recommended_irrigation_mm is None


def test_implausible_ceiling_is_configurable():
    assert schedule(250.0, config=ScheduleConfig(max_plausible_irrigation_mm=300.0)).action == ACTION_IRRIGATE


def test_zero_prediction_means_no_irrigation_even_without_weather():
    s = schedule(0.0, weather=make_weather(status="unavailable", usable_for_prediction=False, observation=None))
    assert s.action == ACTION_NONE and s.recommended_irrigation_mm == 0.0
    assert s.reason_codes == ["prediction_zero"]
    assert any("Weather not used" in w for w in s.warnings)


# ── Unusable weather: never fabricated, never defaulted ───────────────────────────────────────────

@pytest.mark.parametrize("status,usable,code", [
    ("unavailable", False, "weather_unavailable"),
    ("stale", False, "weather_stale"),
    ("mock", False, "weather_mock"),
    ("something_new", False, "weather_not_usable"),
    ("ok", False, "weather_not_usable"),       # status ok but adapter did not mark it usable
])
def test_unusable_weather_withholds_recommendation(status, usable, code):
    w = make_weather(status=status, usable_for_prediction=usable)
    s = schedule(20.0, weather=w)
    assert s.action == ACTION_WITHHELD and s.reason_codes == [code]
    assert s.predicted_irrigation_mm == 20.0, "raw model output is still echoed for the caller"
    assert s.recommended_irrigation_mm is None


def test_unavailable_weather_error_code_is_reported():
    w = make_weather(status="unavailable", usable_for_prediction=False, observation=None,
                     error={"code": "weather_timeout", "message": "slow"})
    s = schedule(20.0, weather=w)
    assert s.action == ACTION_WITHHELD and "weather_timeout" in s.reasons[0]


@pytest.mark.parametrize("weather,code", [
    (None, "weather_missing"),
    ({}, "weather_malformed"),
    ("sunny", "weather_malformed"),
    (make_weather(observation=None), "weather_malformed"),
    (make_weather(rain_1h=None), "weather_values_invalid"),
    (make_weather(rain_1h=float("nan")), "weather_values_invalid"),
    (make_weather(rain_1h=-4.0), "weather_values_invalid"),
    (make_weather(rain_1h="heavy"), "weather_values_invalid"),
])
def test_missing_or_malformed_weather_is_withheld(weather, code):
    s = generate_irrigation_schedule(20.0, weather, FIELD, now=NOW)
    assert s.action == ACTION_WITHHELD and s.reason_codes == [code]
    assert s.recommended_irrigation_mm is None


def test_mock_observation_flag_blocks_even_if_status_ok():
    w = make_weather()
    w["observation"]["is_mock"] = True
    s = schedule(20.0, weather=w)
    assert s.action == ACTION_WITHHELD and s.recommended_irrigation_mm is None


def test_stale_weather_values_are_not_used_for_rain_rules():
    s = schedule(20.0, weather=make_weather(rain_1h=9.0, status="stale"))
    assert s.action == ACTION_WITHHELD and s.reason_codes == ["weather_stale"]  # not DEFER from old data


# ── Invalid field data / config ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("field", [None, {}, {"area_hectares": 1.0}, {"field_id": ""}, {"field_id": "  "}, "F001"])
def test_invalid_field_data_is_withheld(field):
    s = generate_irrigation_schedule(20.0, make_weather(), field, now=NOW)
    assert s.action == ACTION_WITHHELD and s.reason_codes == ["field_data_invalid"]
    assert s.recommended_irrigation_mm is None


@pytest.mark.parametrize("name", ["defer_if_rain_last_1h_mm", "defer_if_forecast_rain_mm", "max_forecast_window_hours",
                                  "reevaluate_after_rain_hours", "max_plausible_irrigation_mm", "small_depth_warning_mm"])
@pytest.mark.parametrize("bad", [0, -1, float("nan"), "5", None, True])
def test_invalid_config_is_rejected(name, bad):
    with pytest.raises(ValueError):
        ScheduleConfig(**{name: bad})


def test_withheld_results_never_carry_a_recommended_quantity():
    cases = [schedule(None), schedule(float("nan")), schedule(-3.0), schedule(999.0),
             schedule(20.0, weather=make_weather(status="unavailable", usable_for_prediction=False)),
             generate_irrigation_schedule(20.0, None, FIELD, now=NOW),
             generate_irrigation_schedule(20.0, make_weather(), None, now=NOW)]
    for s in cases:
        assert s.action == ACTION_WITHHELD
        assert s.recommended_irrigation_mm is None and s.volume is None and s.reasons and s.reason_codes
