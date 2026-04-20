"""
Telemetry Simulator — posts GPS + extended telemetry to the REST API at 1 Hz.

Phase 3 additions:
  - on_position_update callback: called after each successful POST so the
    FlightOrchestrator can drive state transitions without polling.
  - Battery stop: once battery reaches 0 % the simulator exits cleanly.
  - Single-route semantics: the route loops while battery > 0; when battery
    hits 0 the loop exits and is_stopped becomes True.
"""

import asyncio
import logging
import math
import random
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class TelemetrySimulator:
    def __init__(
        self,
        drone_id: str,
        route: list[dict[str, Any]],
        base_url: str,
        speed_multiplier: float = 1.0,
        on_position_update: Optional[Callable[[str, dict], Awaitable[None]]] = None,
    ):
        self.drone_id = drone_id
        self.route = route
        self.base_url = base_url
        self.speed_multiplier = speed_multiplier
        self.on_position_update = on_position_update
        self.running = False
        self._stopped = False

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    async def start(self):
        self.running = True
        self._stopped = False
        # Wait for the FastAPI server to finish startup before sending the
        # first POST so we don't hit "connection refused".
        await asyncio.sleep(3)

        elapsed_seconds = 0
        total_segments = len(self.route) - 1

        async with httpx.AsyncClient(timeout=10.0) as client:
            done = False
            while self.running and not done:
                for segment_idx in range(total_segments):
                    if not self.running or done:
                        break

                    start_wp = self.route[segment_idx]
                    end_wp = self.route[segment_idx + 1]
                    steps = max(int(self._distance(start_wp, end_wp) / 0.0003), 5)
                    heading = self._heading(start_wp, end_wp)

                    for step in range(steps):
                        if not self.running or done:
                            break

                        t = step / steps
                        point = self._interpolate(start_wp, end_wp, t)
                        battery = max(0.0, 100.0 - elapsed_seconds * 0.05)
                        signal = 95.0 + random.uniform(-3.0, 3.0)

                        payload = {
                            "drone_id": self.drone_id,
                            "latitude": point["lat"],
                            "longitude": point["lon"],
                            "altitude": point["alt"],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "battery_level": round(battery, 2),
                            "speed": 10.0,
                            "heading": round(heading, 1),
                            "signal_strength": round(signal, 1),
                        }

                        try:
                            await client.post(
                                f"{self.base_url}/api/v1/telemetry", json=payload
                            )
                        except Exception as exc:
                            logger.warning("[%s] POST failed: %s", self.drone_id, exc)

                        # Callback after successful (or attempted) POST
                        if self.on_position_update is not None:
                            try:
                                await self.on_position_update(
                                    self.drone_id,
                                    {
                                        "lat": point["lat"],
                                        "lon": point["lon"],
                                        "alt": point["alt"],
                                        "battery_level": round(battery, 2),
                                        "speed": 10.0,
                                        "heading": round(heading, 1),
                                        "segment_idx": segment_idx,
                                        "total_segments": total_segments,
                                    },
                                )
                            except Exception as exc:
                                logger.warning(
                                    "[%s] Position callback error: %s",
                                    self.drone_id,
                                    exc,
                                )

                        elapsed_seconds += 1

                        if battery <= 0.0:
                            logger.info(
                                "[%s] Battery depleted after %ds — stopping.",
                                self.drone_id,
                                elapsed_seconds,
                            )
                            done = True
                            break

                        await asyncio.sleep(1.0 / self.speed_multiplier)

        self.running = False
        self._stopped = True

    async def stop(self):
        self.running = False
        self._stopped = True

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
        return math.degrees(math.atan2(dlon, dlat)) % 360
