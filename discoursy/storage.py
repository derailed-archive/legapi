import asyncio
import base64
import os
import secrets
import threading
import time
from random import randint
from typing import Any

import itsdangerous
from sanic import Sanic

from .database import User


class Snowflake:
    def __init__(self, epoch: int = 1672534800000) -> None:
        self.incr: int = 0
        self.epoch = epoch

    def form(self) -> str:
        current_ms = int(time.time() * 1000)
        epoch = current_ms - self.epoch << 22

        curthread = threading.current_thread().ident
        if curthread is None:
            raise AssertionError

        epoch |= (curthread % 32) << 17
        epoch |= (os.getpid() % 32) << 12

        epoch |= self.incr % 4096

        if self.incr == 9000000000:
            self.incr = 0

        self.incr += 1

        return str(epoch)

    def invite(self) -> str:
        return secrets.token_urlsafe(randint(4, 9))


class Exchange:
    def form(self, identifier: str, password: str) -> str:
        signer = itsdangerous.TimestampSigner(password)
        encoded_id = base64.b64encode(identifier.encode())

        return signer.sign(encoded_id).decode()

    def get_value(self, token: str) -> str:
        fragmented = token.split('.')
        encoded_id = fragmented[0]

        return base64.b64decode(encoded_id.encode()).decode()

    def verify_signature(self, token: str, password: str) -> bool:
        signer = itsdangerous.TimestampSigner(password)

        try:
            signer.unsign(token)
            return True
        except itsdangerous.BadSignature:
            return False


class Storage:
    def __init__(self, app: Sanic) -> None:
        self._cache: dict[str, Any] = {}
        self.app: Sanic = app
        self.app.ctx.storage = self

    async def clear_cache(self) -> None:
        await asyncio.sleep(30)

        self._cache.clear()

        asyncio.create_task(self.clear_cache())

    async def from_auth(self, token: str) -> User:
        user_id: str = self.app.ctx.exchange.get_value(token)

        user = await self.get_user(user_id=user_id)

        if user is None:
            raise ValueError('There is no user with this id')

        true_auth = self.app.ctx.exchange.verify_signature(token, user.password)

        if true_auth is False:
            raise ValueError('Signature on token is invalid')
        else:
            return user

    async def get_user(self, user_id: str) -> User | None:
        cached = self._cache.get(user_id)

        if cached is None:
            return await User.find_one(User.id == user_id)
        else:
            return cached
