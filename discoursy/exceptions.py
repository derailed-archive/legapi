class RateLimited(Exception):
    def __init__(self, retry_after: str | int, global_ratelimit: bool, **headers) -> None:
        self.retry_after = retry_after
        self.global_rate_limit = global_ratelimit
        self.headers = headers
