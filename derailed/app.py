import asyncio

from dotenv import load_dotenv

load_dotenv()

from msgspec import json
from sanic import Request, Sanic
from sanic import json as jsone
from sanic_ext import Extend

from .constants import setup_jobber
from .database import start_db
from .dispatcher import Dispatcher
from .rate_limit import RateLimiter
from .storage import Exchange, Snowflake, Storage
from .user.managing import user_managing

app = Sanic('derailed', loads=json.decode, dumps=json.encode)
app.blueprint(user_managing)
app.config.FALLBACK_ERROR_FORMAT = 'json'
app.config.KEEP_ALIVE_TIMEOUT = 15
app.ctx.exchange = Exchange()
app.ctx.dispatcher = Dispatcher()
app.ctx.snowflake = Snowflake(1420070400000)
storage = Storage(app=app)
Extend.register(RateLimiter)


@app.before_server_start
async def setup(app: Sanic) -> None:
    setup_jobber()
    await start_db()
    await app.ctx.dispatcher.start()
    asyncio.create_task(storage.clear_cache())


@app.get('/', ctx_rate_limit='2/second')
async def main(request: Request):
    return jsone({'discourse': True})
