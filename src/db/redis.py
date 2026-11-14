import redis.asyncio as redis
from src.config import Config

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()

redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)

async def record_view(paste, viewer: str):
    try:
        first_time = await redis_client.set(f"viewed:{paste.uid}:{viewer}", 1, nx=True, ex=60)
        if first_time:
            await redis_client.incr(f"views:{paste.uid}")
    except redis.RedisError:
        logger.warning("views.redis_down", paste_uid=str(paste.uid))
    