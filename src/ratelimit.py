# FIXED WINDOW ALGORITHM

import time

import redis.asyncio as redis
import structlog
from fastapi import Depends, Request

from src.auth.dependencies import get_optional_user_uid
from src.db.redis import redis_client
from src.errors import RateLimited

logger = structlog.get_logger()

class RateLimiter:
    def __init__(self, limit: int, window: int, name: str):
        self.limit = limit
        self.window = window
        self.name = name

    async def __call__(self, request: Request, user_uid=Depends(get_optional_user_uid)):
        who = str(user_uid) if user_uid else request.client.host
        bucket = int(time.time() // self.window)
        key = f"rl:{self.name}:{who}:{bucket}"

        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, self.window)
        except redis.RedisError:
            logger.warning("ratelimit.redis_down", limiter=self.name)
            return

        if count > self.limit:
            retry_after = self.window - int(time.time()) % self.window
            raise RateLimited(headers={"Retry-After": str(retry_after)})

login_ratelimit = RateLimiter(limit=5,window=60,name="LOGIN")
register_ratelimit = RateLimiter(limit=3,window=3600,name="REGISTER")
pastes_ratelimit = RateLimiter(limit=10,window=60,name="PASTES")
images_upload_ratelimit = RateLimiter(limit=10,window=3600,name="IMAGES_UPLOAD")
pastes_report_ratelimit = RateLimiter(limit=5,window=3600,name="PASTES_REPORT")