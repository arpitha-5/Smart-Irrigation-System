"""Rule-based alert engine (pure logic: no database, no network, no sending).

Input : one soil-moisture reading, a field's thresholds, and sensor timing.
Output: a list of RuleAlert objects describing any problem found.

Keeping this module free of database and notification code makes it easy to test.
Other modules decide what to do with the alerts (store them, send them, etc.).
"""
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class AlertType(str, Enum):
    DROUGHT = "drought"
    OVER_WATERING = "over_watering"
    SENSOR_FAILURE = "sensor_failure"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Thresholds:
    """Per-field limits. Moisture values are volumetric percent (0 to 100)."""
    min_moisture: float
    max_moisture: float
    critical_margin: float = 10.0       # percentage points beyond a limit that count as severe
    sensor_silent_minutes: int = 60     # no data for this long = sensor problem

    def __post_init__(self):
        if not (0 <= self.min_moisture < self.max_moisture <= 100):
            raise ValueError("Thresholds must satisfy 0 <= min < max <= 100")
        if self.critical_margin <= 0:
            raise ValueError("critical_margin must be positive")
        if self.sensor_silent_minutes <= 0:
            raise ValueError("sensor_silent_minutes must be positive")


@dataclass(frozen=True)
class RuleAlert:
    alert_type: AlertType
    severity: Severity
    message: str
    recommended_action: str
    value: Optional[float] = None
    threshold: Optional[float] = None


def _is_valid_moisture(value: Optional[float]) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 100
    )


def evaluate_moisture(moisture: Optional[float], t: Thresholds) -> Optional[RuleAlert]:
    """Check one moisture value against the field's thresholds.

    Returns None when the value is fine, or when it is missing
    (a missing value is a sensor problem, handled by check_sensor_silence).
    """
    if moisture is None:
        return None
    if not _is_valid_moisture(moisture):
        return RuleAlert(
            AlertType.SENSOR_FAILURE, Severity.HIGH,
            "Abnormal soil moisture value received: %r (valid range is 0 to 100)." % (moisture,),
            "Check the sensor and its wiring; readings are not trustworthy until it is fixed.",
            value=None,
        )

    if moisture < t.min_moisture:
        deficit = t.min_moisture - moisture
        if deficit >= t.critical_margin:
            severity = Severity.CRITICAL
        elif deficit >= t.critical_margin / 2:
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM
        return RuleAlert(
            AlertType.DROUGHT, severity,
            "Soil moisture %.1f%% is below the minimum %.1f%%." % (moisture, t.min_moisture),
            "Irrigate this field soon.",
            value=moisture, threshold=t.min_moisture,
        )

    if moisture > t.max_moisture:
        excess = moisture - t.max_moisture
        severity = Severity.HIGH if excess >= t.critical_margin else Severity.MEDIUM
        return RuleAlert(
            AlertType.OVER_WATERING, severity,
            "Soil moisture %.1f%% is above the maximum %.1f%%." % (moisture, t.max_moisture),
            "Pause irrigation and check drainage.",
            value=moisture, threshold=t.max_moisture,
        )
    return None


def check_sensor_silence(last_seen_at: Optional[datetime], now: datetime, t: Thresholds) -> Optional[RuleAlert]:
    """Detect a sensor that has stopped sending data. Times are naive UTC."""
    if last_seen_at is None:
        return RuleAlert(
            AlertType.SENSOR_FAILURE, Severity.MEDIUM,
            "This sensor has never sent a reading.",
            "Check that the sensor is powered, connected and registered correctly.",
        )
    silent_minutes = (now - last_seen_at).total_seconds() / 60
    if silent_minutes < t.sensor_silent_minutes:
        return None
    severity = Severity.HIGH if silent_minutes >= 4 * t.sensor_silent_minutes else Severity.MEDIUM
    return RuleAlert(
        AlertType.SENSOR_FAILURE, severity,
        "No data from this sensor for %d minutes (limit %d)." % (int(silent_minutes), t.sensor_silent_minutes),
        "Check the sensor's power and connection.",
        value=float(int(silent_minutes)), threshold=float(t.sensor_silent_minutes),
    )


def evaluate_reading(moisture: Optional[float], last_seen_at: Optional[datetime],
                     now: datetime, t: Thresholds) -> List[RuleAlert]:
    """Run all rules for one sensor and return every alert found."""
    alerts: List[RuleAlert] = []
    moisture_alert = evaluate_moisture(moisture, t)
    if moisture_alert:
        alerts.append(moisture_alert)
    silence_alert = check_sensor_silence(last_seen_at, now, t)
    if silence_alert:
        alerts.append(silence_alert)
    return alerts
