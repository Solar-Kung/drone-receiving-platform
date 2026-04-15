import uuid
from datetime import datetime

from sqlalchemy import String, Float, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TelemetryData(Base):
    """
    Phase 1 TelemetryData model — drone_id is a plain string, no FK to drones.

    Uses extend_existing=True to replace the legacy definition in flight.py
    without modifying that file. The replacements made here vs the legacy model:
      - 'time' (was composite PK)  → demoted to regular non-PK column
      - 'drone_id' (was UUID FK PK) → replaced with String(255), no FK, non-PK
      - 'id' UUID                  → new, primary key
      - 'timestamp' DateTime       → new, primary key (required by TimescaleDB
                                     hypertable: all unique constraints must
                                     include the partition column)
      - speed/heading/battery/signal → nullable (Phase 2 extended fields)

    The table will be recreated with a clean schema (id-only PK, no legacy
    columns) when the legacy model is removed in Phase 1B.
    """
    __tablename__ = "telemetry_data"
    __table_args__ = {"extend_existing": True}

    # Demotes legacy 'time' from primary key to a plain column
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Replaces legacy UUID FK primary key with a plain string identifier
    drone_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # New primary key pair — (id, timestamp) satisfies TimescaleDB's requirement
    # that all unique constraints include the hypertable time column
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

    # Core telemetry (Phase 1)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Extended telemetry fields enabled in Phase 2 (nullable until then)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
