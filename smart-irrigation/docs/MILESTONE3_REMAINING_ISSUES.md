# AgriPulse AI – Milestone 3 Known Constraints & Technical Handover Notes

**Project:** AgriPulse AI – AI-Powered Smart Irrigation System  
**Auditor / Role:** Senior Full-Stack Developer & QA Engineer (Member 1 – Farmer Dashboard & Irrigation Schedules)  
**Date:** November 2026  
**Document Purpose:** Transparently document technical boundaries, architectural constraints, and team coordination touchpoints.  

---

## 1. Technical Boundaries & Operational Reality

### 1.1 Physical Hardware vs Software Simulation (Member 2 Touchpoint)
- **Current Architecture:** All sensor telemetry and pump actuation operate in **software-simulated mode**.
  - Sensor telemetry can be ingested via HTTP REST (`POST /sensor/readings`) or MQTT, and carries the boolean flag `is_simulated = True`.
  - The script `simulate_sensor.py` provides realistic diurnal soil moisture fluctuations, evapotranspiration loss, and rainfall replenishment.
- **Physical Integration Constraint:** No physical GPIO relay shields, LoRaWAN gateways, or solenoid plumbing valves are currently connected to physical farmland pipes.
- **UI Transparency:** The UI explicitly presents schedule completion as `"Software record logged"` and includes an actuation notice explaining that physical relay integration is simulated.

### 1.2 Database Engine Selection: SQLite vs PostgreSQL/TimescaleDB (Member 4 Touchpoint)
- **Default Developer Database:** The project is configured with `DATABASE_URL=sqlite:///./irrigation.db`.
  - SQLite requires zero installation, no external background services, and persists all records across restarts.
  - Foreign key constraints are actively enforced using `PRAGMA foreign_keys=ON`.
- **TimescaleDB Containerization:**
  - The repository includes a production-grade `docker-compose.yml` with TimescaleDB published on host port `5434:5432`.
  - When Docker Desktop is started and `DATABASE_URL=postgresql+psycopg2://irrigation:irrigation@localhost:5434/irrigation` is set in `backend/.env`, `app.database.timescale.setup_timescale()` automatically converts `sensor_readings` and `weather_data` into hypertable chunks.
  - In local development without Docker running, the application gracefully skips TimescaleDB hypertables and uses standard SQLite tables without failing.

### 1.3 MQTT Telemetry Broker Configuration (Member 2 & 4 Touchpoint)
- **Current Setting:** `MQTT_ENABLED=false` in `backend/.env`.
- **Reason:** Prevents backend startup hangs when running in environments where a Mosquitto or EMQX broker is not active.
- **Broker Activation:** To activate live MQTT ingestion:
  1. Start a local Mosquitto broker on port 1883 (`mosquitto -v` or via Docker).
  2. Set `MQTT_ENABLED=true` in `backend/.env`.
  3. The backend daemon thread will automatically subscribe to `irrigation/sensors/#` and ingest incoming JSON telemetry payloads into `sensor_readings`.

### 1.4 Weather Service Rate Limits & Offline Mode (Member 4 Touchpoint)
- **API Provider:** OpenWeatherMap 2.5 API.
- **API Key Security:** Kept strictly server-side in `backend/.env`. Never exposed to client bundles.
- **Mock Mode:** When `WEATHER_MOCK=true` or when internet connectivity is unavailable, the backend automatically serves deterministic meteorological observations (`is_mock = True`) to prevent user disruption.

---

## 2. Team Member Coordination & Responsibilities

| Role | Core Scope | Milestone 3 Integration Status |
| :--- | :--- | :--- |
| **Member 1 (Current Role)** | Farmer Dashboard & Irrigation Schedules | **Complete:** Full farmer dashboard, live telemetry integration, schedule execution logs, responsive UI, profile management, and zero mock fallbacks. |
| **Member 2** | Sensors, Ingestion & MQTT | **Integrated:** Connected via `sensor_service.py`, `POST /sensor/readings`, duplicate rejection, and `is_simulated` tracking. |
| **Member 3** | Crop Recommendation & Agronomic ML | **Integrated:** Connected via `ml_crop_service.py` (99.55% test accuracy) and FAO-56 irrigation recommendation algorithms. |
| **Member 4** | Weather, Data Quality & System DevOps | **Integrated:** Connected via `weather_service.py`, `quality_service.py`, `data_quality_events` audit table, and `system_status` diagnostics. |

---

## 3. Submission-Readiness Checklist

- [x] All 132 automated backend unit and integration tests passing (`pytest` 132/132).
- [x] Frontend builds with zero TypeScript compiler errors (`tsc -b && vite build`).
- [x] Misleading hardcoded fallbacks (42.5%, 14,500 L) completely removed.
- [x] Soil moisture displayed dynamically from live database telemetry.
- [x] Status indicators adhere to official FAO-56 deficit rules (Red / Yellow / Green).
- [x] Machine learning 99.55% accuracy verified on 2,200-sample dataset without fabrication.
- [x] Software records clearly distinguished from physical solenoid pump actuation.
- [x] Full audit reports compiled and documented in `docs/`.

