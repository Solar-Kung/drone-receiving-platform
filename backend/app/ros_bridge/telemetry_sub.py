"""
ROS 2 Telemetry Subscriber

Subscribes to drone telemetry topics via DDS/ROS 2 and forwards
data to the FastAPI backend for storage and WebSocket broadcasting.

ROS 2 Topics:
  - /drone/{drone_id}/telemetry  (sensor_msgs/NavSatFix + custom)
  - /drone/{drone_id}/battery    (sensor_msgs/BatteryState)
  - /drone/{drone_id}/velocity   (geometry_msgs/TwistStamped)
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class TelemetryMessage:
    drone_id: str
    flight_id: str
    timestamp: str
    latitude: float
    longitude: float
    altitude: float
    speed: float = 0.0
    heading: float = 0.0
    battery_level: float = 100.0
    signal_strength: float = 0.0
    status_message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class TelemetrySubscriber:
    """
    Subscribes to ROS 2 telemetry topics and dispatches messages
    to registered handlers (DB persistence, WebSocket broadcast, etc.).
    """

    def __init__(self):
        self._handlers: list[Callable[[TelemetryMessage], Awaitable[None]]] = []
        self._running = False
        self._node = None

    def on_message(self, handler: Callable[[TelemetryMessage], Awaitable[None]]):
        self._handlers.append(handler)

    async def _dispatch(self, msg: TelemetryMessage):
        for handler in self._handlers:
            try:
                await handler(msg)
            except Exception as e:
                logger.error(f"Telemetry handler error: {e}")

    async def start(self):
        """
        Initialize ROS 2 node and subscribe to telemetry topics.

        Requires ROS 2 (rclpy) to be installed. Falls back to a mock
        mode for development without ROS 2.
        """
        self._running = True
        try:
            import rclpy
            from rclpy.node import Node
            from sensor_msgs.msg import NavSatFix, BatteryState
            from geometry_msgs.msg import TwistStamped

            rclpy.init()
            self._node = rclpy.create_node("telemetry_subscriber")

            self._node.create_subscription(
                NavSatFix,
                "/drone/+/telemetry",
                self._handle_navsatfix,
                10,
            )

            logger.info("ROS 2 telemetry subscriber started")

            while self._running:
                rclpy.spin_once(self._node, timeout_sec=0.1)
                await asyncio.sleep(0.01)

        except ImportError:
            logger.warning(
                "ROS 2 (rclpy) not available. Running in mock mode. "
                "Install ROS 2 Humble+ for production use."
            )
            await self._run_mock_mode()

    async def _run_mock_mode(self):
        """Generate mock telemetry data for development/testing."""
        import random

        base_lat, base_lon = 25.0330, 121.5654  # Taipei
        while self._running:
            msg = TelemetryMessage(
                drone_id="mock-drone-001",
                flight_id="mock-flight-001",
                timestamp=datetime.now(timezone.utc).isoformat(),
                latitude=base_lat + random.uniform(-0.01, 0.01),
                longitude=base_lon + random.uniform(-0.01, 0.01),
                altitude=random.uniform(50, 150),
                speed=random.uniform(0, 15),
                heading=random.uniform(0, 360),
                battery_level=max(0, 100 - random.uniform(0, 5)),
                signal_strength=random.uniform(70, 100),
            )
            await self._dispatch(msg)
            await asyncio.sleep(1.0)

    def _handle_navsatfix(self, msg):
        """Process ROS 2 NavSatFix message."""
        telemetry = TelemetryMessage(
            drone_id="unknown",
            flight_id="unknown",
            timestamp=datetime.now(timezone.utc).isoformat(),
            latitude=msg.latitude,
            longitude=msg.longitude,
            altitude=msg.altitude,
        )
        asyncio.get_event_loop().create_task(self._dispatch(telemetry))

    async def stop(self):
        self._running = False
        if self._node:
            self._node.destroy_node()
            import rclpy
            rclpy.shutdown()
        logger.info("Telemetry subscriber stopped")
