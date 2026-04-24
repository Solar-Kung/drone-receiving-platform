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
Simulation Engine  ──►  POST /api/v1/telemetry  ──►  TimescaleDB
(1 Hz per drone)              │
                              ├──►  WebSocket broadcast  ──►  Frontend (React)
                              │          (Redis pub/sub)
                              │
ROS 2 / DDS  ──►  ros_bridge/  (fallback, optional)
```

### Backend (`backend/app/`)

- **`main.py`** — FastAPI app; runs `Base.metadata.create_all` and `ensure_buckets()` on startup via `lifespan`
- **`config.py`** — All settings via `pydantic-settings`; reads from `configs/.env`
- **`database.py`** — Async SQLAlchemy engine + `get_db()` dependency (yields `AsyncSession`)
- **`models/`** — SQLAlchemy ORM models: `Drone`, `FlightRecord`, `TelemetryData`, `LandingPad`, `LandingSchedule`, `Mission`, `InspectionImage`
- **`api/`** — FastAPI routers: `flights`, `landings`, `data`, `websocket`
- **`services/`** — Business logic: `FlightTracker` (telemetry persistence + state transitions + battery alerts), `LandingManager` (pad assignment), `DataCollector` (mission/image), `MinioClient` (presigned URLs)
- **`simulation/`** — *(Phase 1+)* Telemetry simulator, fleet simulator, flight orchestrator, route definitions
- **`ros_bridge/`** — ROS 2 subscribers. **Automatically falls back to mock mode** when `rclpy` is not installed. Being replaced by `simulation/` module.

### WebSocket Channels

Three channels managed by a single `ConnectionManager` in `api/websocket.py`:
- `/ws/telemetry` — real-time telemetry; also carries battery alert messages
- `/ws/flights` — flight status change events
- `/ws/landings` — landing pad status updates

**Envelope format** (all WebSocket messages must use):
```json
{
  "type": "telemetry_update",
  "drone_id": "drone-001",
  "data": { "latitude": 25.033, "longitude": 121.565, "altitude": 120.5, "timestamp": "..." }
}
```

### Frontend (`frontend/src/`)

- **`App.tsx`** — Layout, sidebar nav, and top-level routes
- **`components/`** — `MapView` (Leaflet live map), `TelemetryPanel`, `LandingControl`, `InspectionReport`
- **`hooks/useWebSocket.ts`** — Auto-reconnecting WebSocket hook used by all real-time components
- **`services/api.ts`** — Axios client + TanStack Query wrappers for REST calls

### Infrastructure (Docker Compose)

| Service | Port | Purpose |
|---------|------|---------|
| nginx | 8000 | Load balancer (reverse proxy to backend pool) |
| backend | (internal) | FastAPI (uvicorn), scalable via `--scale backend=N` |
| frontend | 3000 | Vite preview / nginx |
| timescaledb | 5432 | Time-series PostgreSQL |
| redis | 6379 | WebSocket pub/sub + leader election |
| minio | 9000/9001 | Inspection image storage |

### Horizontal Scaling

Backend instances can be scaled with `docker compose up -d --scale backend=2`.

- **Redis pub/sub fan-out**: every `manager.broadcast(channel, data)` call publishes to Redis. Each instance runs a `run_redis_subscriber()` task that listens on Redis and calls `_local_broadcast()` to send to its own WebSocket clients. This makes WebSocket events visible to all connected clients regardless of which backend they hit.
- **Leader election**: on startup, each instance tries `Redis SET NX EX 60` for key `drone_platform:simulation_leader`. The winner starts FleetSimulator + FlightOrchestrator + UDP listener. The loser (follower) skips the simulation stack. The leader refreshes its TTL every 30 seconds; if the leader dies, the key expires in 60 seconds and the next startup wins.
- **Follower behaviour**: `GET /api/v1/simulation/status` and `POST /api/v1/simulation/control` return 503 `{"error": "not_leader"}` on followers — nginx round-robin will route retries to the leader.
- **Known trade-offs**: UDP telemetry from C++ publisher may hit a follower (Docker DNS round-robin); only the leader processes it. Simulation control requests require hitting the leader — callers should retry on 503.

## Key Implementation Notes

- **Flight status lifecycle**: `scheduled → in_flight → approaching → landing → landed → completed / aborted`
- **Simulator pushes data via REST API** — `POST /api/v1/telemetry`, same path a real drone would use. Simulator does NOT write directly to DB or WebSocket.
- **TelemetryData model** — core fields: `drone_id`, `latitude`, `longitude`, `altitude`, `timestamp`. Extended fields (`battery`, `speed`, `heading`, `signal_strength`) are nullable, enabled in Phase 2.
- **MinIO buckets** (`inspection-images`, `flight-logs`) are auto-created on startup by `ensure_buckets()`.
- **No authentication layer** exists yet — all endpoints are open.
- `recharts` is already a frontend dependency for telemetry charts.

## Planned Work

See these docs for implementation details:
- **`docs/platform_status_and_plan.md`** — Platform current status & capabilities overview
- **`docs/implementation_plan.md`** — **Active implementation plan** with Phase 1-4 details, API specs, code examples, file structure, and acceptance criteria

When implementing features, always read `docs/implementation_plan.md` first and follow the phase order:

1. **Phase 1** — Single drone telemetry pipeline (data model → REST API → simulator → map + chart)
2. **Phase 2** — Dashboard stats + extended telemetry (battery/speed/heading) + alerts
3. **Phase 3** — Multi-drone fleet + flight lifecycle orchestrator + landing pad management
4. **Phase 4** — Mission/inspection system + anomaly injection + simulation control panel
