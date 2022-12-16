import os
from datetime import datetime
from typing import Literal
from sanic import Request, exceptions

from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
import binascii

client = AsyncIOMotorClient(os.environ['MONGO_URI'])


async def start_db() -> None:
    await init_beanie(
        database=client.db_name,
        document_models=[User, Settings, Guild, Member, Invite, Presence, Message, Channel],  # type: ignore
    )
    


class User(Document):
    id: str
    username: str = Field(min_length=1, max_length=30)
    discriminator: str = Field(min_length=4, max_length=4)
    email: str = Field(min_length=5, max_length=15)
    password: str = Field(exclude=True)
    flags: int
    system: bool
    deletor_job_id: str | None = Field(exclude=True)
    suspended: bool
    pronouns: str = Field('undefined', max_length=10, min_length=1)


async def authorize_user(request: Request) -> User:
    authorization = request.headers.get('Authorization')

    if authorization is None or not isinstance(authorization, str):
        raise exceptions.InvalidHeader('Authorization is missing or an invalid type', 400)

    try:
        user_id = request.app.ctx.exchange.get_value(authorization)
    except binascii.Error:
        raise exceptions.InvalidHeader('Authorization is invalid', 401)

    user = await User.find_one(User.id == user_id)

    if user is None:
        raise exceptions.InvalidHeader('Authorization is invalid', 401)

    ok_signature = request.app.ctx.exchange.verify_signature(authorization, user.password)

    if not ok_signature:
        raise exceptions.InvalidHeader('Authorization is invalid', 401)

    return user


class Settings(Document):
    status: Literal['online', 'offline', 'dnd']
    guild_order: list[int]


class Guild(Document):
    id: str
    name: str
    description: str | None = Field(min_length=1, max_length=1000)
    flags: int
    color: int
    owner_id: str
    joinable: bool
    unjoinable_reason: str | None


class Member(Document):
    user_id: str
    guild_id: str
    nick: str


class Invite(Document):
    code: str
    guild_id: str
    author_id: str


class Activity(BaseModel):
    name: str
    type: int
    created_at: datetime


class StatusableActivity(Activity):
    content: str


class GameActivity(StatusableActivity):
    game_id: str


class Stream(BaseModel):
    platform: Literal['youtube', 'twitch']
    platform_user: str
    stream_id: str | None


class StreamActivity(StatusableActivity):
    stream: Stream


class CustomActivity(StatusableActivity):
    emoji_id: str


class Presence(Document):
    user_id: str
    guild_id: str
    device: Literal['mobile', 'desktop']
    activities: list[StatusableActivity | GameActivity | StreamActivity | CustomActivity]
    status: Literal['online', 'offline', 'dnd']


class Message(Document):
    id: str
    author_id: str
    content: str
    channel_id: str
    timestamp: datetime
    edited_timestamp: datetime | None = Field(None)


# Types
# User-to-User: 0
# Group: 1
# Support: 2
# Text: 3
# Category: 4
class Channel(Document):
    id: str
    name: str | None
    last_message_id: str
    parent_id: str | None
    guild_id: str | None
    type: int
    delete_messages_job_id: str | None = Field()
    shun: bool = Field(False)
    members: list[User]
