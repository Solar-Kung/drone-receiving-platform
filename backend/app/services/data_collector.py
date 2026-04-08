"""
Data Collector Service

Handles incoming inspection data from drones including images,
sensor readings, and flight logs. Stores files in MinIO and
metadata in TimescaleDB.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket import manager
from app.database import async_session
from app.models.mission import Mission, MissionStatus, InspectionImage
from app.ros_bridge.image_sub import ImageMessage
from app.ros_bridge.mission_sub import MissionStatusMessage
from app.services.minio_client import upload_file

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects and stores inspection data from drone missions."""

    async def handle_image(self, msg: ImageMessage):
        """Process incoming drone camera image."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{msg.drone_id}_{timestamp}.{msg.encoding}"
        object_key = f"missions/{msg.mission_id}/{filename}"

        try:
            await upload_file(
                file_data=msg.image_data,
                object_key=object_key,
                content_type=f"image/{msg.encoding}",
            )

            async with async_session() as db:
                image = InspectionImage(
                    mission_id=uuid.UUID(msg.mission_id),
                    filename=filename,
                    object_key=object_key,
                    content_type=f"image/{msg.encoding}",
                    captured_at=datetime.fromisoformat(msg.timestamp),
                    metadata_json=json.dumps(msg.metadata) if msg.metadata else None,
                )
                db.add(image)
                await db.commit()

            await manager.broadcast("telemetry", {
                "type": "image_received",
                "data": {
                    "drone_id": msg.drone_id,
                    "mission_id": msg.mission_id,
                    "filename": filename,
                },
            })

            logger.info(f"Stored inspection image: {object_key}")

        except Exception as e:
            logger.error(f"Failed to store image: {e}")

    async def handle_mission_status(self, msg: MissionStatusMessage):
        """Process mission status update from drone."""
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Mission).where(Mission.id == uuid.UUID(msg.mission_id))
                )
                mission = result.scalar_one_or_none()
                if not mission:
                    logger.warning(f"Mission {msg.mission_id} not found")
                    return

                status_map = {
                    "created": MissionStatus.CREATED,
                    "in_progress": MissionStatus.IN_PROGRESS,
                    "data_uploading": MissionStatus.DATA_UPLOADING,
                    "completed": MissionStatus.COMPLETED,
                    "failed": MissionStatus.FAILED,
                }
                new_status = status_map.get(msg.status)
                if new_status:
                    mission.status = new_status
                    if new_status == MissionStatus.IN_PROGRESS and not mission.started_at:
                        mission.started_at = datetime.now(timezone.utc)
                    elif new_status == MissionStatus.COMPLETED:
                        mission.completed_at = datetime.now(timezone.utc)
                    await db.commit()

            await manager.broadcast("telemetry", {
                "type": "mission_status_update",
                "data": msg.to_dict(),
            })

        except Exception as e:
            logger.error(f"Failed to process mission status: {e}")


data_collector = DataCollector()
