import os
from typing import Any

from arq.connections import RedisSettings
from dotenv import load_dotenv

from discoursy.database import (Channel, Member, Message, Presence, Settings,
                                User)

load_dotenv()


redis_settings = RedisSettings(host=os.environ['redis_host'], port=int(os.environ['redis_port']))


async def delete_user(ctx, user_id: str) -> None:
    await User.find_one(User.id == user_id).delete()
    await Settings.find_one(Settings.user_id == user_id).delete()
    await Presence.find(Presence.user_id == user_id).delete()
    await Member.find(Member.user_id == user_id).delete()


async def chunk_guild(ctx, guild_id: str) -> list[dict[str, Any]]:
    members = []
    async for member in Member.find(Member.guild_id == guild_id):
        members.append(member.dict())
    return members


async def delete_channel_messages(ctx, channel_id: str) -> None:
    channel = await Channel.find_one(Channel.id == channel_id)

    if channel is None:
        return

    await Message.find(Message.channel_id == channel_id).delete()
    await channel.delete()


async def delete_guild_members(ctx, guild_id: str) -> None:
    await Member.find(Member.guild_id == guild_id).delete()


class WorkerSettings:
    functions = [
        delete_user,
        chunk_guild,
        delete_channel_messages,
        delete_guild_members,
    ]
    redis_settings = redis_settings
    allow_abort_jobs = True
