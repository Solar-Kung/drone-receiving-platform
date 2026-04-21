"""
Flight Orchestrator — drives the per-drone flight lifecycle.

State machine:
  scheduled → in_flight → approaching → landing → landed → completed

Mission lifecycle (parallel):
  created → in_progress → data_uploading → completed
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.api.websocket import manager
from app.database import async_session
from app.services import inspection_image_generator
from app.models.drone import Drone
from app.models.flight import FlightRecord, FlightStatus
from app.models.landing import LandingPad
from app.models.mission import Mission, MissionStatus
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

_SIM_IDS = ["drone-001", "drone-002", "drone-003"]

_SIM_DESCRIPTIONS = {
    "drone-001": "Keelung River corridor patrol and infrastructure inspection",
    "drone-002": "Solar panel array grid scan (Zhonghe)",
    "drone-003": "Bridge structural inspection (Xinbei Bridge)",
}


class FlightOrchestrator:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._drone_uuids: dict[str, uuid.UUID] = {}
        self._flight_ids: dict[str, uuid.UUID] = {}
        self._flight_statuses: dict[str, FlightStatus] = {}
        self._schedule_ids: dict[str, uuid.UUID | None] = {}
        self._pad_ids: dict[str, uuid.UUID | None] = {}
        self._mission_ids: dict[str, uuid.UUID] = {}
        self._last_segment_idx: dict[str, int] = {}
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
        """Create a FlightRecord (scheduled) for every seeded drone, then create missions."""
        # Step 1: create flights
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

        # Step 2: create missions (independent — failure does not affect flights)
        for sim_id, drone_uuid in self._drone_uuids.items():
            try:
                flight_id = self._flight_ids[sim_id]
                spec_idx = _SIM_IDS.index(sim_id)
                spec_name = DRONE_SPECS[spec_idx]["name"]
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
                async with async_session() as db:
                    mission = Mission(
                        drone_id=drone_uuid,
                        flight_id=flight_id,
                        name=f"{spec_name} — {timestamp}",
                        description=_SIM_DESCRIPTIONS.get(sim_id),
                        status=MissionStatus.CREATED,
                    )
                    db.add(mission)
                    await db.commit()
                    await db.refresh(mission)
                    self._mission_ids[sim_id] = mission.id
                    logger.info("Mission %s created for %s", mission.id, sim_id)
            except Exception as exc:
                logger.error("Mission creation failed for %s: %s", sim_id, exc)

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
            return

        current_status = self._flight_statuses.get(drone_id, FlightStatus.SCHEDULED)
        if current_status == FlightStatus.COMPLETED:
            return

        battery = point.get("battery_level", 100.0)
        segment_idx = point.get("segment_idx", 0)
        total_segments = point.get("total_segments", 1)
        alt = point.get("alt", 0.0)

        # Waypoint progress tracking — runs before fast-path so every tick is checked
        last_seg = self._last_segment_idx.get(drone_id, -1)
        if segment_idx != last_seg:
            self._last_segment_idx[drone_id] = segment_idx
            mission_id = self._mission_ids.get(drone_id)
            if mission_id and current_status in (
                FlightStatus.IN_FLIGHT,
                FlightStatus.APPROACHING,
                FlightStatus.LANDING,
            ):
                progress = round(segment_idx / total_segments * 100, 1)
                await manager.broadcast("telemetry", {
                    "type": "mission_progress",
                    "drone_id": drone_id,
                    "data": {
                        "mission_id": str(mission_id),
                        "current_waypoint": segment_idx,
                        "total_waypoints": total_segments,
                        "progress": progress,
                    },
                })
                # Generate inspection image for mid-route waypoints (skip first and last)
                is_takeoff = segment_idx == 0
                is_landing = segment_idx >= total_segments - 1
                if not is_takeoff and not is_landing:
                    lat = point.get("lat", 0.0)
                    lon = point.get("lon", 0.0)
                    asyncio.create_task(
                        self._generate_inspection_image(
                            mission_id, drone_id, segment_idx, total_segments, lat, lon,
                        )
                    )

        # Fast-path exits — avoid lock + DB session on every tick
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
            current_status = self._flight_statuses.get(drone_id, FlightStatus.SCHEDULED)
            if current_status == FlightStatus.COMPLETED:
                return

            async with async_session() as db:
                await self._transition(
                    drone_id, flight_id, current_status,
                    battery, segment_idx, total_segments, alt, db,
                )

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
        # Battery depleted — complete flight (and mission) from any state
        if battery <= 0.0:
            pad_id = self._pad_ids.get(drone_id)
            if pad_id:
                await landing_manager.release_pad(pad_id, db)
                self._pad_ids[drone_id] = None
            await flight_tracker.update_flight_status(flight_id, FlightStatus.COMPLETED, db)
            self._flight_statuses[drone_id] = FlightStatus.COMPLETED
            logger.info("[%s] battery depleted → completed", drone_id)
            await self._complete_mission(drone_id, db)
            return

        if status == FlightStatus.SCHEDULED:
            await flight_tracker.update_flight_status(flight_id, FlightStatus.IN_FLIGHT, db)
            self._flight_statuses[drone_id] = FlightStatus.IN_FLIGHT
            logger.info("[%s] scheduled → in_flight", drone_id)
            # Mission: created → in_progress
            mission_id = self._mission_ids.get(drone_id)
            if mission_id:
                result = await db.execute(select(Mission).where(Mission.id == mission_id))
                m = result.scalar_one_or_none()
                if m and m.status == MissionStatus.CREATED:
                    m.status = MissionStatus.IN_PROGRESS
                    m.started_at = datetime.now(timezone.utc)
                    await db.commit()
                    logger.info("[%s] mission → in_progress", drone_id)

        elif status == FlightStatus.IN_FLIGHT and segment_idx >= total_segments * 0.8:
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
            # Mission: in_progress → data_uploading
            mission_id = self._mission_ids.get(drone_id)
            if mission_id:
                result = await db.execute(select(Mission).where(Mission.id == mission_id))
                m = result.scalar_one_or_none()
                if m and m.status == MissionStatus.IN_PROGRESS:
                    m.status = MissionStatus.DATA_UPLOADING
                    await db.commit()
                    logger.info("[%s] mission → data_uploading", drone_id)

    async def _generate_inspection_image(
        self,
        mission_id: uuid.UUID,
        drone_id: str,
        waypoint_idx: int,
        total_waypoints: int,
        lat: float,
        lon: float,
    ) -> None:
        """Non-blocking wrapper around inspection_image_generator."""
        image_record = await inspection_image_generator.generate_and_upload(
            mission_id=mission_id,
            drone_id=drone_id,
            waypoint_idx=waypoint_idx,
            total_waypoints=total_waypoints,
            latitude=lat,
            longitude=lon,
        )
        if image_record:
            await manager.broadcast("telemetry", {
                "type": "inspection_image",
                "drone_id": drone_id,
                "data": {
                    "mission_id": str(mission_id),
                    "image_id": str(image_record.id),
                    "filename": image_record.filename,
                    "waypoint_idx": waypoint_idx,
                },
            })

    async def _complete_mission(self, drone_id: str, db) -> None:
        """Mark mission as COMPLETED. Called when flight reaches COMPLETED."""
        mission_id = self._mission_ids.get(drone_id)
        if not mission_id:
            return
        try:
            result = await db.execute(select(Mission).where(Mission.id == mission_id))
            m = result.scalar_one_or_none()
            if m and m.status != MissionStatus.COMPLETED:
                m.status = MissionStatus.COMPLETED
                m.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info("[%s] mission %s → completed", drone_id, mission_id)
        except Exception as exc:
            logger.error("[%s] failed to complete mission: %s", drone_id, exc)
