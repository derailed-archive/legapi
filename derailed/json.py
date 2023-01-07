from typing import Any

import msgspec
from flask import Response


class Decoder:
    def __init__(self, **kwargs):
        # eventually take into consideration when deserializing
        self.options = kwargs

    def decode(self, obj):
        return msgspec.json.decode(obj, type=dict)


class Encoder:
    def __init__(self, **kwargs):
        # eventually take into consideration when serializing
        self.options = kwargs

    def encode(self, obj):
        # decode back to str, as orjson returns bytes
        return msgspec.json.encode(obj).decode('utf-8')


def proper(data: dict[str, Any], status: int = 200) -> Response:
    return Response(msgspec.json.encode(data), status, content_type='application/json')
