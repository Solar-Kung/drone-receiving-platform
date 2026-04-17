import uuid
from datetime import datetime

from pydantic import BaseModel


class TelemetryCreate(BaseModel):
    drone_id: str
    latitude: float
    longitude: float
    altitude: float
    timestamp: datetime


class TelemetryResponse(BaseModel):
    id: uuid.UUID
    drone_id: str
    latitude: float
    longitude: float
    altitude: float
    timestamp: datetime

    model_config = {"from_attributes": True}
