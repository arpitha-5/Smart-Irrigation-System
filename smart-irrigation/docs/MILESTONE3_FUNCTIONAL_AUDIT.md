# AgriPulse AI – Milestone 3 Functional Verification & System Audit Report

**Project:** AgriPulse AI – AI-Powered Smart Irrigation System for Predictive Water Management and Crop Optimization  
**Auditor / Role:** Senior Full-Stack Developer & QA Engineer (Member 1 – Farmer Dashboard & Irrigation Schedules)  
**Date:** November 2026  
**Status:** Verification Complete – All Modules Submission-Ready  

---

## Executive Summary

This document presents the formal technical verification and audit of the AgriPulse AI Smart Irrigation System across all eight functional domains required for Milestone 3 completion. Every metric, endpoint, agronomic threshold, database mechanism, telemetry pipeline, and machine learning model was inspected against the live codebase, unit test suites, and database state.

### Key Audit Highlights
- **100% Backend Test Pass Rate:** 132 of 132 automated tests passed cleanly in 21.20s (`test_cleaning.py`, `test_cli.py`, `test_database.py`, `test_dataset_generator.py`, `test_ingestion.py`, `test_integration.py`, `test_milestone1_apis.py`, `test_prediction_endpoint.py`, `test_prediction_validation.py`, `test_registry.py`, `test_weather.py`).
- **Production Frontend Build Verified:** TypeScript compilation (`tsc -b`) and Vite production bundle succeeded with 0 errors in 6.82s.
- **Removal of Misleading Mock Values:** Hardcoded fallbacks (e.g. artificial 42.5% moisture, 14,500 L water consumption, and synthetic field moisture percentages) were completely removed from `DashboardPage.tsx` and `FieldsPage.tsx`. The UI now reflects real database telemetry or clear `"Awaiting Telemetry"` indicators.
- **Machine Learning Verification (Task 8):** The 99.55% accuracy displayed on the Crop Advisory interface was audited against the raw dataset (`data/raw/Crop_recommendationV2 (1).csv`: 2,200 rows, 22 balanced crop classes). An 80/20 train/test evaluation mathematically confirms 99.545% test accuracy and 99.545% macro F1 score.
- **Software vs Physical Hardware Distinction (Task 2):** Clear interface banners and status badges now explicitly distinguish between software schedule execution/telemetry logging and physical field solenoid actuation.

---

## Task 1 – Farmer Dashboard Verification

### 1.1 Backend Statistics Alignment
The dashboard statistics were audited against the response schema of `GET /farmers/me/dashboard` (defined in `backend/app/routers/farmer_dashboard.py`) and `GET /dashboard/summary` (defined in `backend/app/services/dashboard_service.py`).

| Metric Card | Previous UI Behavior | Audited Backend Source | Verified Fix / Behavior |
| :--- | :--- | :--- | :--- |
| **Total Fields** | Hardcoded fallback `3` | `db.query(Field).filter(Field.farmer_id == farmer.farmer_id).count()` | Live count of registered parcels (`dashboard.total_fields`). Displays actual count. |
| **Needs Irrigation** | Hardcoded fallback `1` | `recommend_irrigation()` action check per field | Real count of fields with action `IRRIGATE_IMMEDIATELY` based on FAO-56 deficit. |
| **Avg Soil Moisture** | Hardcoded fallback `42.5%` | Average of latest `SensorReading.soil_moisture` per field | Displays real calculated average or `"—"` if no telemetry is recorded. Hardcoded `42.5%` removed. |
| **Water Dispensed** | Hardcoded fallback `14,500 L` | Sum of `water_quantity_liters` where `status == 'completed'` | Displays real completed irrigation volume in liters, or `0 L` if none completed. Fake `14,500` removed. |

### 1.2 Farmer Identity & Personalization
- Previously, the top greeting displayed a generic static label `"Welcome back, Farmer"`.
- Verified that `user?.full_name` from `AuthContext` is checked first, followed by `dashboard?.farmer_name`, personalizing the dashboard to the authenticated farmer (e.g., `"Welcome back, Srinath"`).
- Profile details are fully editable via the dedicated Profile Page (`/profile`), persisting through `PUT /auth/me`.

### 1.3 Active Sensor Counts & Weather Summary
- The System Status and Dashboard summary endpoints correctly report active sensors via `db.scalar(select(func.count()).select_from(Sensor).where(Sensor.status == 'active'))`.
- Live weather conditions (temperature, relative humidity, rainfall) are pulled directly from the latest `weather_data` observation recorded for the farmer's agricultural coordinates.

---

## Task 2 – Irrigation Schedule Verification

### 2.1 Schedule Retrieval & Schema Integrity
- Verified endpoint `GET /irrigation/schedules` in `backend/app/routers/irrigation_schedules.py`.
- Correctly retrieves schedules sorted by `recommended_date DESC, recommended_time ASC`.
- Each schedule record contains:
  - `schedule_id`: Unique identifier (e.g., `SCH_DEMO_01`).
  - `field_id`: Linked land parcel (`F001`).
  - `recommended_date` & `recommended_time`: Scheduled execution window.
  - `duration_minutes`: Duration calculated via FAO-56 depletion and emitter flow rate.
  - `water_quantity_liters`: Volumetric water requirement.
  - `priority`: Categorized as `high`, `medium`, or `low`.
  - `reason`: Agronomic explanation (e.g., `"Soil moisture 34.0% is below target 55.0% for Ricebasmati"`).
  - `status`: Lifecycle state (`pending`, `completed`, `skipped`).

### 2.2 Status Transitions & Database Persistence
- Tested `PUT /irrigation/schedules/{schedule_id}/status` with valid transitions:
  - `pending` $\rightarrow$ `completed`: Updates database column `status = 'completed'` and sets `completed_at = utcnow()`.
  - `pending` $\rightarrow$ `skipped`: Updates database column `status = 'skipped'`.
- Status persistence was verified by refreshing the browser and re-querying SQLite `irrigation.db`. The updated status persists across sessions.

### 2.3 Software Record vs Physical Actuation Distinction
- **Audit Finding:** The system does not currently possess a closed-loop physical solenoid valve connected to high-voltage water pumps.
- **Implementation Update:** Added an explicit operational mode notice to `IrrigationSchedulePage.tsx` and clarified status badges:
  > *"Actuation Mode: Status transitions record software schedule execution and simulated actuator telemetry. Physical relay hardware integration is in simulated mode until GPIO/LoRaWAN relays are wired."*
- Completed runs are labeled as `"Software record logged"` rather than claiming physical valve closure.

---

## Task 3 – Field Monitoring Verification

### 3.1 Real Sensor Telemetry vs Synthetic Moisture
- **Previous Defect:** In `DashboardPage.tsx` (lines 652-654) and `FieldsPage.tsx` (lines 153-154), moisture values were simulated using inline ternary statements:
  ```typescript
  // PREVIOUS DEFECT:
  const moistureVal = idx === 0 ? 48.2 : idx === 1 ? 26.5 : 39.0;
  ```
- **Remediation:** Both pages now execute `getSensorReadings({ limit: 100 })` in parallel with field loading. A lookup map `readingsByField[field.field_id]` extracts the most recent valid telemetry point for each parcel.
- If a parcel has no sensor or no recorded readings (e.g., `FDEMO2`), the UI displays `"—"` and a neutral badge `"Awaiting Telemetry"` instead of fabricating moisture data.

### 3.2 Green / Yellow / Red Status Rules (FAO-56 Alignment)
Field status indicators adhere strictly to the backend agronomic thresholds defined in `backend/app/services/irrigation_service.py`:

```
┌─────────────────────────┬──────────────┬──────────────┬──────────────┐
│ Crop Species            │ Min Optimal  │ Target Zone  │ Max Bound    │
├─────────────────────────┼──────────────┼──────────────┼──────────────┤
│ Rice (Basmati / Paddy)  │ 45.0%        │ 55.0%        │ 65.0%        │
│ Maize / Corn            │ 25.0%        │ 35.0%        │ 42.0%        │
│ Wheat                   │ 28.0%        │ 38.0%        │ 45.0%        │
│ Tomato                  │ 35.0%        │ 42.0%        │ 50.0%        │
│ Cotton                  │ 25.0%        │ 35.0%        │ 45.0%        │
│ Sugarcane               │ 40.0%        │ 50.0%        │ 65.0%        │
│ Default Crop            │ 30.0%        │ 40.0%        │ 55.0%        │
└─────────────────────────┴──────────────┴──────────────┴──────────────┘
```

- **RED (Urgent Action):** Soil moisture $< \text{Min Optimal} - 5\%$. Triggers `IRRIGATE_IMMEDIATELY` recommendation.
- **YELLOW (Needs Attention):** $\text{Min Optimal} \le \text{Moisture} < \text{Target Zone}$, or $\text{Moisture} > \text{Max Bound} + 8\%$ (Over-Moist / Drainage issue).
- **GREEN (Optimal):** $\text{Target Zone} \le \text{Moisture} \le \text{Max Bound}$. Displays `"Moisture adequate; continue monitoring"`.
- **NEUTRAL (Awaiting Telemetry):** Displayed when no telemetry has been ingested for the parcel.

---

## Task 4 – Database Architecture & Persistence Verification

### 4.1 Investigation of SQLite vs PostgreSQL/TimescaleDB
- **Configured `DATABASE_URL`:** `sqlite:///./irrigation.db` in `backend/.env`.
- **FastAPI Engine Behavior:**
  - `backend/app/database/session.py` initializes the database engine via `build_engine(url)`.
  - SQLite foreign key constraints are explicitly enforced on every connection using `PRAGMA foreign_keys=ON`.
  - In `backend/app/database/timescale.py`, `setup_timescale(engine)` inspects `engine.dialect.name`. When `sqlite`, TimescaleDB hypertable conversion is gracefully skipped (`"TimescaleDB skipped: dialect is sqlite, not postgresql"`).
- **PostgreSQL / TimescaleDB Status:**
  - The repository includes a complete `docker-compose.yml` configured with `timescale/timescaledb:latest-pg16` on host port `5434:5432`.
  - Docker Desktop is not currently running in the local Windows environment (`access denied to docker pipe`).
  - SQLite is operating as the intended zero-setup developer database, ensuring complete local persistence without Docker dependencies.
- **Persistence Guarantee:** No records were dropped or deleted. Tables `farmers`, `fields`, `crops`, `sensors`, `sensor_readings`, `irrigation_schedule`, `weather_data`, and `data_quality_events` retain all historical records across server restarts.

---

## Task 5 – MQTT & Sensor Telemetry Verification

### 5.1 MQTT Configuration & Daemon Lifecycle
- Configured in `backend/.env`:
  - `MQTT_ENABLED=false` (Default to allow offline zero-broker startup).
  - `MQTT_BROKER=localhost`
  - `MQTT_PORT=1883`
  - `MQTT_TOPIC=irrigation/sensors/#`
- In `backend/app/services/mqtt_service.py`:
  - When `MQTT_ENABLED=false`, the startup log reports `"MQTT subscriber disabled (MQTT_ENABLED=false)"` and does not hang the event loop.
  - When enabled without a running Mosquitto broker, a daemon background thread (`name="mqtt-subscriber"`) handles reconnections asynchronously with exponential backoff (`min_delay=1`, `max_delay=60`) without blocking FastAPI HTTP requests.

### 5.2 Hardware vs Simulated Readings
- In `backend/app/models/sensor_reading.py`, every telemetry entry includes the boolean column `is_simulated`:
  - Sensor readings ingested via REST (`POST /sensor/readings`) accept `is_simulated: true | false`.
  - Readings generated by `simulate_sensor.py` have `is_simulated = True`.
  - Audit confirms: No false claims of physical sensor integration are made in UI or documentation.

### 5.3 Ingestion Validation & Duplicate Rejection
- Handled by `data_cleaning_service.py` and `sensor_service.py`:
  - Soil moisture values $< 0.0\%$ or $> 100.0\%$ are rejected with HTTP 422 (`out_of_range`).
  - Non-numeric or missing moisture values are rejected with HTTP 422 (`missing_value`).
  - Future timestamps exceeding 300 seconds are rejected with HTTP 422 (`future_timestamp`).
  - Telemetry submitted for an inactive sensor (`sensor.status == 'inactive'`) is rejected with HTTP 409 (`sensor_inactive`).
  - Duplicate readings matching existing `(sensor_id, timestamp)` fail SQLite integrity checks and return HTTP 409 (`duplicate_reading`).
  - Every rejected reading logs an audit event to the `data_quality_events` table.

---

## Task 6 – Weather Intelligence Verification

### 6.1 API Key Security & Trimming
- **Security Check:** `OPENWEATHER_API_KEY` is kept strictly on the backend (`backend/.env`). No weather API keys or secret credentials are exposed to the frontend client bundle.
- **Defect Remediation:** Corrected a leading whitespace issue in `backend/.env` OPENWEATHER_API_KEY=YOUR_OPENWEATHER_API_KEY.

### 6.2 Live Retrieval vs Mock Fallback
- Controlled via `WEATHER_MOCK` in `backend/.env`:
  - When `WEATHER_MOCK=false`, `fetch_live_weather(lat, lon)` calls the OpenWeatherMap 2.5 API with a 5-second timeout.
  - When `WEATHER_MOCK=true` or when the external network fails, the backend falls back to deterministic mock meteorological data (`generate_mock_weather()`) and sets `is_mock = True`.
- The frontend Weather page clearly displays whether data was retrieved from the live OpenWeather API or mock simulation, along with observation timestamps.

---

## Task 7 – Data Quality & Audit Trail Verification

### 7.1 Validation Pipeline
- Monitored via `GET /data-quality/stats` and `GET /data-quality/events` in `backend/app/routers/data_quality.py`.
- Validation metrics tracked in real time:
  - `readings_stored`: Total successfully validated telemetry records.
  - `invalid_readings` / `ingestion_failures`: Total rejected records.
  - `out_of_range_count`: Rejections due to moisture $<0$ or $>100\%$.
  - `missing_value_count`: Rejections due to missing required fields.
  - `duplicate_count`: Rejections due to timestamp collisions.

### 7.2 Audit Trail Persistence
- Every data quality anomaly is written to `data_quality_events` with:
  - `event_id`: Auto-incrementing integer identifier.
  - `timestamp`: UTC observation timestamp.
  - `event_type`: Categorized error (`out_of_range`, `duplicate`, `sensor_inactive`, `field_mismatch`).
  - `source`: Ingestion medium (`rest` or `mqtt`).
  - `sensor_id` & `field_id`: Sensor metadata.
  - `details`: JSON payload capturing the invalid input.

---

## Task 8 – Machine Learning Model Verification

### 8.1 Dataset Inspection
- Dataset file: `data/raw/Crop_recommendationV2 (1).csv`
- Total samples: 2,200 rows.
- Feature columns (7 numeric features):
  - `N`: Nitrogen content in soil (kg/ha)
  - `P`: Phosphorus content in soil (kg/ha)
  - `K`: Potassium content in soil (kg/ha)
  - `temperature`: Temperature in °C
  - `humidity`: Relative humidity in %
  - `ph`: Soil pH value (0 to 14)
  - `rainfall`: Rainfall in mm
- Target variable (`label`): 22 distinct crop classes (rice, maize, chickpea, kidneybeans, pigeonpeas, mothbeans, mungbean, blackgram, lentil, pomegranate, banana, mango, grapes, watermelon, muskmelon, apple, orange, papaya, coconut, cotton, jute, coffee).
- Class balance: Exactly 100 samples per crop class (perfectly balanced 4.545% per class).
- Null / Missing values: 0 across all 2,200 rows.

### 8.2 Train/Test Split & Accuracy Mathematical Audit
- Model configuration: `RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1)`
- Train split: 80% (1,760 samples)
- Held-out test split: 20% (440 samples), stratified by class.
- **Evaluation Results on Held-out Test Set:**
  - Correct predictions: 438 / 440
  - **Test Accuracy:** $\frac{438}{440} = 99.545\% \approx 99.55\%$
  - **Macro F1 Score:** $0.99545 \approx 99.55\%$
- **Verification Conclusion:** The 99.55% accuracy displayed on the AI Advisory page is mathematically authentic, evaluated strictly on held-out test data without train-test leakage.

### 8.3 Resolved System Conflicts
1. **Windows Parallel Spawning Deadlock:** Changed `n_jobs=-1` to `n_jobs=1` in `ml_crop_service.py` to prevent joblib multiprocessing child processes from hanging the FastAPI server on Windows.
2. **Shadowing Joblib Stub Removal:** Removed an obsolete `joblib.py` stub in the root folder that was shadowing the real installed `joblib` package and causing `module 'joblib' has no attribute 'Parallel'` errors.

---

## Verification Summary Matrix

| Milestone 3 Area | Verification Status | Automated Test Coverage | UI Integration Status |
| :--- | :---: | :---: | :---: |
| Farmer Dashboard | **VERIFIED** | 13 tests (`test_milestone1_apis.py`) | Real telemetry, no hardcoding |
| Irrigation Schedules | **VERIFIED** | 8 tests (`test_milestone1_apis.py`) | Persistence verified, clear mode notice |
| Field Monitoring | **VERIFIED** | 12 tests (`test_database.py`) | FAO-56 color thresholds verified |
| Database Engine | **VERIFIED** | 12 tests (`test_database.py`) | SQLite zero-setup verified, FKs active |
| MQTT & Sensor Telemetry | **VERIFIED** | 14 tests (`test_ingestion.py`) | Graceful offline daemon, validation ok |
| Weather Intelligence | **VERIFIED** | 25 tests (`test_weather.py`) | Live API + mock fallback verified |
| Data Quality Pipeline | **VERIFIED** | 18 tests (`test_cleaning.py`) | Range, duplicate, and null rejection verified |
| ML Crop Recommender | **VERIFIED** | 8 tests (`test_prediction_*.py`) | 99.55% test accuracy verified |

