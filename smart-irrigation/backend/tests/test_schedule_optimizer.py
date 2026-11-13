"""Unit tests for app.services.schedule_optimizer (pure logic, fixed clock)."""
from datetime import datetime, timedelta, timezone

from app.services.schedule_optimizer import DEFAULT_RATE_MM_PER_H, PlanConfig, plan_irrigation, resolve_rate

UTC = timezone.utc
# 07:30 IST on a Saturday (inside the 05:00-09:00 morning window)
MORNING = datetime(2026, 10, 31, 2, 0, tzinfo=UTC)
# 12:30 IST (midday, outside every normal window)
MIDDAY = datetime(2026, 10, 31, 7, 0, tzinfo=UTC)


def plan(**kw):
    kw.setdefault("action", "IRRIGATE")
    kw.setdefault("depth_mm", 12.0)
    kw.setdefault("now_utc", MORNING)
    kw.setdefault("rate_mm_per_hour", 6.0)
    return plan_irrigation(**kw)


def test_depth_is_split_across_windows_and_totals_match():
    p = plan()                                   # 12 mm at 6 mm/h = 2 h; only 1.5 h left in the morning window
    assert p["status"] == "SCHEDULED"
    assert [s["window"] for s in p["slots"]] == ["MORNING", "EVENING"]
    assert p["slots"][0]["start_local"].startswith("2026-10-31T07:30") and p["slots"][0]["duration_min"] == 90
    assert p["slots"][1]["start_local"].startswith("2026-10-31T17:00") and p["slots"][1]["duration_min"] == 30
    assert abs(p["total_depth_mm"] - 12.0) < 0.05 and p["total_duration_min"] == 120
    assert p["rate_assumed"] is False and p["emergency"] is False


def test_midday_request_waits_for_the_evening_window():
    p = plan(now_utc=MIDDAY, depth_mm=6.0)
    assert p["slots"][0]["window"] == "EVENING" and p["slots"][0]["start_local"].startswith("2026-10-31T17:00")


def test_emergency_starts_immediately_even_at_midday_and_caps_session_length():
    p = plan(now_utc=MIDDAY, depth_mm=30.0, emergency=True)   # 5 h of work, sessions capped at 4 h
    first = p["slots"][0]
    assert first["window"] == "IMMEDIATE" and first["start_local"].startswith("2026-10-31T12:30") and first["duration_min"] == 240
    assert p["slots"][1]["window"] == "EVENING" and p["slots"][1]["duration_min"] == 60
    assert abs(p["total_depth_mm"] - 30.0) < 0.05
    assert any("EMERGENCY" in w for w in p["warnings"])


def test_emergency_start_is_never_in_the_past():
    now = datetime(2026, 10, 31, 7, 3, 41, tzinfo=UTC)
    p = plan(now_utc=now, emergency=True, depth_mm=3.0)
    assert datetime.fromisoformat(p["slots"][0]["start_utc"]) >= now


def test_non_irrigate_actions_produce_no_plan():
    for action in ("NO_IRRIGATION_NEEDED", "WITHHELD", "DEFER"):
        p = plan(action=action, reevaluate_after_hours=3.0)
        assert p["status"] == "NO_PLAN" and p["slots"] == [] and p["reason"]
    assert plan(action="DEFER", reevaluate_after_hours=3.0)["reevaluate_at_utc"] == "2026-10-31T05:00:00+00:00"


def test_invalid_depth_gives_no_plan():
    for bad in (None, 0, -5, float("nan"), "12", True):
        assert plan(depth_mm=bad)["status"] == "NO_PLAN"


def test_rate_resolution_and_assumed_default_is_labelled():
    cfg = PlanConfig()
    assert resolve_rate("drip", None, cfg)[:2] == (3.0, False)
    assert resolve_rate("Flood", None, cfg)[:2] == (15.0, False)
    assert resolve_rate("drip", 8.0, cfg)[:2] == (8.0, False)              # explicit rate wins
    rate, assumed, warns = resolve_rate(None, None, cfg)
    assert rate == DEFAULT_RATE_MM_PER_H and assumed is True and any("ASSUMED" in w for w in warns)
    assert resolve_rate("laser", None, cfg)[1] is True
    assert resolve_rate(None, -3, cfg)[1] is True and resolve_rate(None, 9999, cfg)[1] is True
    p = plan(rate_mm_per_hour=None)
    assert p["rate_assumed"] is True and p["rate_mm_per_hour"] == DEFAULT_RATE_MM_PER_H


def test_volume_per_slot_uses_the_area():
    p = plan(area_hectares=2.0)
    assert p["slots"][0]["volume_litres"] == round(p["slots"][0]["depth_mm"] * 2.0 * 10_000)


def test_wind_warning_and_horizon_overflow_warning():
    assert any("Wind" in w for w in plan(wind_speed_ms=11.0)["warnings"])
    assert not any("Wind" in w for w in plan(wind_speed_ms=2.0)["warnings"])
    huge = plan(depth_mm=95.0, rate_mm_per_hour=3.0, config=PlanConfig(max_days_ahead=0))   # 32 h of drip in one day
    assert any("unscheduled" in w for w in huge["warnings"]) and huge["total_depth_mm"] < 95.0


def test_slots_never_overlap_and_are_chronological():
    p = plan(depth_mm=60.0, now_utc=MIDDAY, emergency=True)
    for a, b in zip(p["slots"], p["slots"][1:]):
        assert datetime.fromisoformat(a["end_utc"]) <= datetime.fromisoformat(b["start_utc"])
    assert all(s["duration_min"] <= 240 for s in p["slots"])
