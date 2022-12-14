from time import time

from msgspec import json
from sanic.exceptions import SanicException


class RateLimited(SanicException):
    def __init__(self, retry_after: str | int, global_ratelimit: bool, ip: bool = False, **headers) -> None:
        self.retry_after = retry_after - time()
        self.global_rate_limit = global_ratelimit
        self.headers = headers
        self.ip = ip
        super().__init__(json.encode({'retry_after': retry_after, 'global': global_ratelimit}), 429)
