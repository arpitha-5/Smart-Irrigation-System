# AgriPulse AI – Milestone 3: Team Integration & Interface Contracts
**Author**: Member 1 – Farmer Dashboard & Irrigation Schedule  
**Collaborators**:
- **Member 2**: Progressive Web App (PWA), Offline Sync & IoT Telemetry Ingestion
- **Member 3**: Alert Dispatch Engine, Incident Management & ML Predictor Services
- **Member 4**: Agro-Meteorological Weather Service, TimescaleDB & DevOps/Deployment  
**Project**: AgriPulse AI – Smart Irrigation System  
**Date**: November 2026  

---

## 1. Integration Overview

Milestone 3 mandates strict modular boundaries: each team member implements their assigned functional domain while integrating cleanly through well-defined REST API contracts, shared Pydantic/TypeScript data schemas, and shared database models.

As **Member 1 (Farmer Dashboard & Irrigation Schedule)**, our modules interface with our teammates as follows:

```
┌─────────────────────────────────────────────────────────────┐
│                       AgriPulse AI UI                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  Member 1: Farmer Dashboard & Irrigation Schedule       │ │
│ └───────▲─────────────────────▲─────────────────────▲─────┘ │
└─────────┼─────────────────────┼─────────────────────┼───────┘
          │ (Read Telemetry)    │ (Alerts & ML Recs)  │ (Weather Data)
┌─────────▼─────────┐   ┌───────▼─────────┐   ┌───────▼─────────┐
│     Member 2      │   │    Member 3     │   │    Member 4     │
│   IoT Telemetry   │   │ Alert Dispatch  │   │  Weather Engine │
│   & PWA Sync      │   │  & ML Services  │   │   & TimescaleDB │
└───────────────────┘   └─────────────────┘   └─────────────────┘
```

---

## 2. Interface Contracts by Teammate

### Interface A: Member 1 $\longleftrightarrow$ Member 2 (IoT Telemetry & PWA Sync)

#### Shared Data Assets:
- `SensorReading` table: `sensor_id`, `field_id`, `soil_moisture`, `temperature`, `humidity`, `timestamp`.
- Telemetry ingestion endpoint: `POST /sensor/readings` (Member 2 writes, Member 1 reads).

#### Contract Specifications:
1. **Latest Reading Access**: Member 1 queries `GET /sensor/readings?limit=100` and `GET /sensor/latest/{field_id}` to calculate parcel soil moisture and determine whether a parcel requires water.
2. **Stale Telemetry Threshold**: If Member 2's sensor gateway does not transmit a reading within 24 hours, Member 1 displays a `Sensor telemetry stale (>24h)` notice and triggers an alert.
3. **PWA Offline Continuity**: Member 1's UI components use standard browser `localStorage` caching and Axios error fallbacks so that if a farmer loses 4G connectivity in the field, the dashboard gracefully presents the last cached telemetry state.

---

### Interface B: Member 1 $\longleftrightarrow$ Member 3 (Alert Dispatch & ML Predictions)

#### Shared Data Assets:
- `FarmAlert` / `SystemEvent`: Alert items containing `severity`, `field_id`, `message`, `actionable_recommendation`.
- `ML Crop Recommendation`: Predictive model output predicting optimal crop based on soil N-P-K, pH, temperature, and humidity.

#### Contract Specifications:
1. **Dynamic Alert Synthesis**: Member 1 consumes `GET /farmers/me/alerts`. Member 3's backend alert rules populate incidents into `system_events`. Member 1 dynamically surfaces these with visual severity tags (`critical`, `warning`, `info`) and actionable buttons.
2. **FAO-56 Irrigation Service**: `POST /irrigation/schedules/generate/{field_id}` invokes Member 3's shared recommendation logic, which computes water deficit based on current VWC and crop coefficients ($K_c$). Member 1 renders the resulting schedule card and permits the farmer to edit or execute it.

---

### Interface C: Member 1 $\longleftrightarrow$ Member 4 (Weather Intelligence & DevOps)

#### Shared Data Assets:
- `WeatherData` table: `field_id`, `temperature`, `humidity`, `rainfall`, `timestamp`.
- Database Infrastructure: PostgreSQL with TimescaleDB extension / SQLite local fallback.

#### Contract Specifications:
1. **Rainfall Precipitation Feed**: Member 1 consumes `weather_summary` from `GET /farmers/me/dashboard` and live queries from `GET /weather/live/{field_id}` provided by Member 4.
2. **Weather-Based Scheduling Override**: When Member 4's weather service reports rainfall $\ge 5.0$ mm, Member 1's scheduling dashboard immediately raises a `Rain Conflict: Consider Deferral` alert so the farmer can avoid over-irrigating.
3. **Database Portability**: Member 1's models and queries are written with pure SQLAlchemy ORM, ensuring seamless execution on either SQLite (`backend/irrigation.db`) during lightweight offline evaluation or PostgreSQL/TimescaleDB in cloud environments.

---

## 3. Shared Endpoints & Schema Cross-Reference

| Endpoint | Method | Provider | Consumer | Purpose |
|---|:---:|:---:|:---:|---|
| `/farmers/me/dashboard` | `GET` | Member 1 | Farmer UI | Aggregated farmer KPIs, water analytics, weather summary |
| `/farmers/me/alerts` | `GET` | Member 1 & 3 | Farmer UI | Synthesized real-time farm alerts with actionable recommendations |
| `/irrigation/schedules` | `GET`, `POST` | Member 1 | Farmer UI | Schedule listing, date filtering, and manual creation |
| `/irrigation/schedules/{id}` | `PUT`, `DELETE` | Member 1 | Farmer UI | Schedule inline editing, cancellation, and deletion |
| `/irrigation/schedules/{id}/status` | `PATCH` | Member 1 | Farmer UI | Transition schedule status (`completed`, `skipped`, `cancelled`) |
| `/fields` | `GET`, `POST`, `PUT` | Member 1 | Farmer UI | Land parcel CRUD, area, coordinates, crop assignment |
| `/sensor/readings` | `GET` | Member 2 | Member 1 | Soil moisture, temperature, humidity telemetry |
| `/weather/live/{field_id}` | `GET` | Member 4 | Member 1 | Real-time agro-meteorological observations |

---

## 4. Verification & Handoff Checklist

- [x] All Member 1 endpoints documented in OpenAPI schema (`/docs`).
- [x] All frontend components typed with TypeScript strict mode.
- [x] No circular imports between Member 1, 2, 3, and 4 services.
- [x] Pytest test suite verifies end-to-end integration across all 132 tests.
- [x] Ready for Milestone 3 team submission and evaluation.

