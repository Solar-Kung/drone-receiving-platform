import asyncio
import logging
import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import flights, landings, data, websocket, telemetry, stats, simulation
from app.database import engine, Base
from app.services.minio_client import ensure_buckets
from app.services.timescale import ensure_hypertable, ensure_mission_columns
from app.services.redis_client import init_redis, close_redis, get_redis
from app.api.websocket import run_redis_subscriber
from app.ros_bridge.udp_listener import start_udp_listener
from app.services.flight_tracker import flight_tracker
from app.simulation.fleet_simulator import FleetSimulator
from app.simulation.orchestrator import FlightOrchestrator
import app.models  # noqa: F401 — registers all models (incl. telemetry) with Base.metadata

logger = logging.getLogger(__name__)

SIMULATION_LEADER_KEY = "drone_platform:simulation_leader"
LEADER_TTL_SECONDS = 60
LEADER_REFRESH_INTERVAL = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Core startup (all instances) ---
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_hypertable()
    await ensure_mission_columns()
    await ensure_buckets()
    await init_redis()

    # Every instance subscribes to Redis and broadcasts to its own WS clients
    subscriber_task = asyncio.create_task(run_redis_subscriber())

    # --- Leader election via Redis SET NX ---
    hostname = socket.gethostname()
    r = get_redis()
    is_leader = await r.set(
        SIMULATION_LEADER_KEY, hostname,
        nx=True, ex=LEADER_TTL_SECONDS,
    )
    app.state.is_leader = bool(is_leader)
    app.state.hostname = hostname

    fleet_task = None
    orch_task = None
    udp_task = None
    refresh_task = None
    fleet = None
    orchestrator = None

    if is_leader:
        logger.info("This instance (%s) is the simulation leader", hostname)

        udp_task = asyncio.create_task(start_udp_listener(flight_tracker.handle_telemetry))

        orchestrator = FlightOrchestrator(base_url="http://127.0.0.1:8000")
        await orchestrator.seed_data()

        fleet = FleetSimulator(base_url="http://127.0.0.1:8000")
        orchestrator.attach_to_fleet(fleet)
        app.state.fleet = fleet
        app.state.orchestrator = orchestrator

        fleet_task = asyncio.create_task(fleet.start())
        orch_task = asyncio.create_task(orchestrator.start())

        async def refresh_leader_lock():
            while True:
                await asyncio.sleep(LEADER_REFRESH_INTERVAL)
                try:
                    current = await r.get(SIMULATION_LEADER_KEY)
                    if current == hostname:
                        await r.expire(SIMULATION_LEADER_KEY, LEADER_TTL_SECONDS)
                    else:
                        logger.warning("Lost leadership (current holder: %s)", current)
                        break
                except Exception as exc:
                    logger.error("Leader refresh failed: %s", exc)

        refresh_task = asyncio.create_task(refresh_leader_lock())
    else:
        logger.info("This instance (%s) is a follower", hostname)
        app.state.fleet = None
        app.state.orchestrator = None

    yield

    # --- Shutdown ---
    if fleet is not None:
        await fleet.stop()
    if orchestrator is not None:
        await orchestrator.stop()
    for task in [fleet_task, orch_task, udp_task, refresh_task, subscriber_task]:
        if task is not None:
            task.cancel()

    # Release leader lock (best-effort)
    if is_leader:
        try:
            current = await r.get(SIMULATION_LEADER_KEY)
            if current == hostname:
                await r.delete(SIMULATION_LEADER_KEY)
        except Exception:
            pass

    await close_redis()
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
app.include_router(simulation.router, prefix="/api/v1/simulation", tags=["simulation"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "drone-receiving-platform"}
