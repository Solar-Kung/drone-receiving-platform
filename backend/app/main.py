from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import flights, landings, data, websocket
from app.database import engine, Base
from app.services.minio_client import ensure_buckets
from app.services.timescale import ensure_hypertable
import app.models  # noqa: F401 — registers all models (incl. telemetry) with Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_hypertable()
    await ensure_buckets()
    yield
    # Shutdown
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
app.include_router(flights.router, prefix="/api/v1/flights", tags=["flights"])
app.include_router(landings.router, prefix="/api/v1/landings", tags=["landings"])
app.include_router(data.router, prefix="/api/v1/data", tags=["data"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "drone-receiving-platform"}
