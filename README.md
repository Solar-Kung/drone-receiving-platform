# Drone Receiving Platform

無人機巡檢監控接收站 — 接收無人機回傳的巡檢影像與感測數據，提供即時飛行追蹤、降落管理與資料收集功能。

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + FastAPI |
| Frontend | React + TypeScript (Vite) |
| Communication | DDS / ROS 2 (rclpy) |
| Database | TimescaleDB (PostgreSQL) |
| Object Storage | MinIO (S3-compatible) |
| Cache | Redis |
| Deployment | Docker Compose |

## Quick Start

```bash
# 1. Copy environment config
cp configs/.env.example configs/.env

# 2. Start all services
docker compose up -d

# 3. Access
#    - Frontend Dashboard: http://localhost:3000
#    - Backend API Docs:   http://localhost:8000/docs
#    - MinIO Console:      http://localhost:9001
```

## Project Structure

```
├── backend/
│   └── app/
│       ├── main.py              # FastAPI entrypoint
│       ├── config.py            # Settings management
│       ├── database.py          # TimescaleDB connection
│       ├── models/              # SQLAlchemy models
│       ├── api/                 # REST & WebSocket routes
│       ├── services/            # Business logic
│       └── ros_bridge/          # ROS 2 DDS subscribers
├── frontend/
│   └── src/
│       ├── App.tsx              # Main layout & routing
│       ├── components/          # React components
│       ├── hooks/               # WebSocket hooks
│       └── services/            # API client
├── configs/
│   └── .env.example             # Environment template
└── docker-compose.yml
```

## API Endpoints

| Method | Path | Description |
|--------|------|------------|
| GET | `/health` | Health check |
| GET/POST | `/api/v1/flights/drones` | Drone management |
| GET | `/api/v1/flights/` | Flight records |
| GET | `/api/v1/flights/{id}/telemetry` | Telemetry data |
| GET/POST | `/api/v1/landings/pads` | Landing pad management |
| GET/POST | `/api/v1/landings/schedules` | Landing schedules |
| GET/POST | `/api/v1/data/missions` | Mission management |
| POST | `/api/v1/data/missions/{id}/images` | Upload inspection images |
| WS | `/ws/telemetry` | Real-time telemetry stream |
| WS | `/ws/flights` | Flight status updates |
| WS | `/ws/landings` | Landing status updates |
