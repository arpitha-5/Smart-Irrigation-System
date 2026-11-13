# AI-Powered Smart Irrigation System for Predictive Water Management and Crop Optimization

An agricultural IoT platform that ingests soil-moisture telemetry (REST and optional MQTT), validates it with an
auditable data-quality pipeline, stores it in PostgreSQL/TimescaleDB (or SQLite for zero-setup development), pulls
field-level weather and forecasts from OpenWeatherMap, and produces **advisory** crop and irrigation recommendations,
all behind a FastAPI backend and a React + Vite dashboard ("AgriPulse").

> **Advisory only.** Irrigation output (ML and rule-based) is not guaranteed to be agronomically correct. It must not
> drive pumps or valves without manual verification of soil, crop stage, emitter/flow rate and local conditions.

---

## 1. What is in the project

| Area | What it does |
|---|---|
| **Registry** | CRUD for farmers, fields (GPS, area, crop), crops (growth stage) and sensors |
| **Ingestion** | `POST /sensor/readings` (REST) and an optional MQTT subscriber; CSV export |
| **Data quality** | Range, null, duplicate, future-timestamp and ordering checks; every rejection is logged as an auditable event |
| **Time-series storage** | `sensor_readings` and `weather_data` become TimescaleDB hypertables on PostgreSQL; plain tables on SQLite |
| **Weather** | OpenWeatherMap current weather + geocoding, stored per field; optional mock mode |
| **Crop recommendation (ML)** | Random Forest classifier trained at startup on `data/raw/Crop_recommendationV2 (1).csv` |
| **Irrigation recommendation (ML + rules)** | A trained model (hurdle classifier + depth regressor) supplies the irrigation depth when it can; the FAO-56 style rule engine remains as the fallback and safety net |
| **Irrigation plan** | Time-slotted sessions (start, duration, depth) for the chosen depth; emergencies start immediately |
| **Emergency alerts** | Rule-based EMERGENCY / WARNING / INFO alerts (drought, over-watering, stale or missing sensor), independent of the model and weather |
| **Weather-aware scheduling** | `irrigation_scheduler` + `weather_adapter` decide whether to apply that depth now, defer it for rain, or withhold it when weather is unusable |
| **Dashboard** | React pages for every resource, charts, data quality, system status and the recommendation tools |

### Architecture

```
[Soil probes / simulator] --REST POST /sensor/readings--\
[MQTT sensors] --> MQTT broker --> background subscriber --> [Data-quality pipeline]
                                                                   |
                                         range / null / duplicate / future-time checks
                                                                   |
                                  +--------------------------------+---------------+
                                  |                                                |
                      [PostgreSQL core tables]                       [TimescaleDB hypertables]
                  farmers, fields, crops, sensors,                 sensor_readings, weather_data
                  data_quality_events                              (SQLite: ordinary tables)
                                  |
        [OpenWeatherMap] --> weather_service --> weather_adapter (observation + 24 h forecast)
                                  |
              ML model (depth) or rule engine (fallback) --> irrigation_scheduler (final decision)
                                  |--> alert_engine (emergency) --> schedule_optimizer (time slots)
                                  |
                     [FastAPI backend, default port 8010]
                                  |
                   [React + Vite dashboard, port 5173]
```

---

## 2. Technology stack

- **Backend:** Python 3.10+ (developed on 3.12/3.13), FastAPI, Uvicorn, SQLAlchemy 2.x, Pydantic v2, pydantic-settings, httpx
- **Database:** PostgreSQL 16 with TimescaleDB (Docker image `timescale/timescaledb:latest-pg16`), or SQLite
- **ML:** scikit-learn (Random Forest, Gradient Boosting), pandas, numpy, joblib. Optional, not in `requirements.txt`: `mlflow` (run tracking), `torch` (LSTM comparison)
- **IoT:** REST (JSON) and MQTT via `paho-mqtt` (**optional, not in `requirements.txt`**)
- **Frontend:** React 19, Vite, TypeScript, Tailwind CSS 4, Recharts, Axios, React Router 7, lucide-react
- **Tests:** pytest

---

## 3. Repository structure

```
smart-irrigation/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, router registration, startup (DB init, MQTT)
│   │   ├── config.py                # Settings (environment variables / backend/.env)
│   │   ├── errors.py                # Uniform JSON error envelope
│   │   ├── database/                # engine/session, init_db, TimescaleDB setup, additive migrations
│   │   ├── models/                  # Farmer, Field, Crop, Sensor, SensorReading, WeatherData, DataQualityEvent
│   │   ├── schemas/                 # Pydantic request/response contracts
│   │   ├── routers/                 # farmers, fields, crops, sensors, weather, data_quality,
│   │   │                            # recommendations, system, demo
│   │   ├── services/
│   │   │   ├── data_cleaning_service.py   # validation rules
│   │   │   ├── sensor_service.py, quality_service.py, registry_service.py, dashboard_service.py
│   │   │   ├── weather_service.py         # OpenWeatherMap provider (current + forecast), storage
│   │   │   ├── weather_adapter.py         # validated observation + forecast for scheduling
│   │   │   ├── irrigation_service.py      # rule-based recommendation + ML/scheduler/alert/plan orchestration
│   │   │   ├── ml_irrigation_service.py   # loads the model, gathers field features from the database
│   │   │   ├── alert_engine.py            # emergency / warning rules
│   │   │   ├── schedule_optimizer.py      # time-slotted irrigation plan
│   │   │   ├── agro_params.py             # crop Kc / stage parameters shared by training and serving
│   │   │   ├── irrigation_scheduler.py    # weather-aware IRRIGATE / DEFER / NO_IRRIGATION_NEEDED / WITHHELD
│   │   │   ├── ml_crop_service.py         # Random Forest crop recommender
│   │   │   ├── mqtt_service.py, location_service.py, combined_service.py, demo_service.py
│   │   ├── ml/                      # features, training/evaluation, predictor, tracking (MLflow or local JSON), optional LSTM
│   │   └── cli/weather_cli.py       # interactive weather lookup
│   ├── models/irrigation/<version>/ # trained model, metadata.json, evaluation_report.json (+ latest.txt)
│   ├── scripts/                     # simulator, dataset generator/loader, train_irrigation_model.py, verification scripts
│   ├── tests/                       # pytest suite (see section 8)
│   ├── pytest.ini
│   ├── requirements.txt
│   └── .env.example                 # copy to backend/.env (never commit .env)
├── frontend/
│   ├── src/
│   │   ├── components/layout/       # Navbar, Sidebar, Layout
│   │   ├── pages/                   # Landing, Dashboard, Recommendations, Farmers, Fields, Crops,
│   │   │                            # Sensors, Readings, Weather, DataQuality, SystemStatus
│   │   ├── services/api.ts          # Axios client and typed API calls
│   │   ├── types/index.ts           # TypeScript types mirroring the backend schemas
│   │   └── App.tsx, main.tsx
│   └── .env.example                 # VITE_API_BASE_URL
├── data/raw/                        # Crop_recommendationV2 (1).csv (see note in section 7A)
├── docs/                            # ml_irrigation_model.md, scheduling_logic.md, WEEK1.md, DATASETS.md, CROP_RECOMMENDATION_DATASET.md
├── docker-compose.yml               # TimescaleDB container (host port 5433)
└── README.md
```

---

## 4. Quick start

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Docker Desktop (only if you want PostgreSQL/TimescaleDB; SQLite needs nothing)

### Step 1: Python environment

Run from the repository root.

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pip install paho-mqtt          # optional: only for MQTT ingestion / simulator --mqtt
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install paho-mqtt          # optional
```

### Step 2: Choose a database

**Option A: SQLite (no Docker).** In `backend/.env` set `DATABASE_URL=sqlite:///./irrigation.db`.

**Option B: PostgreSQL + TimescaleDB (Docker).** From the repository root:

```bash
docker compose up -d
```

The container maps container port 5432 to **host port 5433** (to avoid clashing with a native PostgreSQL on 5432) and
creates database/user/password `irrigation` / `irrigation` / `irrigation`. These are local development defaults only;
change them for any shared or production environment. If `DATABASE_URL` is not set, the backend defaults to
`postgresql+psycopg2://irrigation:irrigation@localhost:5433/irrigation`.

### Step 3: Configure the backend

```bash
cp backend/.env.example backend/.env      # Windows: copy backend\.env.example backend\.env
```

Edit `backend/.env`. Add your own OpenWeatherMap key as `OPENWEATHER_API_KEY`. **Never commit `.env`**; it is listed in
`.gitignore`. See section 5 for every variable.

### Step 4: Start the backend

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

- Health: <http://127.0.0.1:8010/health>
- Interactive API docs: <http://127.0.0.1:8010/docs>
- System status: <http://127.0.0.1:8010/system/status>

Tables (and TimescaleDB hypertables, when available) are created automatically at startup.

### Step 5: Start the frontend

```bash
cd frontend
npm install
cp .env.example .env                       # Windows: copy .env.example .env
npm run dev
```

Open <http://localhost:5173>. The frontend calls `http://localhost:8010` unless `VITE_API_BASE_URL` says otherwise. If
you change the backend port, change that variable and `CORS_ORIGINS` accordingly.

### Step 6 (optional): Load demo data

Use the **Demo Seeder** button on the System Status page, or call `POST /demo/seed`.

### Stopping

Press `Ctrl+C` in the frontend and backend terminals, then `docker compose stop`. Do **not** run
`docker compose down -v` unless you want to delete the database volume.

---

## 5. Configuration (`backend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | assembled from `POSTGRES_*` (localhost:5433) | Full SQLAlchemy URL; `sqlite:///./irrigation.db` for SQLite |
| `POSTGRES_USER/PASSWORD/HOST/PORT/DB` | `irrigation` / `irrigation` / `localhost` / `5433` / `irrigation` | Used only when `DATABASE_URL` is unset |
| `APP_ENV`, `APP_VERSION` | `development`, `0.2.0` | Reported by `/system/status` |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |
| `OPENWEATHER_API_KEY` | empty | Required for live weather. Without it, weather endpoints return `weather_not_configured` |
| `OPENWEATHER_BASE_URL` | OWM 2.5 current weather | Current-weather endpoint |
| `OPENWEATHER_FORECAST_URL` | OWM 2.5 `forecast` (5-day / 3-hour) | Forecast endpoint |
| `OPENWEATHER_GEOCODE_URL` | OWM geo 1.0 `direct` | Place-name lookup |
| `WEATHER_TIMEOUT_SECONDS` | `5` | Provider timeout |
| `WEATHER_MOCK` | `false` | `true` returns simulated weather flagged `is_mock`; the scheduler never treats mock weather as real |
| `IRRIGATION_ML_ENABLED` | `true` | `false` forces the rule-based engine only |
| `IRRIGATION_MODELS_DIR` | `backend/models` | Where trained models live |
| `IRRIGATION_UTC_OFFSET_HOURS` | `5.5` | Local time offset used for irrigation windows (field time zone is not stored) |
| `SENSOR_FUTURE_TOLERANCE_SECONDS` | `300` | Readings dated further in the future are rejected |
| `MQTT_ENABLED`, `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_CLIENT_ID` | disabled, `localhost`, `1883`, `irrigation/sensors/#`, ... | Optional MQTT subscriber; startup never requires a broker |

`OPENWEATHER_FORECAST_URL` and `OPENWEATHER_GEOCODE_URL` are not in `.env.example`; the defaults work, and you can add them
to override.

---

## 6. API overview

Interactive documentation for every endpoint is at `/docs`.

| Group | Endpoints |
|---|---|
| Meta / system | `GET /health`, `GET /health/ready`, `GET /system/status`, `GET /dashboard/summary` |
| Farmers | `POST/GET /farmers`, `GET/PUT/DELETE /farmers/{farmer_id}` |
| Fields | `POST/GET /fields`, `GET/PUT/DELETE /fields/{field_id}`, `PUT /fields/{field_id}/crop`, `GET /fields/{field_id}/sensors`, `GET /fields/{field_id}/combined` |
| Crops | `POST/GET /crops`, `GET/PUT/DELETE /crops/{crop_id}` |
| Sensors | `POST/GET /sensors`, `GET/PUT/DELETE /sensors/{sensor_id}`, `PUT /sensors/{sensor_id}/status` |
| Ingestion | `POST /sensor/readings`, `GET /sensor/readings`, `GET /sensor/readings/export.csv` |
| Weather | `GET /weather/{field_id}` (fetch + store), `GET /weather/{field_id}/latest`, `GET /weather/{field_id}/history`, `GET /weather/observations`, `GET /weather/geocode`, `GET /weather/live-by-coords` |
| Data quality | `GET /data-quality/stats`, `GET /data-quality/events` |
| Recommendations | `POST /recommendations/crop`, `GET /recommendations/crop/metrics`, `POST /recommendations/irrigation`, `GET /recommendations/irrigation/{field_id}`, `GET /recommendations/irrigation-model` (model status, metrics, limitations), `POST /recommendations/irrigation/ml-predict` (run the model on supplied features) |
| Demo | `POST /demo/seed` |

Errors use a uniform JSON envelope.

### Frontend routes

`/` landing, `/dashboard`, `/recommendations`, `/farmers`, `/fields`, `/crops`, `/sensors`, `/readings`, `/weather`,
`/data-quality`, `/status`.

---

## 7. Recommendations

### A. Crop recommendation (machine learning)

- **Data:** `data/raw/Crop_recommendationV2 (1).csv`, 2,200 rows, 22 crops with 100 rows each, no missing values.
- **Model:** `RandomForestClassifier(n_estimators=100, random_state=42)` trained at startup on a stratified 80/20 split
  (1,760 train / 440 test). Features: N, P, K, temperature, humidity, pH, rainfall.
- **Held-out result** (reproduced when this README was written): accuracy 0.9955, macro-F1 0.9955. The dataset is
  public, balanced and well separated, so this does not predict performance on real farm data.
- **Endpoints:** `POST /recommendations/crop` (top crop, confidence, top candidates, rationale) and
  `GET /recommendations/crop/metrics`.

> **Dataset is git-ignored.** `.gitignore` contains `data/`, so a fresh clone will not contain the CSV and the crop
> recommender will fail to initialise. Place the file at `data/raw/Crop_recommendationV2 (1).csv`, or force-add it
> (`git add -f`) if you want it versioned.

### B. Irrigation: ML depth, weather-aware scheduler, emergency alerts and time-slot plan

`POST /recommendations/irrigation` and `GET /recommendations/irrigation/{field_id}` run these stages for a **registered field**:

1. **Rule-based engine** (`irrigation_service.recommend_irrigation`, FAO-56 style), unchanged. It returns the top-level `action`
   (`IRRIGATE_IMMEDIATELY`, `IRRIGATE_LIGHT`, `MAINTAIN_MONITORING`, `DEFER_DUE_TO_RAIN`) and `recommended_water_mm`.
2. **ML model** (`backend/models/irrigation/`). A hurdle model (classifier for "irrigate today?" plus a depth regressor) predicts the
   **gross** depth in mm from soil moisture, its 24 h change, 24 h forecast rain, crop and days after sowing. It is used **only if** it can run:
   crop is rice, maize, cotton or wheat; the field's crop record has a **planting date**; a soil-moisture reading under 24 h old (or a manual
   `soil_moisture`) exists. Otherwise the rule-based depth is used and `ml_prediction.reason` says why.
3. **Scheduler** (`irrigation_scheduler` + `weather_adapter`) returns `irrigation_schedule.action`:

| `irrigation_schedule.action` | Meaning |
|---|---|
| `IRRIGATE` | No hold rule applies; apply the depth unchanged. A volume in litres is added when the field has a valid area |
| `DEFER` | Hold the depth back: at least 2.5 mm of rain in the last hour, or at least 10 mm forecast within 24 h |
| `NO_IRRIGATION_NEEDED` | The depth handed to the scheduler is exactly 0 mm (including "the model says no") |
| `WITHHELD` | No safe recommendation: weather missing, stale (older than 180 min), mock, unavailable or invalid; or an implausible depth |

4. **Alerts** (`alert_engine`): rule-based, independent of the model and the weather. `EMERGENCY` when soil moisture is below 0.70 x the
   crop's critical threshold (0.85 x in flowering/fruiting), the reading is fresh, and no relieving rain is observed or forecast (at least 10 mm in 24 h).
   Also warnings for drought risk, over-watering, stale or missing sensor data.
5. **Plan** (`schedule_optimizer`): when the action is `IRRIGATE`, time slots in cool morning/evening windows; an emergency starts within
   minutes. Durations need an application rate: pass `irrigation_method` (drip / sprinkler / flood) or `application_rate_mm_per_hour`,
   otherwise 6 mm/h is **assumed** and flagged.

Safety net: if an `EMERGENCY` alert fires while the model advises no irrigation, the rule-based depth is used
(`schedule_input.source = "rule_based_emergency_override"`).

**Which action is final?** `irrigation_schedule.action` whenever `irrigation_schedule` is not `null`. `ml_prediction` shows what the model
said and `schedule_input.source` which source supplied the depth. When the schedule is `null` (no `field_id` or unregistered field) only the
engine's action exists, it is not weather-verified, and `scheduling_note` explains why; alerts are still returned.

**Model quality, honestly.** Trained on **synthetic** data only. On 1417 field-days from 10 unseen fields: ROC-AUC 0.93, recall 0.76,
**precision 0.46** (about half of "irrigate" calls are false alarms vs the simulated farmer), depth error 7.8 mm on average.
It clearly beats naive baselines, but this says nothing about real farms. Full protocol, per-crop results and limitations:
[`docs/ml_irrigation_model.md`](docs/ml_irrigation_model.md). Retrain with `python scripts/train_irrigation_model.py`.

Known limitations:

- The model's training moisture range (about 13-40 %) differs from the rule engine's per-crop thresholds (for example rice critical about 45 %), so
  the alert rules and the model can disagree. This needs calibration against real sensor and soil data.
- A new field has **no planting date**, so ML stays off (rule-based fallback) until a crop record with a planting date exists.
- The rule engine substitutes defaults (30 % soil moisture, 25 °C) when no reading is available; check
  `factors_evaluated.current_soil_moisture_pct`. Its `recent_rainfall_mm` fallback uses the latest stored weather row of any age.
- Alert and scheduling thresholds are proposals, not calibrated to a crop, soil or region.
- Each call for a registered field makes a live weather and forecast request and stores a `weather_data` row.
- Alerts are shown in the dashboard and API only; push / SMS / email delivery is a later milestone.
- The LSTM comparison and MLflow logging are implemented but were not run in the environment this was built in (see the ML doc).

---

## 8. Testing

```bash
cd backend
python -m pytest
```

- Uses in-memory SQLite by default. Set `TEST_DATABASE_URL` to run the same tests on PostgreSQL.
- `tests/conftest.py` blocks real HTTP (`httpx.HTTPTransport`) in every test and fails any test during which a real
  request was attempted, so no API key or internet is needed. Tests that need weather inject an `httpx.MockTransport`.
- Test files: cleaning, CLI, database, dataset generator, ingestion, integration, registry, weather, weather adapter,
  scheduler, scheduler API integration, Milestone 1 APIs, and Milestone 2: `test_ml_pipeline.py`, `test_schedule_optimizer.py`,
  `test_alert_engine.py`, `test_ml_recommendation_integration.py` (the last needs the model in `backend/models`; it skips if absent).
- Known issue: `tests/test_weather_forecast.py` is currently an exact duplicate of `tests/test_weather_adapter.py` (only line
  endings differ), so those tests run twice.
- If `OPENWEATHER_API_KEY` is set in your local `.env`, a test that hits the irrigation endpoint without mocking weather
  (for example `test_irrigation_recommendation_service`) will now fail loudly instead of passing silently. Mock the
  weather provider in that test.

Frontend:

```bash
cd frontend
npm run lint
npm run build      # tsc -b && vite build
```

### Verification scripts (`backend/scripts`)

Run from `backend/` with the backend already running on port 8010 unless noted.

| Script | Purpose |
|---|---|
| `verify_milestone.py` | Database connectivity, schema, foreign keys, hypertables |
| `verify_persistence.py` | Reading insertion, ordering and persistence |
| `verify_full_system.py` | End-to-end checks against the running server (port 8010) |
| `verify_e2e_milestone1.py`, `audit_milestone1_final.py` | Milestone 1 end-to-end / audit (port 8010) |
| `demo_week1.py` | Demo against a running server; **defaults to port 8000**, so pass `--base-url http://127.0.0.1:8010` |

---

## 9. Sensor ingestion examples

```bash
# valid reading
curl -X POST http://127.0.0.1:8010/sensor/readings -H "Content-Type: application/json" \
  -d '{"sensor_id": "SM001", "timestamp": "2026-10-15T10:00:00", "soil_moisture": 36.5, "is_simulated": true}'

# invalid reading: rejected with 422 and logged in data_quality_events
curl -X POST http://127.0.0.1:8010/sensor/readings -H "Content-Type: application/json" \
  -d '{"sensor_id": "SM001", "soil_moisture": 150.0, "is_simulated": true}'
```

The sensor must be registered first (via the UI, the API, or the demo seeder). The simulator (every reading carries
`is_simulated: true`):

```bash
cd backend
python scripts/simulate_sensor.py --sensor-id SM001 --field-id F001 --count 10
python scripts/simulate_sensor.py --sensor-id SM001 --count 6 --inject-faults     # nulls and out-of-range values
python scripts/simulate_sensor.py --sensor-id SM001 --mqtt                        # needs paho-mqtt and a broker
```

Other utilities: `scripts/generate_dataset.py` and `scripts/load_dataset.py` (synthetic development data) and
`python scripts/weather_cli.py --location "Hyderabad, IN"` (add `--field-id` to store the observation, `--debug` to see the raw response).

---

## 10. Security notes

- `.env` is git-ignored; only `.env.example` files (with an empty key) belong in version control. Do not paste API keys
  into code, tests, screenshots or issues.
- The weather provider never logs or returns the API key, and database URLs are masked in status output.
- The Docker credentials in `docker-compose.yml` are development defaults.
- There is no authentication on the API; do not expose it to an untrusted network as-is.

---

## 11. Further documentation

- [`docs/ml_irrigation_model.md`](docs/ml_irrigation_model.md): ML model, validation results, alerts, time-slot plan, limitations, retraining
- [`docs/scheduling_logic.md`](docs/scheduling_logic.md): scheduler and weather-adapter rules, thresholds, reason codes, limitations
- [`docs/WEEK1.md`](docs/WEEK1.md): Week 1 scope (ingestion and weather)
- [`docs/DATASETS.md`](docs/DATASETS.md) and [`docs/CROP_RECOMMENDATION_DATASET.md`](docs/CROP_RECOMMENDATION_DATASET.md): dataset notes
