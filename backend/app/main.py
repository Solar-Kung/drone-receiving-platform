import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import flights, landings, data, websocket, telemetry, stats
from app.database import engine, Base
from app.services.minio_client import ensure_buckets
from app.services.timescale import ensure_hypertable
from app.ros_bridge.udp_listener import start_udp_listener
from app.services.flight_tracker import flight_tracker
from app.simulation.fleet_simulator import FleetSimulator
from app.simulation.orchestrator import FlightOrchestrator
import app.models  # noqa: F401 — registers all models (incl. telemetry) with Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_hypertable()
    await ensure_buckets()
    # Start UDP listener for C++ telemetry publisher (WP5)
    asyncio.create_task(start_udp_listener(flight_tracker.handle_telemetry))

    # Phase 3A: multi-drone fleet + flight lifecycle orchestrator
    orchestrator = FlightOrchestrator(base_url="http://127.0.0.1:8000")
    await orchestrator.seed_data()  # idempotent drone + pad seeding

    fleet = FleetSimulator(base_url="http://127.0.0.1:8000")
    orchestrator.attach_to_fleet(fleet)  # wire position callbacks before start

    fleet_task = asyncio.create_task(fleet.start())
    orch_task = asyncio.create_task(orchestrator.start())

    yield

    # Shutdown
    await fleet.stop()
    await orchestrator.stop()
    fleet_task.cancel()
    orch_task.cancel()
    await engine.dispose()


app = FastAPI(
    title="Drone Receiving Platform",
    description="無人機巡檢監控接收站 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(telemetry.router, prefix="/api/v1/telemetry", tags=["telemetry"])
app.include_router(flights.router, prefix="/api/v1/flights", tags=["flights"])
app.include_router(landings.router, prefix="/api/v1/landings", tags=["landings"])
app.include_router(data.router, prefix="/api/v1/data", tags=["data"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["stats"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "drone-receiving-platform"}
