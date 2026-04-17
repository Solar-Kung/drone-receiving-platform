from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.telemetry import TelemetryData

router = APIRouter()

# Recorded once at import time — approximates server start
_server_start: datetime = datetime.now(timezone.utc)


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    window = now - timedelta(seconds=30)

    active_result = await db.execute(
        select(func.count(distinct(TelemetryData.drone_id))).where(
            TelemetryData.timestamp > window
        )
    )
    active_drones = active_result.scalar() or 0

    total_result = await db.execute(select(func.count(TelemetryData.id)))
    total_points = total_result.scalar() or 0

    latest_result = await db.execute(
        select(TelemetryData.altitude)
        .order_by(TelemetryData.timestamp.desc())
        .limit(1)
    )
    latest_altitude = latest_result.scalar()

    return {
        "success": True,
        "data": {
            "active_drones": active_drones,
            "total_telemetry_points": total_points,
            "latest_altitude": latest_altitude,
            "uptime_since": _server_start.isoformat(),
        },
    }
