# Irrigation Scheduling Logic (Weather Integration & Scheduling)

This document describes the rules implemented in `backend/app/services/irrigation_scheduler.py`, the weather
input produced by `backend/app/services/weather_adapter.py`, and how both are exposed through the existing
irrigation endpoints. It is derived from the code; if the code and this file disagree, the code is authoritative.

The output is **advisory**. It is rule-based, not guaranteed to be agronomically correct, and must be checked against
soil, crop stage, emitter/flow rate and local conditions before any water is applied.

---

## 1. Purpose and design rules

The scheduler decides **whether to apply an already-computed irrigation depth now**. It does not compute the depth.

- Pure Python: no database, HTTP or ML imports. It never calls the weather API and never loads a model.
- The depth it receives is **never re-categorised and never modified**. Rainfall is **not subtracted** from it.
  Rain only decides between applying the depth (`IRRIGATE`), holding it back (`DEFER`) or making no
  recommendation (`WITHHELD`).
- Nothing is fabricated. Missing, invalid, stale or simulated weather gives `WITHHELD` with a reason and
  `recommended_irrigation_mm = null`. No default weather values are ever substituted.
- Unit: millimetres of water **depth** over the field surface (1 mm = 1 L per m²).
  A volume in litres is reported only when a valid `area_hectares` is available (1 mm over 1 ha = 10,000 L).
- `generate_irrigation_schedule()` never raises for bad data; it returns `WITHHELD` with reasons.

## 2. Inputs

`generate_irrigation_schedule(predicted_irrigation_mm, weather_data, field_data, *, config=None, now=None)`

| Input | Meaning |
|---|---|
| `predicted_irrigation_mm` | Irrigation depth in mm for one event. Must be a finite, non-negative number not above the plausibility ceiling. |
| `weather_data` | A `FieldWeatherResult` from `weather_adapter.get_field_weather()` (or its `to_dict()`). |
| `field_data` | Mapping/object with `field_id` (required) and `area_hectares` (optional). Taken from the `Field` model. |

### Source of the depth in the API

In the current API the depth comes from one of three sources, and every response states which in `schedule_input`:

| `schedule_input.source` | `is_ml_prediction` | When |
|---|---|---|
| `ml_model` | true | The trained model ran (supported crop, crop record with a planting date, soil-moisture reading under 24 h old or a manual value). Depth = the model's **gross** applied depth. See `docs/ml_irrigation_model.md`. |
| `rule_based_recommendation` | false | The ML model could not run (reason in `ml_prediction.reason`), or ML is disabled. Depth = `recommended_water_mm` from the existing FAO-56 style engine. |
| `rule_based_emergency_override` | false | EMERGENCY alert (soil critically dry) while the model advised no irrigation: the rule-based depth is used as a safety net. |

The scheduler itself is unchanged and is told nothing about the source: it receives one depth in mm and never modifies it.

## 3. Decision order

Rules are evaluated in this order and the first match wins.

1. **Prediction check** – missing / non-numeric / NaN → `WITHHELD`; negative → `WITHHELD` (not clipped to 0);
   above the plausibility ceiling → `WITHHELD` (not clipped).
2. **Field check** – no usable `field_id` → `WITHHELD` (`field_data_invalid`).
3. **Zero depth** – exactly `0` → `NO_IRRIGATION_NEEDED`, whatever the weather says. If weather was unusable a warning
   notes that it was not used.
4. **Weather gate** – weather must be usable (section 5), otherwise `WITHHELD` with the weather reason.
5. **R1, observed rain** – rain in the last hour ≥ threshold → `DEFER`.
6. **R2, forecast rain** – a valid, correctly labelled forecast with window ≤ max window and expected rain ≥ threshold → `DEFER`.
7. **Otherwise** → `IRRIGATE` with the depth exactly as given.

### Actions

| Action | `recommended_irrigation_mm` | Meaning |
|---|---|---|
| `IRRIGATE` | the input depth, unchanged | No hold rule applies. Volume is added if the area is valid. |
| `DEFER` | `0.0` | Rain-based hold. `predicted_irrigation_mm` still shows the unchanged input. `reevaluate_after_hours` is set. |
| `NO_IRRIGATION_NEEDED` | `0.0` | The input depth was exactly 0 mm. |
| `WITHHELD` | `null` | No safe recommendation (see `reason_codes`). The caller decides whether to act on the raw depth. |

## 4. Thresholds and defaults

These defaults are **proposals for team review** (`ScheduleConfig` and `weather_adapter` constants). Change them
only with agreement, and update this table.

| Setting | Default | Where | Rationale / effect |
|---|---|---|---|
| `defer_if_rain_last_1h_mm` | 2.5 mm | `ScheduleConfig` | Lower bound of "moderate" rain intensity (light rain is < 2.5 mm/h). At or above → `DEFER`. |
| `defer_if_forecast_rain_mm` | 10.0 mm | `ScheduleConfig` | Forecast rain inside the window at or above this → `DEFER`. |
| `max_forecast_window_hours` | 24 h | `ScheduleConfig` | Forecast windows longer than this are ignored (a warning is added). |
| `reevaluate_after_rain_hours` | 3 h | `ScheduleConfig` | Suggested re-run delay after an observed-rain `DEFER`. After a forecast `DEFER` it equals the forecast window. |
| `max_plausible_irrigation_mm` | 100 mm | `ScheduleConfig` | Larger inputs are withheld as probable unit/model errors. |
| `small_depth_warning_mm` | 1 mm | `ScheduleConfig` | Smaller depths get a "may not be practical to apply" warning; the value is kept. |
| `DEFAULT_MAX_OBSERVATION_AGE_MINUTES` | 180 min | `weather_adapter` | Older real observations are `stale`. |
| `FUTURE_TOLERANCE_MINUTES` | 5 min | `weather_adapter` | Observations dated further in the future are rejected. |
| `DEFAULT_FORECAST_WINDOW_HOURS` | 24 h | `weather_adapter` | Forecast window requested after a fresh live observation. Must be a multiple of 3. |

Light rain below the observed-rain threshold does **not** reduce the depth; a warning states this.

The response field `thresholds` echoes only four of these values (`defer_if_rain_last_1h_mm`, `defer_if_forecast_rain_mm`,
`max_forecast_window_hours`, `max_plausible_irrigation_mm`); `reevaluate_after_rain_hours` and `small_depth_warning_mm`
are not echoed. `ScheduleConfig` rejects any non-positive, non-finite or non-numeric value with `ValueError`.

## 5. Weather input and safety rules

`weather_adapter.get_field_weather(db, field_id)` reuses the existing stack (field registry, `WeatherProvider`,
`weather_data` table, data-cleaning validation). It adds no endpoint, table or API client and never raises for
weather problems.

| Adapter `status` | Meaning | Usable | Scheduler result (depth > 0) |
|---|---|---|---|
| `ok` | Real, complete, fresh observation | yes | rules R1/R2 are evaluated |
| `stale` | Real observation older than the max age | no | `WITHHELD` – `weather_stale` |
| `mock` | Synthetic data (`WEATHER_MOCK=true`) | no | `WITHHELD` – `weather_mock` |
| `unavailable` | Timeout, no API key, bad/missing values, unknown field, future timestamp… | no | `WITHHELD` – `weather_unavailable` |

Further gates in the scheduler: missing weather → `weather_missing`; no `status` → `weather_malformed`; status `ok`
without a real observation → `weather_malformed`; missing/negative `rainfall_last_1h_mm` → `weather_values_invalid`.

If the live call fails, the adapter may fall back to the latest **real stored** observation; it is labelled
`data_origin = "stored_observation"`, still must pass the staleness check, and no forecast is requested for it.

### Observed rainfall vs forecast rainfall

These are never mixed.

- **Observed:** `observation.rainfall_last_1h_mm`, `data_kind = "current_observation"`. It is the provider's rain in the
  *last hour* (mm); it says nothing about daily totals.
- **Forecast:** a separate `forecast` block, `data_kind = "forecast"`, built from the OpenWeatherMap 5-day/3-hour
  forecast. `expected_rainfall_mm` is the **sum of the 3-hour rain volumes inside the window** (mm over the whole
  window, not mm/h). It is not reduced by probability of precipitation, and snow is not included.
- The forecast is requested only after a fresh, real, **live** current observation.
- The window `(now, now + window]` must be **completely and regularly** covered (e.g. 8 consecutive 3-hour steps for
  24 h). Otherwise the forecast is `available: false` with a reason; a partial sum is never used.
- A missing, failed, partial or invalid forecast is **never** treated as 0 mm. The scheduler then decides on the
  current observation alone and adds the warning `Forecast not used: …`.
- If the observed-rain rule (R1) already defers, a forecast that cannot be used still adds the `Forecast not used: …` warning. If the forecast
  is usable but its window is longer than `max_forecast_window_hours`, it is ignored with a warning (only when R1 did not fire).
- A forecast step the provider reported without a `rain` value counts as 0 mm only when the entry was otherwise complete
  (it has `pop`); the number of such steps is reported as `assumed_dry_steps`.
- The provider's `dt` is treated as the step time. The first step may include up to 3 h of rain that has already
  fallen, which can only make deferral more likely, never hide forecast rain.

## 6. Volume

Calculated only when `action = IRRIGATE` **and** `area_hectares` is a finite number > 0:

```
litres = recommended_irrigation_mm × area_hectares × 10,000
```

Example: 35 mm on 1.5 ha = 35 × 1.5 × 10,000 = 525,000 L (525 m³). This assumes the whole registered area is irrigated
uniformly with no application-efficiency losses. With a missing, zero or negative area the depth is reported in mm
only, `volume` is `null`, and a warning is added.

## 7. Reason codes

| Code | Result | Meaning |
|---|---|---|
| `prediction_missing` / `prediction_invalid` | WITHHELD | No usable number supplied |
| `prediction_negative` | WITHHELD | Negative depth (not clipped) |
| `prediction_implausible` | WITHHELD | Above the plausibility ceiling (not clipped) |
| `field_data_invalid` | WITHHELD | No usable `field_id` |
| `prediction_zero` | NO_IRRIGATION_NEEDED | Depth is exactly 0 mm |
| `weather_missing` / `weather_malformed` / `weather_values_invalid` | WITHHELD | Weather absent or unusable |
| `weather_unavailable` / `weather_stale` / `weather_mock` / `weather_not_usable` | WITHHELD | Weather status not usable |
| `rain_in_last_hour` | DEFER | R1 (observed rain) |
| `forecast_rain` | DEFER | R2 (forecast rain) |
| `no_deferral_rule_met` | IRRIGATE | No hold rule applies |

## 8. API integration

No separate scheduler endpoint exists. The scheduler is part of the existing irrigation workflow:

- `POST /recommendations/irrigation`
- `GET  /recommendations/irrigation/{field_id}`

Flow: `recommend_irrigation()` (unchanged) → `get_field_weather()` → `generate_irrigation_schedule()` →
three **additional, optional** response fields. All pre-existing fields keep their names, types and values.

| Field | Content |
|---|---|
| `irrigation_schedule` | Scheduler output (action, depths, volume, reasons, warnings, weather context, thresholds, assumptions). `null` when no schedule could be produced. |
| `schedule_input` | Provenance of the depth: `source`, `is_ml_prediction`, `predicted_irrigation_mm`, `recommendation_engine`. |
| `ml_prediction` | What the trained model said (`irrigate`, `probability`, `depth_mm`, warnings), or `available: false` with the reason. |
| `irrigation_plan` | Time slots (start, duration, depth) when the action is IRRIGATE. |
| `alerts` | Rule-based EMERGENCY / WARNING / INFO alerts. |
| `scheduling_note` | Why `irrigation_schedule` is `null` (no `field_id`, field not registered, or an unexpected scheduling error). |

Notes:

- A schedule requires a registered field, because weather is looked up by the field's coordinates and the volume uses
  the field's `area_hectares`. Requests without a registered `field_id` still return the normal recommendation.
- Each call for a registered field triggers a live weather (and forecast) request and stores a `weather_data` row.
- An unexpected scheduling error never removes the recommendation; it yields `irrigation_schedule = null` and a note.

### Two different `action` fields: which one is the final decision?

A response carries two actions. They answer different questions and use different vocabularies.

| | Top-level `action` | `irrigation_schedule.action` |
|---|---|---|
| Produced by | `irrigation_service.recommend_irrigation()` (existing rule-based engine, unchanged) | `irrigation_scheduler.generate_irrigation_schedule()` |
| Values | `IRRIGATE_IMMEDIATELY`, `IRRIGATE_LIGHT`, `MAINTAIN_MONITORING`, `DEFER_DUE_TO_RAIN` | `IRRIGATE`, `DEFER`, `NO_IRRIGATION_NEEDED`, `WITHHELD` |
| Based on | Soil-moisture deficit against crop/stage thresholds, plus rainfall numbers (see below) | A depth from the ML model (or the engine's `recommended_water_mm` as fallback), plus a validated current observation and forecast from `weather_adapter` |
| Weather source | `recent_rainfall_mm` / `forecast_rainfall_mm` from the request; for a registered field, `recent_rainfall_mm` falls back to the latest *stored* `weather_data` row when the request value is missing or 0 (no age check). `forecast_rainfall_mm` only ever comes from the request (default 0). | Live observation (rain in the last hour) and 24 h forecast, with staleness / mock / unavailable checks |
| Rain thresholds | `recent_rainfall_mm >= 12` mm → defer; `forecast_rainfall_mm >= 8` mm **and** moisture deficit `< 10` (percentage points) → defer | Section 4: 2.5 mm in the last hour, 10 mm forecast within 24 h |

**Final weather-aware decision: `irrigation_schedule.action`, whenever `irrigation_schedule` is not `null`.** It is the only
action that checks live weather and the only one that carries the scheduled depth and water volume. When
`irrigation_schedule` is `null` (no `field_id`, unregistered field, or a contained scheduling error), no weather-aware
decision exists: only the top-level action is available, it is not weather-verified, and `scheduling_note` says why.

How the two combine when the **rule-based** depth is used (the ML model, when it runs, replaces the depth, so the table's first column is then only context):

| Top-level `action` | `recommended_water_mm` | Possible `irrigation_schedule.action` |
|---|---|---|
| `IRRIGATE_IMMEDIATELY` | always > 0 (5-35 mm) | `IRRIGATE`, `DEFER` (rain rules), or `WITHHELD` (weather not usable) |
| `IRRIGATE_LIGHT` | usually > 0 | same as above |
| `IRRIGATE_LIGHT` with a tiny deficit | can round to `0.0` | `NO_IRRIGATION_NEEDED` |
| `DEFER_DUE_TO_RAIN` | `0.0` | `NO_IRRIGATION_NEEDED` (`prediction_zero`) |
| `MAINTAIN_MONITORING` | `0.0` | `NO_IRRIGATION_NEEDED` (`prediction_zero`) |

Consequences to be aware of:

- The schedule can only turn a "water" recommendation into `DEFER` or `WITHHELD`; it never turns a 0 mm engine result
  into watering.
- When the engine itself deferred for rain, the schedule reports `NO_IRRIGATION_NEEDED` with reason code `prediction_zero`
  (the weather is not evaluated; a warning is added if it was unusable). The "deferred because of rain" explanation
  therefore appears only in the top-level `action` / `reason`. The reason text says "The model predicts 0 mm" even though
  the depth comes from the rule-based engine.
- The two rain thresholds are independent, so they can disagree: for example, the engine says `IRRIGATE_IMMEDIATELY`
  while the schedule says `DEFER` because 3 mm fell in the last hour. In that case the schedule wins.

## 9. Assumptions and limitations

- The depth is treated as a depth in mm for one event. For the ML source it is the model's **gross** applied depth (net need divided by system efficiency); for the rule-based source it is the engine's water-deficit depth.
- Rainfall is a hold trigger only; the depth is not adjusted for it.
- Observed rain is "last hour" precipitation only; forecast rain is a 24 h sum of 3-hour volumes.
- The forecast comes from a single provider and is not guaranteed; a `DEFER` should be re-evaluated after the window.
- Volume assumes uniform application over the whole registered area and applies no efficiency factor of its own. With the ML depth (already gross) the litres are the water to pump; with the rule-based depth no efficiency loss is added on top.
- Thresholds are proposals and are not calibrated to a specific crop, soil or region.
- The depth handed to the scheduler is only as good as the existing engine's inputs. That engine substitutes defaults when
  inputs are missing (30 % soil moisture, 25 °C), and `sensor_freshness` then reads `manual_input`. The scheduler cannot
  see this; check `factors_evaluated.current_soil_moisture_pct` before trusting a non-zero depth for a field without sensor readings.
- The engine's `recent_rainfall_mm` fallback uses the latest stored weather row of any age, whereas the scheduler applies a
  180 minute staleness limit to its own observation.
- Output is advisory and must not drive pumps or valves without manual verification.

## 10. Tests

| File | Covers |
|---|---|
| `backend/tests/test_irrigation_scheduler.py` | Scheduler rules in isolation |
| `backend/tests/test_weather_adapter.py` | Adapter statuses, staleness, mock, stored fallback, forecast parsing, windowing, failure containment |
| `backend/tests/test_weather_forecast.py` | Currently identical in content to `test_weather_adapter.py` (only the line endings differ), so every test in it runs twice |
| `backend/tests/test_irrigation_schedule_integration.py` | The API endpoints end to end (mocked HTTP transport) |

`backend/tests/conftest.py` blocks real HTTP in every test (`httpx.HTTPTransport`; `httpx.MockTransport` is unaffected) and fails any
test during which a real request was attempted, so no live API key or internet is needed.
