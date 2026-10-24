import redis.asyncio as redis
from src.config import Config

redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)