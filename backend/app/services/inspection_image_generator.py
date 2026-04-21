"""
Inspection Image Generator

Generates a placeholder JPEG inspection image using Pillow,
uploads it to MinIO, and creates an InspectionImage DB record.
"""

import io
import logging
import uuid
from datetime import datetime, timezone

from app.database import async_session
from app.models.mission import InspectionImage
from app.services.minio_client import upload_file

logger = logging.getLogger(__name__)


async def generate_and_upload(
    mission_id: uuid.UUID,
    drone_id: str,
    waypoint_idx: int,
    total_waypoints: int,
    latitude: float,
    longitude: float,
) -> InspectionImage | None:
    """
    Generate a placeholder inspection image, upload to MinIO,
    create InspectionImage DB record, and return it.
    Returns None on any failure (caller should handle gracefully).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

        now = datetime.now(timezone.utc)
        iso_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build image
        img = Image.new("RGB", (800, 600), color=(10, 10, 10))
        draw = ImageDraw.Draw(img)

        lines = [
            "INSPECTION CAPTURE",
            f"Drone: {drone_id}",
            f"Waypoint: {waypoint_idx}/{total_waypoints}",
            f"Location: {latitude:.5f}, {longitude:.5f}",
            f"Time: {iso_ts}",
        ]

        # Try to use a monospace font; fall back to default if unavailable
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 32)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 22)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_small = font_large

        # Draw header line larger
        y = 180
        draw.text((400, y), lines[0], fill=(255, 255, 255), font=font_large, anchor="mm")
        y += 60
        for line in lines[1:]:
            draw.text((400, y), line, fill=(200, 200, 200), font=font_small, anchor="mm")
            y += 44

        # Encode as JPEG bytes
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        image_bytes = buf.getvalue()

        # Upload to MinIO
        ts_compact = now.strftime("%Y%m%d_%H%M%S")
        object_key = f"missions/{mission_id}/waypoint_{waypoint_idx:02d}_{ts_compact}.jpg"
        filename = f"waypoint_{waypoint_idx:02d}_{ts_compact}.jpg"

        await upload_file(
            file_data=image_bytes,
            object_key=object_key,
            content_type="image/jpeg",
        )

        # Create DB record
        async with async_session() as db:
            image_record = InspectionImage(
                mission_id=mission_id,
                filename=filename,
                object_key=object_key,
                content_type="image/jpeg",
                captured_at=now,
            )
            db.add(image_record)
            await db.commit()
            await db.refresh(image_record)
            logger.info(
                "Inspection image saved: %s (mission=%s, wp=%d)",
                filename, mission_id, waypoint_idx,
            )
            return image_record

    except Exception as exc:
        logger.error(
            "Failed to generate inspection image for mission %s wp %d: %s",
            mission_id, waypoint_idx, exc,
        )
        return None
