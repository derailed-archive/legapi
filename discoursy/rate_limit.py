import os
from sanic import Sanic, Request, exceptions, response
from sanic_ext import Extension
from limits.aio.strategies import MovingWindowRateLimiter
from limits.aio.storage import RedisStorage, MemoryStorage
from limits import parse
from .exceptions import RateLimited


class RateLimiter(Extension):
    name = 'ratelimiter'

    # type defs
    limiter: MovingWindowRateLimiter
    glbl = parse('50/second')

    def startup(self, bootstrap) -> None:
        if self.included():
            self.app.before_server_start(self._setup)
            self.app.on_request(self)
            self.app.error_handler.add(RateLimited, self._on_rate_limit)

    async def _on_rate_limit(self, request: Request, exc: RateLimited) -> response.BaseHTTPResponse:
        return response.json({'retry_after': exc.retry_after, 'global': exc.global_rate_limit}, status=429, headers=exc.headers)

    async def __call__(self, request: Request) -> None:
        route = request.route

        if route is None:
            return

        limit: str | None = route.ctx.rate_limit if hasattr(route.ctx, 'rate_limit') else None

        auth = request.headers.get('Authorization')

        if auth:
            try:
                user = self.app.ctx.storage.from_auth(auth)
            except ValueError:
                raise exceptions.Unauthorized('Invalid authorization', 401)
        else:
            user = None

        glbl = await self.limiter.hit(self.glbl, request.ip, route.path)

        if glbl is False:
            stats = await self.limiter.get_window_stats(self.glbl, request.ip, route.path)
            raise RateLimited(stats[0], True)

        if user:
            if limit:
                real_limit = parse(limit)
                success = await self.limiter.hit(real_limit, user.id, route.path)

                if success is False:
                    stats = await self.limiter.get_window_stats(real_limit, user.id, route.path)
                    raise RateLimited(stats[0], False)
        else:
            if limit:
                real_limit = parse(limit)
                success = await self.limiter.hit(real_limit, request.ip, route.path)

                if success is False:
                    stats = await self.limiter.get_window_stats(real_limit, request.ip, route.path)
                    raise RateLimited(stats[0], False)


    async def _setup(self, app: Sanic) -> None:
        redis_uri = os.getenv('redis_uri')

        self.limiter = MovingWindowRateLimiter(MemoryStorage() if redis_uri is None else RedisStorage(redis_uri))
