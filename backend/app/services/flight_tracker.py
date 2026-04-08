"""
Flight Tracker Service

Manages real-time flight tracking, telemetry persistence,
and flight state transitions.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import manager
from app.database import async_session
from app.models.flight import FlightRecord, FlightStatus, TelemetryData
from app.ros_bridge.telemetry_sub import TelemetryMessage

logger = logging.getLogger(__name__)


class FlightTracker:
    """Processes incoming telemetry and manages flight lifecycle."""

    async def handle_telemetry(self, msg: TelemetryMessage):
        """Store telemetry data and broadcast to WebSocket clients."""
        async with async_session() as db:
            telemetry = TelemetryData(
                drone_id=uuid.UUID(msg.drone_id) if msg.drone_id != "mock-drone-001" else None,
                flight_id=uuid.UUID(msg.flight_id) if msg.flight_id != "mock-flight-001" else None,
                latitude=msg.latitude,
                longitude=msg.longitude,
                altitude=msg.altitude,
                speed=msg.speed,
                heading=msg.heading,
                battery_level=msg.battery_level,
                signal_strength=msg.signal_strength,
                status_message=msg.status_message,
            )
            if telemetry.drone_id and telemetry.flight_id:
                db.add(telemetry)
                await db.commit()

        # Broadcast to WebSocket regardless of DB storage
        await manager.broadcast("telemetry", {
            "type": "telemetry_update",
            "data": msg.to_dict(),
        })

    async def update_flight_status(
        self, flight_id: uuid.UUID, new_status: FlightStatus, db: AsyncSession
    ):
        result = await db.execute(
            select(FlightRecord).where(FlightRecord.id == flight_id)
        )
        flight = result.scalar_one_or_none()
        if not flight:
            logger.warning(f"Flight {flight_id} not found")
            return None

        flight.status = new_status

        if new_status == FlightStatus.IN_FLIGHT and not flight.takeoff_time:
            flight.takeoff_time = datetime.now(timezone.utc)
        elif new_status in (FlightStatus.LANDED, FlightStatus.COMPLETED):
            flight.landing_time = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(flight)

        await manager.broadcast("flights", {
            "type": "flight_status_change",
            "data": {
                "flight_id": str(flight_id),
                "status": new_status.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        })
        return flight

    async def check_battery_alerts(self, msg: TelemetryMessage):
        """Send alert if battery level is critically low."""
        if msg.battery_level < 20:
            await manager.broadcast("telemetry", {
                "type": "alert",
                "severity": "warning" if msg.battery_level >= 10 else "critical",
                "data": {
                    "drone_id": msg.drone_id,
                    "message": f"Low battery: {msg.battery_level:.1f}%",
                    "battery_level": msg.battery_level,
                },
            })


flight_tracker = FlightTracker()
