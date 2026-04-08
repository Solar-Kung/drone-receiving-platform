import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.landing import LandingPad, LandingSchedule, PadStatus

router = APIRouter()


# --- Schemas ---

class LandingPadCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    altitude: float = 0.0
    has_charger: bool = False
    max_drone_weight: Optional[float] = None


class LandingPadResponse(BaseModel):
    id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    altitude: float
    status: PadStatus
    has_charger: bool
    max_drone_weight: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class LandingPadStatusUpdate(BaseModel):
    status: PadStatus


class LandingScheduleCreate(BaseModel):
    flight_id: uuid.UUID
    pad_id: uuid.UUID
    scheduled_time: datetime
    priority: int = 0


class LandingScheduleResponse(BaseModel):
    id: uuid.UUID
    flight_id: uuid.UUID
    pad_id: uuid.UUID
    scheduled_time: datetime
    actual_time: Optional[datetime]
    priority: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Landing Pad Endpoints ---

@router.post("/pads", response_model=LandingPadResponse, status_code=201)
async def create_landing_pad(pad: LandingPadCreate, db: AsyncSession = Depends(get_db)):
    db_pad = LandingPad(**pad.model_dump())
    db.add(db_pad)
    await db.commit()
    await db.refresh(db_pad)
    return db_pad


@router.get("/pads", response_model=list[LandingPadResponse])
async def list_landing_pads(
    status: Optional[PadStatus] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(LandingPad)
    if status:
        query = query.where(LandingPad.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/pads/{pad_id}/status", response_model=LandingPadResponse)
async def update_pad_status(
    pad_id: uuid.UUID,
    update: LandingPadStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LandingPad).where(LandingPad.id == pad_id))
    pad = result.scalar_one_or_none()
    if not pad:
        raise HTTPException(status_code=404, detail="Landing pad not found")
    pad.status = update.status
    await db.commit()
    await db.refresh(pad)
    return pad


# --- Landing Schedule Endpoints ---

@router.post("/schedules", response_model=LandingScheduleResponse, status_code=201)
async def create_landing_schedule(
    schedule: LandingScheduleCreate,
    db: AsyncSession = Depends(get_db),
):
    db_schedule = LandingSchedule(**schedule.model_dump())
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule


@router.get("/schedules", response_model=list[LandingScheduleResponse])
async def list_landing_schedules(
    pad_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(LandingSchedule).order_by(LandingSchedule.scheduled_time)
    if pad_id:
        query = query.where(LandingSchedule.pad_id == pad_id)
    result = await db.execute(query)
    return result.scalars().all()
