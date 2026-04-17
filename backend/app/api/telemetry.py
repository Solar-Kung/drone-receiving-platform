from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import manager
from app.database import get_db
from app.models.telemetry import TelemetryData
from app.schemas.telemetry import TelemetryCreate, TelemetryResponse

router = APIRouter()


@router.post("", status_code=201)
async def receive_telemetry(
    data: TelemetryCreate, db: AsyncSession = Depends(get_db)
):
    telemetry = TelemetryData(
        drone_id=data.drone_id,
        latitude=data.latitude,
        longitude=data.longitude,
        altitude=data.altitude,
        timestamp=data.timestamp,
        speed=None,
        heading=None,
        battery_level=None,
        signal_strength=None,
    )
    db.add(telemetry)
    await db.commit()
    await db.refresh(telemetry)

    await manager.broadcast("telemetry", {
        "type": "telemetry_update",
        "drone_id": data.drone_id,
        "data": {
            "drone_id": data.drone_id,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "altitude": data.altitude,
            "timestamp": data.timestamp.isoformat(),
        },
    })

    return {"success": True, "data": TelemetryResponse.model_validate(telemetry)}


@router.get("/latest")
async def get_latest(drone_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TelemetryData)
        .where(TelemetryData.drone_id == drone_id)
        .order_by(TelemetryData.timestamp.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No telemetry found for drone")
    return {"success": True, "data": TelemetryResponse.model_validate(row)}


@router.get("/history")
async def get_history(
    drone_id: str, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    limit = min(limit, 1000)
    result = await db.execute(
        select(TelemetryData)
        .where(TelemetryData.drone_id == drone_id)
        .order_by(TelemetryData.timestamp.asc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return {
        "success": True,
        "data": [TelemetryResponse.model_validate(r) for r in rows],
        "meta": {"count": len(rows), "drone_id": drone_id},
    }
