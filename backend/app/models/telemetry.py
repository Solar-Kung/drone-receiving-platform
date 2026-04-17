import uuid
from datetime import datetime

from sqlalchemy import String, Float, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TelemetryData(Base):
    """
    Phase 1 TelemetryData model.

    drone_id is a plain string — no FK to the drones table.
    (id, timestamp) is the primary key pair; TimescaleDB requires that all
    unique constraints include the hypertable partition column (timestamp).
    """
    __tablename__ = "telemetry_data"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    drone_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Core telemetry (Phase 1)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Extended telemetry fields — nullable until Phase 2
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
