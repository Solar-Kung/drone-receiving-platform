"""
ROS 2 Mission Status Subscriber

Subscribes to mission status updates from drones, including
task progress, waypoint completion, and mission state changes.

ROS 2 Topics:
  - /drone/{drone_id}/mission/status   (custom MissionStatus msg)
  - /drone/{drone_id}/mission/waypoint (geometry_msgs/PoseStamped)
"""

import asyncio
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class MissionStatusMessage:
    drone_id: str
    mission_id: str
    timestamp: str
    status: str  # created, in_progress, data_uploading, completed, failed
    progress: float = 0.0  # 0-100
    current_waypoint: int = 0
    total_waypoints: int = 0
    message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class MissionSubscriber:
    """
    Subscribes to ROS 2 mission status topics.
    Dispatches status updates for DB persistence and UI notifications.
    """

    def __init__(self):
        self._handlers: list[Callable[[MissionStatusMessage], Awaitable[None]]] = []
        self._running = False
        self._node = None

    def on_status(self, handler: Callable[[MissionStatusMessage], Awaitable[None]]):
        self._handlers.append(handler)

    async def _dispatch(self, msg: MissionStatusMessage):
        for handler in self._handlers:
            try:
                await handler(msg)
            except Exception as e:
                logger.error(f"Mission status handler error: {e}")

    async def start(self):
        self._running = True
        try:
            import rclpy
            from std_msgs.msg import String

            rclpy.init()
            self._node = rclpy.create_node("mission_subscriber")

            self._node.create_subscription(
                String,
                "/drone/+/mission/status",
                self._handle_mission_status,
                10,
            )

            logger.info("ROS 2 mission subscriber started")

            while self._running:
                rclpy.spin_once(self._node, timeout_sec=0.1)
                await asyncio.sleep(0.01)

        except ImportError:
            logger.warning(
                "ROS 2 (rclpy) not available. Mission subscriber in standby mode."
            )
            while self._running:
                await asyncio.sleep(5.0)

    def _handle_mission_status(self, msg):
        import json

        try:
            data = json.loads(msg.data)
            status = MissionStatusMessage(
                drone_id=data.get("drone_id", "unknown"),
                mission_id=data.get("mission_id", "unknown"),
                timestamp=datetime.now(timezone.utc).isoformat(),
                status=data.get("status", "unknown"),
                progress=data.get("progress", 0.0),
                current_waypoint=data.get("current_waypoint", 0),
                total_waypoints=data.get("total_waypoints", 0),
                message=data.get("message"),
            )
            asyncio.get_event_loop().create_task(self._dispatch(status))
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse mission status: {e}")

    async def stop(self):
        self._running = False
        if self._node:
            self._node.destroy_node()
        logger.info("Mission subscriber stopped")
