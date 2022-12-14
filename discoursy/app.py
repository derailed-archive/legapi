import asyncio

from msgspec import json
from sanic import Request, Sanic
from sanic import json as jsone
from sanic_ext import Extend
from dotenv import load_dotenv

from .rate_limit import RateLimiter
from .storage import Exchange, Snowflake, Storage
from .database import start_db

load_dotenv()
app = Sanic('discoursy', loads=json.decode, dumps=json.encode)
app.config.FALLBACK_ERROR_FORMAT = 'json'
app.config.KEEP_ALIVE_TIMEOUT = 15
app.ctx.exchange = Exchange()
app.ctx.snowflake = Snowflake()
storage = Storage(app=app)
Extend.register(RateLimiter)


@app.before_server_start
async def setup(app: Sanic) -> None:
    await start_db()
    asyncio.create_task(storage.clear_cache())


@app.get('/', ctx_rate_limit='2/second')
async def main(request: Request):
    return jsone({'discourse': True})
