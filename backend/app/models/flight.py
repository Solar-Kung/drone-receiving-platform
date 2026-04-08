import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Float, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FlightStatus(str, PyEnum):
    SCHEDULED = "scheduled"
    IN_FLIGHT = "in_flight"
    APPROACHING = "approaching"
    LANDING = "landing"
    LANDED = "landed"
    COMPLETED = "completed"
    ABORTED = "aborted"


class FlightRecord(Base):
    __tablename__ = "flight_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    status: Mapped[FlightStatus] = mapped_column(Enum(FlightStatus), default=FlightStatus.SCHEDULED)
    takeoff_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    landing_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    drone = relationship("Drone", back_populates="flights")


class TelemetryData(Base):
    """Time-series telemetry data - optimized with TimescaleDB hypertable."""
    __tablename__ = "telemetry_data"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    drone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("drones.id"), primary_key=True)
    flight_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("flight_records.id"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[float] = mapped_column(Float, default=0.0)
    heading: Mapped[float] = mapped_column(Float, default=0.0)
    battery_level: Mapped[float] = mapped_column(Float, default=100.0)
    signal_strength: Mapped[float] = mapped_column(Float, default=0.0)
    status_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
