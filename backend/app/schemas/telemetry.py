import uuid
from datetime import datetime

from pydantic import BaseModel


class TelemetryCreate(BaseModel):
    drone_id: str
    latitude: float
    longitude: float
    altitude: float
    timestamp: datetime
    # Phase 2 extended fields — optional so Phase 1 clients remain compatible
    battery_level: float | None = None
    speed: float | None = None
    heading: float | None = None
    signal_strength: float | None = None


class TelemetryResponse(BaseModel):
    id: uuid.UUID
    drone_id: str
    latitude: float
    longitude: float
    altitude: float
    timestamp: datetime
    battery_level: float | None = None
    speed: float | None = None
    heading: float | None = None
    signal_strength: float | None = None

    model_config = {"from_attributes": True}
