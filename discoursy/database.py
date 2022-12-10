from beanie import Document, init_beanie
from pydantic import Field, BaseModel
from datetime import datetime
from typing import Literal
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def start_db() -> None:
    client = AsyncIOMotorClient(os.environ['mongodb_uri'])
    await init_beanie(
        client,
        document_models=[
            User, Settings, Guild, Member, Invite, Presence, Message, Channel # type: ignore
        ]
    )

class User(Document):
    id: str
    username: str = Field(min_length=1, max_length=30)
    discriminator: str = Field(min_length=4, max_length=4)
    email: str = Field(min_length=5, max_length=15)
    password: str = Field(exclude=True)
    flags: int
    system: bool
    deletor_job_id: str | None
    suspended: bool
    pronouns: str = Field('undefined', max_length=10, min_length=1)

class Settings(Document):
    user_id: str
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
