"""Time-slotted irrigation plan: turns a depth (mm) into start times and durations.

Pure Python: no database, HTTP or ML imports. The plan is ADVISORY and only produced for action IRRIGATE.

Rules (all thresholds are proposals in ``PlanConfig``; see docs/ml_irrigation_model.md):
  * Duration = depth / application rate. The rate comes from the request (``application_rate_mm_per_hour`` or an
    ``irrigation_method``); if neither is given a labelled DEFAULT is used and the plan says so (``rate_assumed``).
  * Normal plans use cool, low-wind hours: morning 05:00-09:00 and evening 17:00-20:00 LOCAL time; midday is avoided
    because more water evaporates.
  * Sessions are at most ``max_session_hours`` long (long single runs cause runoff); long jobs span several windows/days.
  * EMERGENCY plans start immediately (next 5 minutes) regardless of the hour, then continue in normal windows.
  * Local time is ``UTC + utc_offset_hours`` (default +5.5, India); the field's real time zone is not stored.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

METHOD_RATES_MM_PER_H: Dict[str, float] = {"drip": 3.0, "sprinkler": 6.0, "flood": 15.0}  # same table as the data generator
DEFAULT_RATE_MM_PER_H = METHOD_RATES_MM_PER_H["sprinkler"]


@dataclass(frozen=True)
class PlanConfig:
    utc_offset_hours: float = 5.5
    morning_window: Tuple[float, float] = (5.0, 9.0)
    evening_window: Tuple[float, float] = (17.0, 20.0)
    max_session_hours: float = 4.0
    min_session_minutes: int = 10
    max_days_ahead: int = 3
    wind_warning_ms: float = 8.0
    max_rate_mm_per_h: float = 100.0


def _positive(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        return None
    return float(v)


def _round_up(dt: datetime, minutes: int = 5) -> datetime:
    """Next multiple of ``minutes`` at or after ``dt`` (never earlier than ``dt``)."""
    floored = dt.replace(second=0, microsecond=0)
    if floored < dt:
        floored += timedelta(minutes=1)
    return floored + timedelta(minutes=(-floored.minute) % minutes)


def resolve_rate(method: Optional[str], rate: Any, cfg: PlanConfig) -> Tuple[float, bool, List[str]]:
    """(rate mm/h, assumed?, warnings). An explicit valid rate wins; then the method; otherwise a labelled default."""
    warnings: List[str] = []
    explicit = _positive(rate)
    if explicit is not None:
        if explicit > cfg.max_rate_mm_per_h:
            warnings.append(f"application_rate_mm_per_hour {explicit:g} is implausibly high; using the default instead.")
        else:
            return explicit, False, warnings
    elif rate is not None:
        warnings.append("application_rate_mm_per_hour must be a positive number; ignored.")
    m = method.strip().lower() if isinstance(method, str) else None
    if m in METHOD_RATES_MM_PER_H:
        return METHOD_RATES_MM_PER_H[m], False, warnings
    if method:
        warnings.append(f"Unknown irrigation_method {method!r} (known: {', '.join(METHOD_RATES_MM_PER_H)}); using the default.")
    warnings.append(f"No irrigation method or application rate was given, so {DEFAULT_RATE_MM_PER_H:g} mm/h "
                    "(sprinkler-class) is ASSUMED. Durations are only as accurate as this rate; supply "
                    "irrigation_method or application_rate_mm_per_hour.")
    return DEFAULT_RATE_MM_PER_H, True, warnings


def _windows(now_utc: datetime, cfg: PlanConfig) -> List[Tuple[str, datetime, datetime]]:
    tz = timezone(timedelta(hours=cfg.utc_offset_hours))
    local_now = now_utc.astimezone(tz)
    out = []
    for day in range(cfg.max_days_ahead + 1):
        base = (local_now + timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)
        for label, (h0, h1) in (("MORNING", cfg.morning_window), ("EVENING", cfg.evening_window)):
            out.append((label, base + timedelta(hours=h0), base + timedelta(hours=h1)))
    return [w for w in out if w[2] > local_now]


def plan_irrigation(*, action: str, depth_mm: Optional[float], now_utc: Optional[datetime] = None, emergency: bool = False,
                    method: Optional[str] = None, rate_mm_per_hour: Any = None, wind_speed_ms: Optional[float] = None,
                    area_hectares: Optional[float] = None, reevaluate_after_hours: Optional[float] = None,
                    config: Optional[PlanConfig] = None) -> Dict[str, Any]:
    """Return {status, slots, ...}. status: SCHEDULED | NO_PLAN. Never raises for bad input."""
    cfg = config or PlanConfig()
    now = (now_utc or datetime.now(timezone.utc))
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    tz = timezone(timedelta(hours=cfg.utc_offset_hours))
    base: Dict[str, Any] = {"status": "NO_PLAN", "slots": [], "emergency": bool(emergency), "total_depth_mm": 0.0,
                            "total_duration_min": 0, "rate_mm_per_hour": None, "rate_assumed": None, "warnings": [],
                            "utc_offset_hours": cfg.utc_offset_hours, "reason": None,
                            "generated_at_utc": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
                            "reevaluate_at_utc": None}
    if action == "DEFER" and reevaluate_after_hours:
        base["reevaluate_at_utc"] = (now + timedelta(hours=reevaluate_after_hours)).astimezone(timezone.utc).isoformat(timespec="seconds")
    if action != "IRRIGATE":
        base["reason"] = {"DEFER": "Irrigation is deferred; re-evaluate with fresh weather.",
                          "NO_IRRIGATION_NEEDED": "No irrigation is needed.",
                          "WITHHELD": "No recommendation could be made, so nothing is scheduled."}.get(action, "No irrigation to schedule.")
        return base
    depth = _positive(depth_mm)
    if depth is None:
        base["reason"] = "No positive depth to schedule."
        return base

    rate, assumed, warns = resolve_rate(method, rate_mm_per_hour, cfg)
    base["warnings"].extend(warns)
    base.update(rate_mm_per_hour=rate, rate_assumed=assumed)
    wind = _positive(wind_speed_ms)
    if wind is not None and wind >= cfg.wind_warning_ms:
        base["warnings"].append(f"Wind is {wind:g} m/s: sprinkler drift and uneven coverage are likely; prefer a calmer slot or drip.")

    remaining_h = depth / rate
    slots: List[Dict[str, Any]] = []

    def add(label: str, start_local: datetime, hours: float) -> float:
        hours = min(hours, cfg.max_session_hours, remaining_h)
        if hours * 60 < cfg.min_session_minutes and hours < remaining_h:
            return 0.0
        end_local = start_local + timedelta(hours=hours)
        mm = hours * rate
        slot = {"window": label, "start_local": start_local.isoformat(timespec="minutes"), "end_local": end_local.isoformat(timespec="minutes"),
                "start_utc": start_local.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "end_utc": end_local.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "duration_min": int(round(hours * 60)), "depth_mm": round(mm, 2)}
        if area_hectares and _positive(area_hectares):
            slot["volume_litres"] = round(mm * float(area_hectares) * 10_000)
        slots.append(slot)
        return hours

    cursor_utc = now
    if emergency:
        start = _round_up(now).astimezone(tz)
        used = add("IMMEDIATE", start, remaining_h)
        remaining_h -= used
        cursor_utc = start.astimezone(timezone.utc) + timedelta(hours=used)
        base["warnings"].append("EMERGENCY: the first session starts now regardless of the hour. Midday watering loses more water "
                                "to evaporation, but protecting the crop takes priority.")
    for label, w0, w1 in _windows(cursor_utc, cfg):
        if remaining_h <= 1e-9:
            break
        start = max(w0, _round_up(cursor_utc).astimezone(tz))
        room_h = (w1 - start).total_seconds() / 3600.0
        if room_h * 60 < cfg.min_session_minutes:
            continue
        used = add(label, start, min(room_h, remaining_h))
        remaining_h -= used
        if used:
            cursor_utc = start.astimezone(timezone.utc) + timedelta(hours=used)
    if remaining_h > 1e-6:
        base["warnings"].append(f"Only part of the depth fits in the next {cfg.max_days_ahead} days of irrigation windows; "
                                f"{remaining_h * rate:.1f} mm remain unscheduled. Re-run the plan later.")
    scheduled = sum(s["depth_mm"] for s in slots)
    base.update(status="SCHEDULED" if slots else "NO_PLAN", slots=slots, total_depth_mm=round(scheduled, 2),
                total_duration_min=int(sum(s["duration_min"] for s in slots)),
                reason=None if slots else "No irrigation window is available in the planning horizon.")
    return base
