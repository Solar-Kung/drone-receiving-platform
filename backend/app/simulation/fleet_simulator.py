"""
Fleet Simulator — manages multiple TelemetrySimulator instances with staggered starts.
"""

import asyncio
import logging

from app.simulation.routes import TAIPEI_ROUTE, SOLAR_FARM_ROUTE, BRIDGE_INSPECTION_ROUTE
from app.simulation.telemetry_simulator import TelemetrySimulator

logger = logging.getLogger(__name__)

_FLEET_CONFIG = [
    ("drone-001", TAIPEI_ROUTE, 0),         # start immediately
    ("drone-002", SOLAR_FARM_ROUTE, 30),    # start after 30 s
    ("drone-003", BRIDGE_INSPECTION_ROUTE, 60),  # start after 60 s
]


class FleetSimulator:
    """Manages multiple TelemetrySimulator instances with staggered starts."""

    def __init__(self, base_url: str, speed_multiplier: float = 1.0):
        self.base_url = base_url
        self.speed_multiplier = speed_multiplier
        self.paused = False
        self._tasks: list[asyncio.Task] = []

        # Create simulators up-front so callbacks can be wired before start().
        self.simulators: dict[str, TelemetrySimulator] = {
            drone_id: TelemetrySimulator(
                drone_id=drone_id,
                route=route,
                base_url=base_url,
                speed_multiplier=speed_multiplier,
            )
            for drone_id, route, _ in _FLEET_CONFIG
        }
        self._delays: dict[str, int] = {
            drone_id: delay for drone_id, _, delay in _FLEET_CONFIG
        }

    async def start(self):
        for drone_id, sim in self.simulators.items():
            delay = self._delays[drone_id]
            task = asyncio.create_task(self._start_delayed(sim, delay))
            self._tasks.append(task)
            logger.info("Scheduled %s with %ds delay", drone_id, delay)

    async def _start_delayed(self, sim: TelemetrySimulator, delay: int):
        if delay > 0:
            await asyncio.sleep(delay)
        await sim.start()

    def pause(self) -> None:
        self.paused = True
        for sim in self.simulators.values():
            sim.paused = True
        logger.info("Fleet paused")

    def resume(self) -> None:
        self.paused = False
        for sim in self.simulators.values():
            sim.paused = False
        logger.info("Fleet resumed")

    def set_speed(self, multiplier: float) -> None:
        self.speed_multiplier = multiplier
        for sim in self.simulators.values():
            sim.speed_multiplier = multiplier
        logger.info("Fleet speed set to %.1fx", multiplier)

    async def stop(self):
        for sim in self.simulators.values():
            await sim.stop()
        for task in self._tasks:
            task.cancel()
