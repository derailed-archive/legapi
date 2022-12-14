import os
from datetime import datetime
from time import time
from typing import TYPE_CHECKING

import coredis
from limits import RateLimitItem, parse
from limits.aio.storage import MemoryStorage, RedisStorage
from limits.aio.strategies import FixedWindowElasticExpiryRateLimiter
from sanic import Request, Sanic, exceptions, response
from sanic_ext import Extension
from sanic_routing import Route

from .exceptions import RateLimited


class RateLimiter(Extension):
    name = 'ratelimiter'

    # type defs
    limiter: FixedWindowElasticExpiryRateLimiter
    glbl = parse('50/second')
    limits: dict[Route, RateLimitItem]

    def startup(self, bootstrap) -> None:
        if self.included():
            self.app.before_server_start(self._setup)
            self.app.on_request(self.call)
            self.app.on_response(self.response)

    def _on_rate_limit(self, exc: RateLimited) -> response.BaseHTTPResponse:
        if exc.ip:
            return {
                'code': 420,
                'message': 'This IP has been tempoarily banned for excessively abusing rate limits',
            }
        return {'retry_after': exc.retry_after, 'global': exc.global_rate_limit}

    async def _increase_ip_tendency(self, request: Request) -> tuple[bool, int | float]:
        if self._redis:
            if not await self._redis.exists(request.ip):
                await self._redis.set(request.ip, 0, ex=3600)
            await self._redis.incr(request.ip)

            value = await self._redis.get(request.ip)
            if int(value) == 60:
                exp = await self._redis.ttl(request.ip)
                return False, exp
            else:
                return True, 0
        else:
            if self._storage.get(request.ip) is None:
                self._storage[request.ip] = 0
                self._storage[request.ip + 'exp'] = datetime.utcnow()
            self._storage[request.ip] += 1

            value = self._storage[request.ip]
            diff = datetime.utcnow() - self._storage[request.ip + 'exp']

            if TYPE_CHECKING:
                diff = datetime() - datetime()

            if diff.seconds == 3600:
                self._storage[request.ip] = 0
                self._storage[request.ip + 'exp'] = datetime.utcnow()

            if int(value) == 60:
                return False, diff.total_seconds()

            return True, 0

    async def _get_ip_tendency(self, request: Request) -> tuple[bool, int | float]:
        if self._redis:
            value = await self._redis.get(request.ip)
            if int(value) == 60:
                exp = await self._redis.ttl(request.ip)
                return False, exp
            else:
                return True, 0
        else:
            value = self._storage[request.ip]
            diff = datetime.utcnow() - self._storage[request.ip + 'exp']

            if TYPE_CHECKING:
                diff = datetime() - datetime()

            if int(value) == 60:
                return False, diff.total_seconds()

            return True, 0

    async def call(self, request: Request) -> None:
        try:
            await self._call(request)
        except RateLimited as exc:
            return response.json(self._on_rate_limit(exc), 429)

    async def _call(self, request: Request) -> None:
        route = request.route

        if route is None:
            return

        limit = self.limits.get(route.name)

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
            tendant = await self._increase_ip_tendency(request=request)
            raise RateLimited(stats[0], True, tendant[0])

        if user:
            if limit:
                success = await self.limiter.hit(limit, user.id, route.path)

                if success is False:
                    stats = await self.limiter.get_window_stats(limit, user.id, route.path)
                    raise RateLimited(stats[0], False)

        else:
            if limit:
                success = await self.limiter.hit(limit, request.ip, route.path)

                if success is False:
                    stats = await self.limiter.get_window_stats(limit, request.ip, route.path)
                    raise RateLimited(stats[0], False)

    async def response(self, request: Request, response: response.BaseHTTPResponse) -> None:
        route = request.route

        if route is None:
            return

        limit = self.limits.get(route.name)

        auth = request.headers.get('Authorization')

        if auth:
            try:
                user = self.app.ctx.storage.from_auth(auth)
            except ValueError:
                raise exceptions.Unauthorized('Invalid authorization', 401)
        else:
            user = None

        if user is None and limit is None:
            stats = await self.limiter.get_window_stats(self.glbl, request.ip, route.path)

        if user:
            if limit:
                stats = await self.limiter.get_window_stats(limit, user.id, route.path)
        else:
            if limit:
                stats = await self.limiter.get_window_stats(limit, request.ip, route.path)

        response.headers.add('X-RateLimit-Reset', stats[0])
        response.headers.add('X-RateLimit-Reset-After', stats[0] - time())
        response.headers.add('X-RateLimit-Remaining', stats[1])

        if limit:
            response.headers.add('X-RateLimit-Limit', limit.amount)

        ip_tendent = await self._get_ip_tendency(request=request)

        if ip_tendent[0] is False:
            response.headers.pop('X-RateLimit-Reset')
            response.headers.add('X-RateLimit-Reset', ip_tendent[1])
            response.headers.pop('X-RateLimit-Reset-After')

    async def _setup(self, app: Sanic) -> None:
        self.limits = {}
        redis_uri = os.getenv('REDIS_URI')

        self.limiter = FixedWindowElasticExpiryRateLimiter(MemoryStorage())
        self.limiter.storage = RedisStorage(redis_uri) if redis_uri is not None else MemoryStorage()

        for _, route in app.router.routes_all.items():
            if hasattr(route.ctx, 'rate_limit'):
                self.limits[route.name] = parse(route.ctx.rate_limit)
            else:
                self.limits[route.name] = None

        if redis_uri:
            self._redis = coredis.Redis(redis_uri)
        else:
            self._redis = None
            self._storage = {}
