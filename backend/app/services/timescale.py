import logging

from sqlalchemy import text

from app.database import engine

logger = logging.getLogger(__name__)


async def ensure_hypertable() -> None:
    """Convert telemetry_data to a TimescaleDB hypertable partitioned on 'timestamp'.

    The call is idempotent: if_not_exists => TRUE means it is safe to run on
    every startup whether or not the table has already been converted.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "SELECT create_hypertable("
                "'telemetry_data', 'timestamp', if_not_exists => TRUE"
                ")"
            )
        )
    logger.info("TimescaleDB hypertable ensured for telemetry_data")
