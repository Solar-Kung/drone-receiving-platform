"""
Flight Orchestrator — drives the per-drone flight lifecycle.

State machine (no holding pattern):
  scheduled → in_flight → approaching → landing → landed → completed

Transitions are triggered by the position callback registered on each
TelemetrySimulator.  No Redis pub/sub — direct async calls only.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session
from app.models.drone import Drone
from app.models.flight import FlightRecord, FlightStatus
from app.models.landing import LandingPad
from app.services.flight_tracker import flight_tracker
from app.services.landing_manager import landing_manager

logger = logging.getLogger(__name__)

DRONE_SPECS = [
    {"name": "Taipei River Patrol", "model": "DJI Matrice 300", "serial_number": "SN-TPE-001"},
    {"name": "Solar Farm Scanner", "model": "DJI Mavic 3E", "serial_number": "SN-SOL-002"},
    {"name": "Bridge Inspector", "model": "DJI Matrice 350", "serial_number": "SN-BRG-003"},
]

LANDING_PADS = [
    {"name": "Songshan Pad A", "latitude": 25.0634, "longitude": 121.5522, "has_charger": True},
    {"name": "Yuanshan Pad B", "latitude": 25.0720, "longitude": 121.5200, "has_charger": True},
    {"name": "Dazhi Pad C", "latitude": 25.0780, "longitude": 121.5310, "has_charger": False},
]

# Ordered to match DRONE_SPECS indices
_SIM_IDS = ["drone-001", "drone-002", "drone-003"]


class FlightOrchestrator:
    def __init__(self, base_url: str):
        self.base_url = base_url
        # drone_id (e.g. "drone-001") → DB UUID of Drone row
        self._drone_uuids: dict[str, uuid.UUID] = {}
        # drone_id → UUID of active FlightRecord
        self._flight_ids: dict[str, uuid.UUID] = {}
        # drone_id → current FlightStatus (in-memory, authoritative for transitions)
        self._flight_statuses: dict[str, FlightStatus] = {}
        # drone_id → UUID of LandingSchedule (None if no pad assigned)
        self._schedule_ids: dict[str, uuid.UUID | None] = {}
        # drone_id → UUID of the reserved/occupied LandingPad (None if none)
        self._pad_ids: dict[str, uuid.UUID | None] = {}
        # Per-drone lock to serialise concurrent callback invocations
        self._locks: dict[str, asyncio.Lock] = {
            sim_id: asyncio.Lock() for sim_id in _SIM_IDS
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def seed_data(self):
        """Idempotently insert drone records and landing pads."""
        async with async_session() as db:
            for sim_id, spec in zip(_SIM_IDS, DRONE_SPECS):
                result = await db.execute(
                    select(Drone).where(Drone.serial_number == spec["serial_number"])
                )
                drone = result.scalar_one_or_none()
                if drone is None:
                    drone = Drone(**spec)
                    db.add(drone)
                    await db.flush()
                    logger.info("Seeded drone %s (%s)", spec["serial_number"], sim_id)
                self._drone_uuids[sim_id] = drone.id
            await db.commit()

            for pad_spec in LANDING_PADS:
                result = await db.execute(
                    select(LandingPad).where(LandingPad.name == pad_spec["name"])
                )
                if result.scalar_one_or_none() is None:
                    db.add(LandingPad(**pad_spec))
                    logger.info("Seeded landing pad: %s", pad_spec["name"])
            await db.commit()

    def attach_to_fleet(self, fleet) -> None:
        """Wire per-drone position callbacks onto each TelemetrySimulator."""
        for drone_id, sim in fleet.simulators.items():
            sim.on_position_update = self._make_callback(drone_id)
        logger.info("Orchestrator callbacks attached to %d simulators", len(fleet.simulators))

    async def start(self):
        """Create a FlightRecord (scheduled) for every seeded drone."""
        async with async_session() as db:
            for sim_id, drone_uuid in self._drone_uuids.items():
                flight = FlightRecord(drone_id=drone_uuid, status=FlightStatus.SCHEDULED)
                db.add(flight)
                await db.flush()
                self._flight_ids[sim_id] = flight.id
                self._flight_statuses[sim_id] = FlightStatus.SCHEDULED
                self._schedule_ids[sim_id] = None
                self._pad_ids[sim_id] = None
                logger.info("Flight %s created for %s (scheduled)", flight.id, sim_id)
            await db.commit()

    async def stop(self):
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_callback(self, drone_id: str):
        async def callback(d_id: str, point: dict) -> None:
            await self._on_position_update(d_id, point)
        return callback

    async def _on_position_update(self, drone_id: str, point: dict) -> None:
        flight_id = self._flight_ids.get(drone_id)
        if not flight_id:
            # orchestrator.start() hasn't run yet — skip
            return

        current_status = self._flight_statuses.get(drone_id, FlightStatus.SCHEDULED)
        if current_status == FlightStatus.COMPLETED:
            return

        battery = point.get("battery_level", 100.0)
        segment_idx = point.get("segment_idx", 0)
        total_segments = point.get("total_segments", 1)
        alt = point.get("alt", 0.0)

        # Fast-path exits — avoid acquiring lock + DB session on every tick
        if current_status == FlightStatus.IN_FLIGHT and battery > 0 and segment_idx < total_segments * 0.8:
            return
        if current_status == FlightStatus.LANDING and alt > 5.0 and battery > 0:
            return
        if current_status == FlightStatus.LANDED and battery > 0:
            return

        lock = self._locks.get(drone_id)
        if lock is None:
            return

        async with lock:
            # Re-read status under lock to avoid double transitions
            current_status = self._flight_statuses.get(drone_id, FlightStatus.SCHEDULED)
            if current_status == FlightStatus.COMPLETED:
                return

            async with async_session() as db:
                await self._transition(drone_id, flight_id, current_status, battery, segment_idx, total_segments, alt, db)

    async def _transition(
        self,
        drone_id: str,
        flight_id: uuid.UUID,
        status: FlightStatus,
        battery: float,
        segment_idx: int,
        total_segments: int,
        alt: float,
        db,
    ) -> None:
        # Battery depleted — complete flight from any state
        if battery <= 0.0:
            pad_id = self._pad_ids.get(drone_id)
            if pad_id:
                await landing_manager.release_pad(pad_id, db)
                self._pad_ids[drone_id] = None
            await flight_tracker.update_flight_status(flight_id, FlightStatus.COMPLETED, db)
            self._flight_statuses[drone_id] = FlightStatus.COMPLETED
            logger.info("[%s] battery depleted → completed", drone_id)
            return

        if status == FlightStatus.SCHEDULED:
            await flight_tracker.update_flight_status(flight_id, FlightStatus.IN_FLIGHT, db)
            self._flight_statuses[drone_id] = FlightStatus.IN_FLIGHT
            logger.info("[%s] scheduled → in_flight", drone_id)

        elif status == FlightStatus.IN_FLIGHT and segment_idx >= total_segments * 0.8:
            # Transition through APPROACHING (transient) directly to LANDING
            await flight_tracker.update_flight_status(flight_id, FlightStatus.APPROACHING, db)
            self._flight_statuses[drone_id] = FlightStatus.APPROACHING
            logger.info("[%s] in_flight → approaching (seg %d/%d)", drone_id, segment_idx, total_segments)

            schedule = await landing_manager.assign_pad(
                flight_id=flight_id,
                pad_id=None,
                scheduled_time=datetime.now(timezone.utc),
                db=db,
            )
            if schedule:
                self._schedule_ids[drone_id] = schedule.id
                self._pad_ids[drone_id] = schedule.pad_id
                logger.info("[%s] pad assigned → landing", drone_id)
            else:
                logger.warning("[%s] no pad available — landing without pad assignment", drone_id)

            await flight_tracker.update_flight_status(flight_id, FlightStatus.LANDING, db)
            self._flight_statuses[drone_id] = FlightStatus.LANDING

        elif status == FlightStatus.LANDING and alt <= 5.0:
            schedule_id = self._schedule_ids.get(drone_id)
            if schedule_id:
                await landing_manager.complete_landing(schedule_id, db)
            await flight_tracker.update_flight_status(flight_id, FlightStatus.LANDED, db)
            self._flight_statuses[drone_id] = FlightStatus.LANDED
            logger.info("[%s] landing → landed (alt=%.1fm)", drone_id, alt)
