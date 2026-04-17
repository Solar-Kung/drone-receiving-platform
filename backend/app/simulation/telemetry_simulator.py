"""
Telemetry Simulator — posts GPS + extended telemetry to the REST API at 1 Hz.

Extended fields added in Phase 2:
  - battery_level: linear drain from 100 % at 0.05 %/s
  - speed:         constant 10 m/s cruise placeholder
  - heading:       computed from atan2(Δlon, Δlat), 0-360°
  - signal_strength: 95 dB ± 3 random noise
"""

import asyncio
import logging
import math
import random
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

        elapsed_seconds = 0

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
                    heading = self._heading(start_wp, end_wp)

                    for step in range(steps):
                        if not self.running:
                            return
                        t = step / steps
                        point = self._interpolate(start_wp, end_wp, t)
                        battery = max(0.0, 100.0 - elapsed_seconds * 0.05)
                        signal = 95.0 + random.uniform(-3.0, 3.0)

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
                                    "battery_level": round(battery, 2),
                                    "speed": 10.0,
                                    "heading": round(heading, 1),
                                    "signal_strength": round(signal, 1),
                                },
                            )
                        except Exception as exc:
                            logger.warning("Simulator POST failed: %s", exc)

                        elapsed_seconds += 1
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

    @staticmethod
    def _heading(a: dict[str, Any], b: dict[str, Any]) -> float:
        """Bearing from a to b in degrees (0 = north, clockwise)."""
        dlat = b["lat"] - a["lat"]
        dlon = b["lon"] - a["lon"]
        angle = math.degrees(math.atan2(dlon, dlat))
        return angle % 360
