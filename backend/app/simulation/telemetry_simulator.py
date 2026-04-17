"""
Telemetry Simulator — posts GPS data to the REST API at 1 Hz.

Uses linear interpolation between waypoints. Steps per segment are
derived from geographic distance so ground speed stays roughly constant.
The simulator loops indefinitely after completing a route.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TelemetrySimulator:
    def __init__(
        self,
        drone_id: str,
        route: list[dict[str, Any]],
        base_url: str,
        speed_multiplier: float = 1.0,  # reserved for Phase 4 control panel
    ):
        self.drone_id = drone_id
        self.route = route
        self.base_url = base_url
        self.speed_multiplier = speed_multiplier
        self.running = False

    async def start(self):
        self.running = True
        # Wait for the FastAPI server to finish its startup sequence before
        # sending the first POST so we don't hit a "connection refused" error.
        await asyncio.sleep(3)

        async with httpx.AsyncClient(timeout=10.0) as client:
            while self.running:
                for i in range(len(self.route) - 1):
                    if not self.running:
                        return
                    start_wp = self.route[i]
                    end_wp = self.route[i + 1]
                    steps = max(
                        int(self._distance(start_wp, end_wp) / 0.0003), 5
                    )
                    for step in range(steps):
                        if not self.running:
                            return
                        t = step / steps
                        point = self._interpolate(start_wp, end_wp, t)
                        try:
                            await client.post(
                                f"{self.base_url}/api/v1/telemetry",
                                json={
                                    "drone_id": self.drone_id,
                                    "latitude": point["lat"],
                                    "longitude": point["lon"],
                                    "altitude": point["alt"],
                                    "timestamp": datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                                },
                            )
                        except Exception as exc:
                            logger.warning("Simulator POST failed: %s", exc)
                        await asyncio.sleep(1.0 / self.speed_multiplier)

    async def stop(self):
        self.running = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _interpolate(
        start: dict[str, Any], end: dict[str, Any], t: float
    ) -> dict[str, float]:
        return {
            "lat": start["lat"] + (end["lat"] - start["lat"]) * t,
            "lon": start["lon"] + (end["lon"] - start["lon"]) * t,
            "alt": start["alt"] + (end["alt"] - start["alt"]) * t,
        }

    @staticmethod
    def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
        return ((a["lat"] - b["lat"]) ** 2 + (a["lon"] - b["lon"]) ** 2) ** 0.5
