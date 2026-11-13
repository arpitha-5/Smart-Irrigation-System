"""Unit tests for app.services.alert_engine (pure rules)."""
from app.services.alert_engine import AlertConfig, evaluate_alerts

# rice-like profile as reported by the existing engine: critical (stress onset) 45 %, target 65 %
BASE = dict(soil_moisture=40.0, reading_age_hours=1.0, critical_threshold_pct=45.0, optimal_target_pct=65.0,
            growth_stage="vegetative", forecast_rain_mm=0.0)


def run(**kw):
    return evaluate_alerts(**{**BASE, **kw})


def codes(r):
    return [a["code"] for a in r["alerts"]]


def test_healthy_soil_raises_nothing():
    r = run(soil_moisture=55.0)
    assert r["level"] == "NONE" and r["alerts"] == [] and r["is_emergency"] is False


def test_below_critical_is_a_warning_not_an_emergency():
    r = run(soil_moisture=40.0)                    # emergency line is 0.70 * 45 = 31.5
    assert r["level"] == "WARNING" and codes(r) == ["DROUGHT_RISK"] and not r["is_emergency"]


def test_severe_depletion_is_an_emergency():
    r = run(soil_moisture=25.0)
    assert r["level"] == "EMERGENCY" and r["is_emergency"] and "DROUGHT_EMERGENCY" in codes(r)
    assert r["thresholds"]["emergency_below_pct"] == 31.5
    assert "Irrigate now" in r["alerts"][0]["recommended_action"]


def test_boundary_is_strict():
    assert run(soil_moisture=31.5)["level"] == "WARNING"          # exactly on the line: not below it
    assert run(soil_moisture=31.4)["level"] == "EMERGENCY"
    assert run(soil_moisture=45.0)["level"] == "NONE"


def test_sensitive_growth_stage_triggers_the_emergency_earlier():
    assert run(soil_moisture=35.0, growth_stage="vegetative")["level"] == "WARNING"     # 35 > 31.5
    assert run(soil_moisture=35.0, growth_stage="Flowering")["level"] == "EMERGENCY"    # 35 < 0.85 * 45 = 38.25


def test_forecast_or_observed_rain_prevents_an_emergency_but_not_the_warning():
    r = run(soil_moisture=25.0, forecast_rain_mm=15.0)
    assert r["level"] == "WARNING" and "DROUGHT_RISK" in codes(r) and "forecast" in r["alerts"][0]["message"]
    r = run(soil_moisture=25.0, schedule_reason_codes=["rain_in_last_hour"], schedule_action="DEFER")
    assert r["level"] == "WARNING" and "IRRIGATION_DEFERRED" in codes(r)
    assert run(soil_moisture=25.0, forecast_rain_mm=9.9)["level"] == "EMERGENCY"      # below the relief threshold


def test_missing_forecast_does_not_block_an_emergency():
    assert run(soil_moisture=25.0, forecast_rain_mm=None)["level"] == "EMERGENCY"


def test_stale_reading_is_flagged_and_never_an_emergency():
    r = run(soil_moisture=25.0, reading_age_hours=30.0)
    assert r["level"] == "WARNING" and "SENSOR_STALE" in codes(r) and "DROUGHT_EMERGENCY" not in codes(r)


def test_no_reading_cannot_assess_drought():
    r = run(soil_moisture=None, reading_age_hours=None)
    assert codes(r) == ["NO_SENSOR_DATA"] and r["level"] == "WARNING"


def test_overwatering_warning():
    r = run(soil_moisture=76.0)
    assert codes(r) == ["OVERWATERING_RISK"] and run(soil_moisture=74.9)["level"] == "NONE"


def test_withheld_schedule_is_informational_and_does_not_hide_an_emergency():
    r = run(soil_moisture=25.0, schedule_action="WITHHELD", schedule_reason_codes=["weather_stale"])
    assert r["level"] == "EMERGENCY" and "SCHEDULE_WITHHELD" in codes(r)
    assert run(schedule_action="WITHHELD", soil_moisture=55.0)["level"] == "INFO"


def test_bad_inputs_never_raise():
    for bad in (None, "x", float("nan"), True, -1):
        r = evaluate_alerts(soil_moisture=bad, reading_age_hours=bad, critical_threshold_pct=bad, optimal_target_pct=bad,
                            forecast_rain_mm=bad, growth_stage=bad)
        assert r["level"] in ("NONE", "INFO", "WARNING", "EMERGENCY")


def test_config_is_respected():
    cfg = AlertConfig(emergency_fraction_of_critical=0.9)
    assert run(soil_moisture=35.0, config=cfg)["level"] == "EMERGENCY"      # 35 < 0.9 * 45 = 40.5
