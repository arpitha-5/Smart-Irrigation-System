"""Tests for the OpenWeatherMap forecast integration.

Layers covered:
  A. WeatherProvider.fetch_forecast / parse_forecast   (HTTP + parsing, mocked transport)
  B. weather_adapter.build_forecast_block              (3-hour steps -> scheduler format)
  C. weather_adapter.get_field_weather                 (current observation + forecast, failures contained)
  D. irrigation_scheduler on the adapter's real output (forecast DEFER / non-deferral, no fabricated rain)

No real API call is possible: an autouse fixture makes the real HTTP transport fail the test.
"""
import calendar
import json
from datetime import datetime, timedelta

import httpx
import pytest

from app.config import Settings
from app.errors import AppError
from app.services.irrigation_scheduler import (
    ACTION_DEFER, ACTION_IRRIGATE, generate_irrigation_schedule,
)
from app.services.weather_adapter import build_forecast_block, get_field_weather
from app.services.weather_service import ForecastStep, ProviderForecast, WeatherProvider

KEY = "SECRET-TEST-KEY-123"
OBSERVED = datetime(2026, 10, 7, 10, 30, 0)
NOW = OBSERVED + timedelta(minutes=10)            # 10:40 UTC
FIRST_STEP = datetime(2026, 10, 7, 12, 0, 0)      # first 3-hour step after NOW; 8 steps fall in (NOW, NOW+24h]
FIELD = {"field_id": "F001", "area_hectares": 1.0}

CURRENT_OK = {"coord": {"lon": 78.4867, "lat": 17.385}, "dt": calendar.timegm(OBSERVED.timetuple()),
              "main": {"temp": 29.0, "humidity": 68}, "rain": {"1h": 0.4}, "wind": {"speed": 3.5},
              "weather": [{"description": "light rain"}]}


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    def blocked(self, request):
        raise AssertionError("A real HTTP request was attempted in a unit test.")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────

def _ts(dt):
    return calendar.timegm(dt.timetuple())


def step(i, rain=None, pop=0.3, **extra):
    """One provider forecast entry i steps after FIRST_STEP. rain=None -> the provider omits 'rain' (dry)."""
    d = {"dt": _ts(FIRST_STEP + timedelta(hours=3 * i)), "main": {"temp": 28.0}, "pop": pop}
    if rain is not None:
        d["rain"] = {"3h": rain}
    d.update(extra)
    return d


def forecast_payload(rains, outside=50.0):
    """8 in-window steps from ``rains`` (None = dry) plus a 9th step OUTSIDE the 24 h window carrying ``outside`` mm."""
    assert len(rains) == 8
    return {"cod": "200", "cnt": 9, "list": [step(i, r) for i, r in enumerate(rains)] + [step(8, outside)],
            "city": {"name": "Hyderabad"}}


def provider(handler, key=KEY, **kw):
    calls = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    s = Settings(openweather_api_key=key, openweather_base_url="https://owm.test/weather",
                 openweather_forecast_url="https://owm.test/forecast", **kw)
    return WeatherProvider(s, httpx.MockTransport(wrapped)), calls


def routed(current=CURRENT_OK, forecast=None, forecast_status=200):
    """Handler that answers /weather and /forecast separately, like the real API does."""
    def handler(req):
        if req.url.path.endswith("/forecast"):
            if forecast_status != 200:
                return httpx.Response(forecast_status, json={"message": "x"})
            return httpx.Response(200, json=forecast)
        return httpx.Response(200, json=current)
    return handler


def parse(payload):
    return WeatherProvider.parse_forecast(httpx.Response(200, content=json.dumps(payload).encode()))


def fetch_forecast(handler, **kw):
    prov, calls = provider(handler)
    return prov.fetch_forecast(17.385, 78.4867, **kw), calls, prov


# ── A. provider: fetch + parse ────────────────────────────────────────────────────────────────────

def test_fetch_forecast_parses_steps_and_uses_forecast_endpoint():
    fc, calls, prov = fetch_forecast(lambda r: httpx.Response(200, json=forecast_payload([1.5, None, 4.0, None, None, 2.5, None, None])))
    assert len(calls) == 1 and calls[0].url.path == "/forecast"
    q = dict(calls[0].url.params)
    assert q["lat"] == "17.385" and q["lon"] == "78.4867" and q["units"] == "metric" and q["cnt"] == "9"
    assert len(fc.steps) == 9 and fc.step_hours == 3
    assert [s.rain_mm for s in fc.steps[:8]] == [1.5, 0.0, 4.0, 0.0, 0.0, 2.5, 0.0, 0.0]
    assert fc.steps[0].timestamp == FIRST_STEP and fc.steps[0].pop == 0.3
    assert [s.assumed_dry for s in fc.steps[:8]] == [False, True, False, True, True, False, True, True]
    assert KEY not in json.dumps(prov.last_forecast_payload)


def test_steps_are_sorted_and_cnt_follows_steps_argument():
    payload = forecast_payload([1.0] * 8)
    payload["list"].reverse()
    fc, calls, _ = fetch_forecast(lambda r: httpx.Response(200, json=payload), steps=4)
    assert dict(calls[0].url.params)["cnt"] == "4"
    assert [s.timestamp for s in fc.steps] == sorted(s.timestamp for s in fc.steps)


def test_current_weather_still_uses_current_endpoint_and_is_not_a_forecast():
    prov, calls = provider(lambda r: httpx.Response(200, json=CURRENT_OK))
    pw = prov.fetch_current(17.385, 78.4867)
    assert calls[0].url.path == "/weather" and "cnt" not in calls[0].url.params
    assert pw.rainfall == 0.4 and prov.last_forecast_payload is None


def test_omitted_rain_is_a_dry_step_only_when_pop_proves_the_entry_is_complete():
    fc = parse({"list": [step(0, None, pop=0.0)]})
    assert fc.steps[0].rain_mm == 0.0 and fc.steps[0].assumed_dry is True
    with pytest.raises(AppError) as e:                     # no rain AND no pop: cannot tell dry from truncated
        parse({"list": [{"dt": _ts(FIRST_STEP), "main": {"temp": 28}}]})
    assert e.value.code == "forecast_incomplete_data"


@pytest.mark.parametrize("entry,code", [
    ({"rain": {}}, "forecast_incomplete_data"),              # rain object without a 3h value
    ({"rain": {"1h": 2.0}}, "forecast_incomplete_data"),     # wrong accumulation period is not reinterpreted
    ({"rain": None}, "forecast_incomplete_data"),
    ({"rain": {"3h": None}}, "forecast_incomplete_data"),
    ({"rain": {"3h": "heavy"}}, "forecast_invalid_data"),
    ({"rain": {"3h": -2.0}}, "forecast_invalid_data"),
    ({"rain": {"3h": 900.0}}, "forecast_invalid_data"),
    ({"rain": {"3h": True}}, "forecast_invalid_data"),
    ({"rain": 5.0}, "forecast_incomplete_data"),
    ({"pop": 1.7}, "forecast_invalid_data"),
    ({"pop": "high"}, "forecast_invalid_data"),
    ({"dt": None}, "forecast_incomplete_data"),
    ({"dt": "tomorrow"}, "forecast_invalid_data"),
])
def test_missing_or_invalid_precipitation_discards_whole_forecast(entry, code):
    bad = step(3, 1.0)
    bad.update(entry)
    payload = {"list": [step(0, 1.0), step(1, 1.0), step(2, 1.0), bad]}
    with pytest.raises(AppError) as e:
        parse(payload)
    assert e.value.status_code == 502 and e.value.code == code
    assert e.value.details and e.value.details[0]["index"] == 3


def test_nan_and_infinite_rain_are_rejected():
    for token in ("NaN", "Infinity"):
        raw = ('{"list":[{"dt": %d, "pop": 0.2, "rain": {"3h": %s}}]}' % (_ts(FIRST_STEP), token)).encode()
        with pytest.raises(AppError) as e:
            WeatherProvider.parse_forecast(httpx.Response(200, content=raw))
        assert e.value.code == "forecast_invalid_data"


def test_duplicate_step_times_are_rejected():
    with pytest.raises(AppError) as e:
        parse({"list": [step(0, 1.0), step(0, 2.0)]})
    assert e.value.code == "forecast_invalid_data"


@pytest.mark.parametrize("resp", [
    httpx.Response(200, text="<html>not json</html>"),
    httpx.Response(200, json=["a", "list"]),
    httpx.Response(200, json={"cod": "200"}),                 # e.g. forecast URL pointing at the current-weather API
    httpx.Response(200, json=CURRENT_OK),
    httpx.Response(200, json={"list": "nope"}),
])
def test_invalid_forecast_response_shapes(resp):
    with pytest.raises(AppError) as e:
        WeatherProvider.parse_forecast(resp)
    assert e.value.code == "forecast_bad_response" and e.value.status_code == 502


def test_empty_forecast_list():
    with pytest.raises(AppError) as e:
        parse({"list": []})
    assert e.value.code == "forecast_incomplete_data"


def test_non_object_step_is_invalid():
    with pytest.raises(AppError) as e:
        parse({"list": [step(0, 1.0), "oops"]})
    assert e.value.code == "forecast_invalid_data"


@pytest.mark.parametrize("status,code", [(401, "weather_auth_failed"), (403, "weather_auth_failed"),
                                         (429, "weather_rate_limited"), (500, "weather_provider_error"),
                                         (404, "weather_provider_error")])
def test_forecast_http_errors_use_the_existing_error_codes(status, code):
    prov, _ = provider(lambda r: httpx.Response(status, json={"message": "x"}))
    with pytest.raises(AppError) as e:
        prov.fetch_forecast(17.385, 78.4867)
    assert e.value.code == code and KEY not in e.value.message


def test_forecast_timeout_and_network_errors():
    def timeout(req):
        raise httpx.ConnectTimeout("x", request=req)

    def down(req):
        raise httpx.ConnectError(f"cannot reach {req.url}", request=req)
    with pytest.raises(AppError) as e:
        provider(timeout)[0].fetch_forecast(17.385, 78.4867)
    assert e.value.code == "weather_timeout"
    with pytest.raises(AppError) as e:
        provider(down)[0].fetch_forecast(17.385, 78.4867)
    assert e.value.code == "weather_unavailable" and KEY not in e.value.message


def test_forecast_requires_key_and_valid_coordinates_and_makes_no_request_otherwise():
    prov, calls = provider(lambda r: httpx.Response(200, json=forecast_payload([1.0] * 8)), key=None)
    with pytest.raises(AppError) as e:
        prov.fetch_forecast(17.385, 78.4867)
    assert e.value.code == "weather_not_configured"
    prov, calls = provider(lambda r: httpx.Response(200, json=forecast_payload([1.0] * 8)))
    for lat, lon, code in ((None, 78.0, "coordinates_missing"), (95.0, 78.0, "coordinates_invalid")):
        with pytest.raises(AppError) as e:
            prov.fetch_forecast(lat, lon)
        assert e.value.code == code
    assert calls == []


# ── B. build_forecast_block: provider steps -> scheduler format ───────────────────────────────────

def make_forecast(rains, start=FIRST_STEP, pop=0.4, assumed=()):
    return ProviderForecast([ForecastStep(start + timedelta(hours=3 * i), r, pop, i in assumed)
                             for i, r in enumerate(rains)])


def test_block_matches_the_scheduler_contract_and_documents_units():
    fc = make_forecast([1.5, 0.0, 4.0, 0.0, 0.0, 2.5, 0.0, 0.0] + [50.0], assumed=(1, 3, 4, 6, 7))
    b = build_forecast_block(fc, now=NOW)
    assert b["available"] is True and b["data_kind"] == "forecast"
    assert b["window_hours"] == 24.0 and b["expected_rainfall_mm"] == 8.0   # 9th step (outside window) excluded
    assert b["unit"] == "mm" and b["steps_used"] == 8 and b["step_hours"] == 3
    assert b["assumed_dry_steps"] == 5 and b["max_pop"] == 0.4
    assert b["window_start_utc"] == "2026-10-07T10:40:00" and b["window_end_utc"] == "2026-10-08T10:40:00"
    assert b["last_step_utc"] == "2026-10-08T09:00:00"


def test_block_sum_is_rounded_without_float_noise():
    assert build_forecast_block(make_forecast([0.1, 0.2] + [0.0] * 6), now=NOW)["expected_rainfall_mm"] == 0.3


def test_steps_at_or_before_now_are_not_counted_and_window_end_is_inclusive():
    fc = make_forecast([9.0] + [1.0] * 8, start=NOW - timedelta(hours=1, minutes=40))   # first step 09:00 = past
    b = build_forecast_block(fc, now=NOW)
    # steps 12:00..09:00(+1d) counted (8 steps = 8 mm); the past step is excluded
    assert b["available"] and b["expected_rainfall_mm"] == 8.0


def test_incomplete_window_is_unavailable_not_a_partial_sum():
    b = build_forecast_block(make_forecast([5.0] * 5), now=NOW)
    assert b["available"] is False and b["data_kind"] == "forecast"
    assert b["error_code"] == "forecast_window_incomplete" and "15 h" in b["reason"]
    assert "expected_rainfall_mm" not in b and "window_hours" not in b


def test_forecast_entirely_in_the_past_is_unavailable():
    b = build_forecast_block(make_forecast([5.0] * 9, start=NOW - timedelta(days=2)), now=NOW)
    assert b["available"] is False and "expected_rainfall_mm" not in b


def test_irregular_steps_are_unavailable():
    fc = make_forecast([1.0] * 8)
    fc.steps[4] = ForecastStep(fc.steps[4].timestamp + timedelta(hours=1), 1.0, 0.1)
    b = build_forecast_block(fc, now=NOW)
    assert b["available"] is False and b["error_code"] == "forecast_window_irregular"


def test_custom_window_and_invalid_window():
    b = build_forecast_block(make_forecast([1.0] * 9), now=NOW, window_hours=12)
    assert b["available"] and b["window_hours"] == 12.0 and b["expected_rainfall_mm"] == 4.0
    for bad in (0, -3, 10, 7.5):
        with pytest.raises(ValueError):
            build_forecast_block(make_forecast([1.0] * 9), now=NOW, window_hours=bad)


# ── C. get_field_weather: current + forecast ──────────────────────────────────────────────────────

def run(db, handler, **kw):
    prov, calls = provider(handler)
    kw.setdefault("now", NOW)
    return get_field_weather(db, "F001", provider=prov, **kw), calls


def test_get_field_weather_returns_observation_and_forecast_separately(db, seeded):
    r, calls = run(db, routed(forecast=forecast_payload([1.5, None, 4.0, None, None, 2.5, None, None])))
    assert [c.url.path for c in calls] == ["/weather", "/forecast"]
    assert r.status == "ok" and r.usable_for_prediction
    assert r.observation.data_kind == "current_observation" and r.observation.rainfall_last_1h_mm == 0.4
    fc = r.to_dict()["forecast"]
    assert fc["available"] is True and fc["data_kind"] == "forecast"
    assert fc["expected_rainfall_mm"] == 8.0 and fc["window_hours"] == 24.0
    assert r.to_dict()["data_kind"] == "current_observation"
    # the two kinds of rain are not mixed: observed 0.4 mm/h stays in observation, forecast sum stays in forecast
    assert r.observation.rainfall_last_1h_mm != fc["expected_rainfall_mm"]
    assert KEY not in str(r.to_dict())
    json.dumps(r.to_dict())


def test_forecast_http_error_leaves_current_weather_intact_and_forecast_unavailable(db, seeded):
    r, _ = run(db, routed(forecast_status=500))
    assert r.status == "ok" and r.usable_for_prediction and r.observation is not None
    fc = r.forecast
    assert fc["available"] is False and fc["data_kind"] == "forecast" and fc["error_code"] == "weather_provider_error"
    assert "expected_rainfall_mm" not in fc and "window_hours" not in fc      # no zero / default substituted


@pytest.mark.parametrize("bad_forecast,code", [
    ({"cod": "200"}, "forecast_bad_response"),
    ({"list": []}, "forecast_incomplete_data"),
    ({"list": [step(i, -1.0 if i == 2 else 1.0) for i in range(9)]}, "forecast_invalid_data"),
    ({"list": [step(i, 1.0) for i in range(3)]}, "forecast_window_incomplete"),   # valid but covers only 9 h
])
def test_bad_forecast_payloads_never_become_zero_rain(db, seeded, bad_forecast, code):
    r, _ = run(db, routed(forecast=bad_forecast))
    assert r.status == "ok"
    assert r.forecast["available"] is False and r.forecast["error_code"] == code
    assert "expected_rainfall_mm" not in r.forecast


def test_forecast_timeout_is_contained(db, seeded):
    def handler(req):
        if req.url.path.endswith("/forecast"):
            raise httpx.ConnectTimeout("x", request=req)
        return httpx.Response(200, json=CURRENT_OK)
    r, _ = run(db, handler)
    assert r.status == "ok" and r.forecast["available"] is False and r.forecast["error_code"] == "weather_timeout"


def test_unexpected_forecast_exception_is_contained(db, seeded, monkeypatch):
    def explode(self, *a, **k):
        raise RuntimeError(f"secret {KEY}")
    monkeypatch.setattr(WeatherProvider, "fetch_forecast", explode)
    r, _ = run(db, routed(forecast=forecast_payload([1.0] * 8)))
    assert r.status == "ok" and r.forecast["error_code"] == "forecast_unexpected_error"
    assert KEY not in str(r.to_dict())


def test_forecast_not_requested_when_disabled(db, seeded):
    r, calls = run(db, routed(forecast=forecast_payload([1.0] * 8)), include_forecast=False)
    assert [c.url.path for c in calls] == ["/weather"]
    assert r.forecast["available"] is False and r.forecast["error_code"] == "forecast_not_requested"


def test_forecast_not_requested_for_stale_current_weather(db, seeded):
    r, calls = run(db, routed(forecast=forecast_payload([1.0] * 8)), now=OBSERVED + timedelta(hours=5))
    assert r.status == "stale" and [c.url.path for c in calls] == ["/weather"]
    assert r.forecast["available"] is False and "stale" in r.forecast["reason"]


def test_forecast_not_requested_in_mock_mode(db, seeded):
    prov, calls = provider(routed(forecast=forecast_payload([1.0] * 8)), weather_mock=True)
    r = get_field_weather(db, "F001", provider=prov)
    assert r.status == "mock" and calls == []
    assert r.forecast["available"] is False and "mock" in r.forecast["reason"]


def test_forecast_not_requested_when_live_fetch_failed_and_stored_row_is_used(db, seeded):
    run(db, routed(forecast=forecast_payload([1.0] * 8)))        # stores one real observation
    def current_down(req):
        raise httpx.ConnectTimeout("x", request=req)
    r, calls = run(db, current_down, now=OBSERVED + timedelta(minutes=30))
    assert r.data_origin == "stored_observation" and [c.url.path for c in calls] == ["/weather"]
    assert r.forecast["available"] is False and r.forecast["error_code"] == "forecast_not_requested"


def test_invalid_forecast_window_hours_does_not_call_the_api(db, seeded):
    r, calls = run(db, routed(forecast=forecast_payload([1.0] * 8)), forecast_window_hours=10)
    assert [c.url.path for c in calls] == ["/weather"]
    assert r.status == "ok" and r.forecast["error_code"] == "forecast_window_invalid"


def test_current_weather_failure_is_unchanged_and_requests_no_forecast(db, seeded):
    r, calls = run(db, lambda req: httpx.Response(500, json={}))
    assert r.status == "unavailable" and r.error["code"] == "weather_provider_error"
    assert [c.url.path for c in calls] == ["/weather"]
    assert r.forecast["available"] is False


# ── D. scheduler on the adapter's real output ─────────────────────────────────────────────────────

def schedule_for(db, rains, predicted=20.0, **kw):
    r, _ = run(db, routed(forecast=forecast_payload(rains)), **kw)
    return r, generate_irrigation_schedule(predicted, r, FIELD, now=NOW)


def test_heavy_forecast_rain_defers_and_keeps_prediction(db, seeded):
    r, s = schedule_for(db, [2.0] * 8)                      # 16 mm in the next 24 h
    assert r.forecast["expected_rainfall_mm"] == 16.0
    assert s.action == ACTION_DEFER and s.reason_codes == ["forecast_rain"]
    assert s.predicted_irrigation_mm == 20.0 and s.recommended_irrigation_mm == 0.0
    assert s.reevaluate_after_hours == 24.0
    assert s.weather_context["forecast"]["usable"] is True


def test_forecast_rain_exactly_at_threshold_defers_and_just_below_does_not(db, seeded):
    assert schedule_for(db, [1.25] * 8)[1].action == ACTION_DEFER         # 10.0 mm
    assert schedule_for(db, [1.2] * 8)[1].action == ACTION_IRRIGATE       # 9.6 mm


def test_light_forecast_rain_does_not_defer_or_reduce_the_prediction(db, seeded):
    r, s = schedule_for(db, [0.5] * 8)                       # 4 mm
    assert s.action == ACTION_IRRIGATE and s.recommended_irrigation_mm == 20.0
    assert s.volume["litres"] == 200000.0


def test_dry_forecast_irrigates_and_reports_assumed_dry_steps(db, seeded):
    r, s = schedule_for(db, [None] * 8)
    assert r.forecast["expected_rainfall_mm"] == 0.0 and r.forecast["assumed_dry_steps"] == 8
    assert s.action == ACTION_IRRIGATE


def test_rain_outside_the_window_is_ignored(db, seeded):
    # the forecast_payload helper puts 50 mm in the 9th step (just outside the 24 h window): must not cause a deferral
    assert schedule_for(db, [0.0] * 8)[1].action == ACTION_IRRIGATE


def test_forecast_failure_is_not_treated_as_dry_or_wet(db, seeded):
    r, _ = run(db, routed(forecast_status=500))
    s = generate_irrigation_schedule(20.0, r, FIELD, now=NOW)
    assert s.action == ACTION_IRRIGATE and s.recommended_irrigation_mm == 20.0
    assert s.weather_context["forecast"]["available"] is False
    assert s.weather_context["forecast"].get("expected_rainfall_mm") is None
    assert any(w.startswith("Forecast not used") for w in s.warnings)


def test_current_heavy_rain_still_takes_precedence_over_forecast(db, seeded):
    heavy_now = dict(CURRENT_OK, rain={"1h": 6.0})
    r, _ = run(db, routed(current=heavy_now, forecast=forecast_payload([0.0] * 8)))
    s = generate_irrigation_schedule(20.0, r, FIELD, now=NOW)
    assert s.action == ACTION_DEFER and s.reason_codes == ["rain_in_last_hour"]