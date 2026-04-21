import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mission import Mission, MissionStatus, InspectionImage
from app.services.minio_client import upload_file, get_presigned_url

router = APIRouter()


# --- Schemas ---

class MissionCreate(BaseModel):
    drone_id: uuid.UUID
    flight_id: uuid.UUID
    name: str
    description: Optional[str] = None
    area_of_interest: Optional[str] = None


class MissionResponse(BaseModel):
    id: uuid.UUID
    drone_id: uuid.UUID
    flight_id: uuid.UUID
    name: str
    description: Optional[str]
    status: MissionStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    report_text: Optional[str] = None
    report_generated_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MissionStatusUpdate(BaseModel):
    status: MissionStatus


class InspectionImageResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    filename: str
    content_type: str
    captured_at: Optional[datetime]
    uploaded_at: datetime
    url: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Mission Endpoints ---

@router.post("/missions", response_model=MissionResponse, status_code=201)
async def create_mission(mission: MissionCreate, db: AsyncSession = Depends(get_db)):
    db_mission = Mission(**mission.model_dump())
    db.add(db_mission)
    await db.commit()
    await db.refresh(db_mission)
    return db_mission


@router.get("/missions", response_model=list[MissionResponse])
async def list_missions(
    status: Optional[MissionStatus] = None,
    drone_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Mission)
    if status:
        query = query.where(Mission.status == status)
    if drone_id:
        query = query.where(Mission.drone_id == drone_id)
    query = query.order_by(Mission.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/missions/{mission_id}", response_model=MissionResponse)
async def get_mission(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@router.patch("/missions/{mission_id}/status", response_model=MissionResponse)
async def update_mission_status(
    mission_id: uuid.UUID,
    update: MissionStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    mission.status = update.status
    if update.status == MissionStatus.IN_PROGRESS and not mission.started_at:
        mission.started_at = datetime.utcnow()
    elif update.status == MissionStatus.COMPLETED:
        mission.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(mission)
    return mission


# --- Inspection Image Endpoints ---

@router.post("/missions/{mission_id}/images", response_model=InspectionImageResponse, status_code=201)
async def upload_inspection_image(
    mission_id: uuid.UUID,
    file: UploadFile = File(...),
    captured_at: Optional[datetime] = Form(None),
    metadata_json: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    object_key = f"missions/{mission_id}/{file.filename}"
    await upload_file(
        file_data=await file.read(),
        object_key=object_key,
        content_type=file.content_type or "image/jpeg",
    )

    db_image = InspectionImage(
        mission_id=mission_id,
        filename=file.filename,
        object_key=object_key,
        content_type=file.content_type or "image/jpeg",
        captured_at=captured_at,
        metadata_json=metadata_json,
    )
    db.add(db_image)
    await db.commit()
    await db.refresh(db_image)
    return db_image


@router.get("/missions/{mission_id}/images", response_model=list[InspectionImageResponse])
async def list_mission_images(
    mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionImage)
        .where(InspectionImage.mission_id == mission_id)
        .order_by(InspectionImage.uploaded_at)
    )
    images = result.scalars().all()
    response = []
    for img in images:
        img_dict = InspectionImageResponse.model_validate(img)
        img_dict.url = await get_presigned_url(img.object_key)
        response.append(img_dict)
    return response
