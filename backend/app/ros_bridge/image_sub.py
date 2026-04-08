"""
ROS 2 Image Subscriber

Subscribes to drone camera image topics and forwards them to
the data collection service for storage in MinIO.

ROS 2 Topics:
  - /drone/{drone_id}/camera/image_raw   (sensor_msgs/Image)
  - /drone/{drone_id}/camera/compressed  (sensor_msgs/CompressedImage)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ImageMessage:
    drone_id: str
    mission_id: str
    timestamp: str
    image_data: bytes
    encoding: str = "jpeg"
    width: int = 0
    height: int = 0
    metadata: Optional[dict] = None


class ImageSubscriber:
    """
    Subscribes to ROS 2 image topics from drone cameras.
    Received images are forwarded to handlers for storage and processing.
    """

    def __init__(self):
        self._handlers: list[Callable[[ImageMessage], Awaitable[None]]] = []
        self._running = False
        self._node = None

    def on_image(self, handler: Callable[[ImageMessage], Awaitable[None]]):
        self._handlers.append(handler)

    async def _dispatch(self, msg: ImageMessage):
        for handler in self._handlers:
            try:
                await handler(msg)
            except Exception as e:
                logger.error(f"Image handler error: {e}")

    async def start(self):
        self._running = True
        try:
            import rclpy
            from sensor_msgs.msg import CompressedImage

            rclpy.init()
            self._node = rclpy.create_node("image_subscriber")

            self._node.create_subscription(
                CompressedImage,
                "/drone/+/camera/compressed",
                self._handle_compressed_image,
                10,
            )

            logger.info("ROS 2 image subscriber started")

            while self._running:
                rclpy.spin_once(self._node, timeout_sec=0.1)
                await asyncio.sleep(0.01)

        except ImportError:
            logger.warning(
                "ROS 2 (rclpy) not available. Image subscriber in standby mode."
            )
            while self._running:
                await asyncio.sleep(5.0)

    def _handle_compressed_image(self, msg):
        image = ImageMessage(
            drone_id="unknown",
            mission_id="unknown",
            timestamp=datetime.now(timezone.utc).isoformat(),
            image_data=bytes(msg.data),
            encoding=msg.format,
        )
        asyncio.get_event_loop().create_task(self._dispatch(image))

    async def stop(self):
        self._running = False
        if self._node:
            self._node.destroy_node()
        logger.info("Image subscriber stopped")
