from arq import create_pool

from .jobs import redis_settings


async def setup_jobber() -> None:
    global jobber
    jobber = await create_pool(redis_settings, retry=3)
