# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

A **drone inspection monitoring receiving station** (無人機巡檢監控接收站). It receives drone telemetry and inspection data, provides real-time flight tracking, landing management, and mission/image collection. All drone data is AI-simulated — there are no real physical drones.

## Running the Platform

```bash
# Copy and configure environment
cp configs/.env.example configs/.env

# Start all services
docker compose up -d

# Access points
# Frontend dashboard: http://localhost:3000
# Backend API + Swagger: http://localhost:8000/docs
# MinIO console: http://localhost:9001
```

The backend mounts `./backend/app` as a live volume, so Python changes apply without rebuilding.

## Frontend Development (without Docker)

```bash
cd frontend
npm install
npm run dev       # dev server on :5173
npm run build     # tsc + vite build
npm run lint      # eslint on .ts/.tsx
```

## Architecture Overview

### Data Flow

```
ROS 2 / DDS  ──►  ros_bridge/  ──►  services/  ──►  TimescaleDB
                  (subscribers)    (business logic)
                                        │
                                        ▼
                              WebSocket manager  ──►  Frontend (React)
                                   (Redis pub/sub)
```

### Backend (`backend/app/`)

- **`main.py`** — FastAPI app; runs `Base.metadata.create_all` and `ensure_buckets()` on startup via `lifespan`
- **`config.py`** — All settings via `pydantic-settings`; reads from `configs/.env`
- **`database.py`** — Async SQLAlchemy engine + `get_db()` dependency (yields `AsyncSession`)
- **`models/`** — SQLAlchemy ORM models: `Drone`, `FlightRecord`, `TelemetryData`, `LandingPad`, `LandingSchedule`, `Mission`, `InspectionImage`
- **`api/`** — FastAPI routers: `flights`, `landings`, `data`, `websocket`
- **`services/`** — Business logic: `FlightTracker` (telemetry persistence + state transitions + battery alerts), `LandingManager` (pad assignment), `DataCollector` (mission/image), `MinioClient` (presigned URLs)
- **`ros_bridge/`** — ROS 2 subscribers. **Automatically falls back to mock mode** when `rclpy` is not installed. `telemetry_sub.py` mock generates random Taipei-area coords for `mock-drone-001` at 1 Hz.

### WebSocket Channels

Three channels managed by a single `ConnectionManager` in `api/websocket.py`:
- `/ws/telemetry` — real-time telemetry; also carries battery alert messages
- `/ws/flights` — flight status change events
- `/ws/landings` — landing pad status updates

### Frontend (`frontend/src/`)

- **`App.tsx`** — Layout, sidebar nav, and top-level routes
- **`components/`** — `MapView` (Leaflet live map), `TelemetryPanel`, `LandingControl`, `InspectionReport`
- **`hooks/useWebSocket.ts`** — Auto-reconnecting WebSocket hook used by all real-time components
- **`services/api.ts`** — Axios client + TanStack Query wrappers for REST calls

### Infrastructure (Docker Compose)

| Service | Port | Purpose |
|---------|------|---------|
| backend | 8000 | FastAPI (uvicorn) |
| frontend | 3000 | Vite preview / nginx |
| timescaledb | 5432 | Time-series PostgreSQL |
| redis | 6379 | WebSocket pub/sub |
| minio | 9000/9001 | Inspection image storage |

## Key Implementation Notes

- **Flight status lifecycle**: `scheduled → in_flight → approaching → landing → landed → completed / aborted`
- **Telemetry is NOT persisted for mock drones** — `FlightTracker.handle_telemetry` skips DB write when `drone_id == "mock-drone-001"` or `flight_id == "mock-flight-001"`, but still broadcasts over WebSocket.
- **MinIO buckets** (`inspection-images`, `flight-logs`) are auto-created on startup by `ensure_buckets()`.
- **No authentication layer** exists yet — all endpoints are open.
- The dashboard summary cards (Active Drones, Active Flights, Available Pads, Today's Missions) are currently hardcoded as `--` and not yet wired to the API.
- `recharts` is already a frontend dependency for telemetry charts (not yet implemented).

## Planned Work (see `docs/platform_status_and_plan.md`)

The roadmap is organized in four phases:
1. **Core Simulation Engine** — replace minimal mock mode with full `SimulationEngine` service
2. **Dashboard & UI Completion** — wire live stats, telemetry charts, multi-drone map
3. **AI-Generated Data** — inspection reports, anomaly injection, historical backfill
4. **Advanced Features** — simulation control panel, scenario presets, replay mode
