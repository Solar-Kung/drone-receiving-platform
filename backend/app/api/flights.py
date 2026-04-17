import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.drone import Drone
from app.models.flight import FlightRecord, FlightStatus

router = APIRouter()


# --- Schemas ---

class DroneCreate(BaseModel):
    name: str
    model: str
    serial_number: str
    max_flight_time: Optional[float] = None


class DroneResponse(BaseModel):
    id: uuid.UUID
    name: str
    model: str
    serial_number: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FlightResponse(BaseModel):
    id: uuid.UUID
    drone_id: uuid.UUID
    status: FlightStatus
    takeoff_time: Optional[datetime] = None
    landing_time: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TelemetryResponse(BaseModel):
    time: datetime
    drone_id: uuid.UUID
    latitude: float
    longitude: float
    altitude: float
    speed: float
    heading: float
    battery_level: float
    signal_strength: float

    model_config = {"from_attributes": True}


# --- Drone Endpoints ---

@router.post("/drones", response_model=DroneResponse, status_code=201)
async def register_drone(drone: DroneCreate, db: AsyncSession = Depends(get_db)):
    db_drone = Drone(**drone.model_dump())
    db.add(db_drone)
    await db.commit()
    await db.refresh(db_drone)
    return db_drone


@router.get("/drones", response_model=list[DroneResponse])
async def list_drones(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Drone).where(Drone.is_active.is_(True)))
    return result.scalars().all()


@router.get("/drones/{drone_id}", response_model=DroneResponse)
async def get_drone(drone_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Drone).where(Drone.id == drone_id))
    drone = result.scalar_one_or_none()
    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found")
    return drone


# --- Flight Endpoints ---

@router.get("/", response_model=list[FlightResponse])
async def list_flights(
    status: Optional[FlightStatus] = None,
    drone_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(FlightRecord)
    if status:
        query = query.where(FlightRecord.status == status)
    if drone_id:
        query = query.where(FlightRecord.drone_id == drone_id)
    query = query.order_by(FlightRecord.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{flight_id}", response_model=FlightResponse)
async def get_flight(flight_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FlightRecord).where(FlightRecord.id == flight_id))
    flight = result.scalar_one_or_none()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight


# --- Telemetry Endpoints ---
# Per-flight telemetry queries are deferred to Phase 3 when flight_id
# is wired into TelemetryData. Use GET /api/v1/telemetry/history for now.

@router.get("/{flight_id}/telemetry", response_model=list[TelemetryResponse])
async def get_flight_telemetry(
    flight_id: uuid.UUID,
    limit: int = Query(default=100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    return []
