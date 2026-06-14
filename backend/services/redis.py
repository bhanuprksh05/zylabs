import redis.asyncio as aioredis
from config.settings import settings

redis_client: aioredis.Redis | None = None


async def init_redis():
    global redis_client
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)


async def close_redis():
    if redis_client:
        await redis_client.close()


def get_redis() -> aioredis.Redis:
    if not redis_client:
        raise RuntimeError("Redis not initialized")
    return redis_client