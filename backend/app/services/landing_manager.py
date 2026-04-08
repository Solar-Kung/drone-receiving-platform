"""
Landing Manager Service

Manages landing pad allocation, scheduling, and auto-guidance
for incoming drones.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import manager
from app.database import async_session
from app.models.landing import LandingPad, LandingSchedule, PadStatus

logger = logging.getLogger(__name__)


class LandingManager:
    """Coordinates drone landings across available pads."""

    async def find_available_pad(self, db: AsyncSession) -> LandingPad | None:
        """Find the first available landing pad."""
        result = await db.execute(
            select(LandingPad).where(LandingPad.status == PadStatus.AVAILABLE)
        )
        return result.scalar_one_or_none()

    async def assign_pad(
        self,
        flight_id: uuid.UUID,
        pad_id: uuid.UUID | None,
        scheduled_time: datetime,
        db: AsyncSession,
    ) -> LandingSchedule | None:
        """Assign a landing pad to a flight. Auto-selects if pad_id is None."""
        if pad_id is None:
            pad = await self.find_available_pad(db)
            if not pad:
                logger.warning("No available landing pads")
                return None
            pad_id = pad.id
        else:
            result = await db.execute(
                select(LandingPad).where(LandingPad.id == pad_id)
            )
            pad = result.scalar_one_or_none()
            if not pad or pad.status != PadStatus.AVAILABLE:
                logger.warning(f"Pad {pad_id} not available")
                return None

        # Reserve the pad
        pad.status = PadStatus.RESERVED

        schedule = LandingSchedule(
            flight_id=flight_id,
            pad_id=pad_id,
            scheduled_time=scheduled_time,
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)

        await manager.broadcast("landings", {
            "type": "pad_assigned",
            "data": {
                "flight_id": str(flight_id),
                "pad_id": str(pad_id),
                "pad_name": pad.name,
                "scheduled_time": scheduled_time.isoformat(),
            },
        })

        return schedule

    async def complete_landing(
        self, schedule_id: uuid.UUID, db: AsyncSession
    ):
        """Mark a landing as completed and free the pad."""
        result = await db.execute(
            select(LandingSchedule).where(LandingSchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        if not schedule:
            return None

        schedule.actual_time = datetime.now(timezone.utc)

        # Update pad status to occupied (drone is on the pad)
        pad_result = await db.execute(
            select(LandingPad).where(LandingPad.id == schedule.pad_id)
        )
        pad = pad_result.scalar_one_or_none()
        if pad:
            pad.status = PadStatus.OCCUPIED

        await db.commit()

        await manager.broadcast("landings", {
            "type": "landing_completed",
            "data": {
                "schedule_id": str(schedule_id),
                "pad_id": str(schedule.pad_id),
                "actual_time": schedule.actual_time.isoformat(),
            },
        })
        return schedule

    async def release_pad(self, pad_id: uuid.UUID, db: AsyncSession):
        """Release a landing pad back to available status."""
        result = await db.execute(
            select(LandingPad).where(LandingPad.id == pad_id)
        )
        pad = result.scalar_one_or_none()
        if pad:
            pad.status = PadStatus.AVAILABLE
            await db.commit()

            await manager.broadcast("landings", {
                "type": "pad_released",
                "data": {"pad_id": str(pad_id), "pad_name": pad.name},
            })


landing_manager = LandingManager()
