import asyncio
from sanic import Sanic, Request, json as jsone
from .storage import Exchange, Storage, Snowflake
from .rate_limit import RateLimiter
from sanic_ext import Extend
from msgspec import json

app = Sanic('discoursy', loads=json.decode, dumps=json.encode)
app.config.FALLBACK_ERROR_FORMAT = 'json'
app.config.KEEP_ALIVE_TIMEOUT = 15
app.ctx.exchange = Exchange()
app.ctx.snowflake = Snowflake()
storage = Storage(app=app)
Extend.register(RateLimiter)


@app.before_server_start
async def setup(app: Sanic) -> None:
    asyncio.create_task(storage.clear_cache())


@app.get('/', ctx_rate_limit='2/second')
async def main(request: Request):
    return jsone({'discourse': True})
