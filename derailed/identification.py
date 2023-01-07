import os
import secrets
import threading
import time
from random import randint
from typing import Callable

from flask import Blueprint

versions = 1


class IDMedium:
    def __init__(self, epoch: int = 1672531200000) -> None:
        self._incr: int = 0
        self._epoch = epoch

    def snowflake(self) -> str:
        current_ms = int(time.time() * 1000)
        epoch = current_ms - self._epoch << 22

        curthread = threading.current_thread().ident
        if curthread is None:
            raise AssertionError

        epoch |= (curthread % 32) << 17
        epoch |= (os.getpid() % 32) << 12

        epoch |= self._incr % 4096

        if self._incr == 9000000000:
            self._incr = 0

        self._incr += 1

        return str(epoch)

    def invite(self) -> str:
        return secrets.token_urlsafe(randint(4, 9))


medium = IDMedium()


def version(
    path: str, minimum_version: int, bp: Blueprint, method: str, exclude_versions_higher: int = 0, **kwargs
) -> Callable:
    def wrapper(func: Callable) -> Callable:
        for version in range(versions):
            version += 1

            if not version <= minimum_version:
                continue
            elif version > versions:
                break
            elif exclude_versions_higher > version:
                break

            bp.add_url_rule(f'/v{minimum_version}{path}', view_func=func, methods=[method], **kwargs)
        return func

    return wrapper
