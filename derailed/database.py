import os
from datetime import datetime
from typing import Literal, NotRequired, TypedDict

import pymongo

_client = pymongo.MongoClient(os.environ['MONGODB_URI'])
db = _client.get_database('derailed')


class User(TypedDict):
    _id: str
    username: str
    discriminator: str
    email: str
    password: str
    flags: int
    system: bool
    deletor_job_id: NotRequired[str]
    suspended: bool


class Settings(TypedDict):
    _id: str
    status: str
    guild_order: list[str]


class Guild(TypedDict):
    _id: str
    name: str
    flags: int
    owner_id: str


class Member(TypedDict):
    _id: str
    user_id: str
    guild_id: str
    nick: str | None


class Invite(TypedDict):
    _id: str
    guild_id: str
    author_id: str


class BaseActivity(TypedDict):
    name: str
    type: int
    created_at: datetime


class StatusableActivity(BaseActivity):
    content: str


class GameActivity(BaseActivity):
    game_id: str


class Stream(TypedDict):
    platform: int
    platform_user: str
    stream_id: str | None


class StreamActivity(BaseActivity):
    stream: Stream


class CustomActivity(StatusableActivity):
    emoji_id: str


class Presence(TypedDict):
    user_id: str
    guild_id: str
    device: Literal['mobile', 'desktop']
    activities: list[StatusableActivity | GameActivity | StreamActivity | CustomActivity]
    status: Literal['online', 'invisible', 'dnd']


class Message(TypedDict):
    _id: str
    author_id: str
    content: str
    channel_id: str
    timestamp: datetime
    edited_timestamp: datetime


class Channel(TypedDict):
    _id: str
    type: int
    name: NotRequired[str | None]
    last_message_id: NotRequired[str]
    parent_id: NotRequired[str]
    guild_id: NotRequired[str]
    message_deletor_job_id: NotRequired[str]
    members: NotRequired[list[User]]
