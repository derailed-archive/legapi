import os
from typing import Any

from aiokafka import AIOKafkaProducer
from msgspec import json


class Dispatcher:
    # the topics this dispatcher allows
    topics = [
        'guild',
        'channel',
        'message',
        'presence',
        'user',
        'member',
    ]

    def __init__(self) -> None:
        self._producer = AIOKafkaProducer(bootstrap_servers=os.environ['KAFKA_SERVERS'].split(','))

    async def dispatch(self, topic: str, name: str, msg: dict[str, Any], key: Any | None = None) -> None:
        if topic not in self.topics:
            raise ValueError(f'topic {topic} is not a valid topic')

        msg['t'] = name.upper()

        data = json.encode(msg)
        await self._producer.send(topic, data, key=key)

    async def start(self) -> None:
        await self._producer.start()
