import json
import logging
from typing import Any, Awaitable, Callable

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    global _client
    _client = redis.from_url(settings.redis_url, decode_responses=True)
    await _client.ping()
    logger.info("Redis client connected: %s", settings.redis_url)
    return _client


async def close_redis() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def get_redis() -> redis.Redis:
    if _client is None:
        raise RuntimeError("Redis client not initialized")
    return _client


async def publish_event(channel: str, data: dict) -> None:
    """Publish JSON-serializable event to Redis channel."""
    r = get_redis()
    await r.publish(f"ws:{channel}", json.dumps(data))


async def subscribe_and_dispatch(
    channels: list[str],
    handler: Callable[[str, dict], Awaitable[None]],
) -> None:
    """
    Long-running task: subscribe to Redis channels, decode messages,
    and call handler(channel, data) for each.
    Channels are given without 'ws:' prefix; prefix is added internally.
    """
    r = get_redis()
    pubsub = r.pubsub()
    prefixed = [f"ws:{c}" for c in channels]
    await pubsub.subscribe(*prefixed)
    logger.info("Subscribed to Redis channels: %s", prefixed)
    try:
        async for msg in pubsub.listen():
            if msg["type"] != "message":
                continue
            raw_channel = msg["channel"]
            channel = raw_channel.removeprefix("ws:")
            try:
                data = json.loads(msg["data"])
            except json.JSONDecodeError:
                logger.warning("Malformed Redis message on %s", raw_channel)
                continue
            await handler(channel, data)
    finally:
        await pubsub.unsubscribe(*prefixed)
        await pubsub.aclose()
