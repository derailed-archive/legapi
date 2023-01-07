import json
import os
import re
from typing import Any, NoReturn

import flask_limiter.util
import grpc
from flask import Response, abort, g, jsonify, request
from flask_limiter import HEADERS, Limiter, RequestLimit

from .authorizer import auth as auth_medium
from .database import Channel, Guild, Member, Role, User, db
from .grpc import derailed_pb2_grpc
from .grpc.derailed_pb2 import GetGuildInfo, Message, Publ, RepliedGuildInfo, UPubl
from .identification import medium
from .permissions import (
    GuildPermission,
    has_bit,
    merge_permissions,
    unwrap_guild_permissions,
)


def authorize_user() -> User | None:
    auth = request.headers.get('Authorization', None)

    if auth is None or auth == '':
        return None

    v = auth_medium.verify(auth)

    if v is None:
        return None

    return dict(v)


def get_key_value() -> str:
    user = g.get('user', None)

    if user is None:
        return flask_limiter.util.get_remote_address()
    else:
        return user['_id']


def respond_rate_limited(limit: RequestLimit) -> Response:
    return {'retry_at': limit.reset_at}


limiter = Limiter(
    key_func=get_key_value,
    default_limits=['50/second'],
    headers_enabled=True,
    header_name_mapping={HEADERS.RETRY_AFTER: 'X-RateLimit-Retry-After'},
    storage_uri=os.getenv('STORAGE_URI', 'memory://'),
    strategy='moving-window',
    # I'd rather 500 than unsync'd rate limits
    in_memory_fallback_enabled=False,
    key_prefix='security.derailed.',
)


def prepare_user(user: User, own: bool = False) -> dict[str, Any]:
    if not own:
        user.pop('email')

    user.pop('password')
    return user


def abort_auth() -> NoReturn:
    abort(jsonify({'_errors': {'headers': {'authorization': ['invalid or missing']}}}), status=401)


user_channel = grpc.insecure_channel(os.getenv('USER_CHANNEL'))
user_stub = derailed_pb2_grpc.UserStub(user_channel)
guild_channel = grpc.insecure_channel(os.getenv('GUILD_CHANNEL'))
guild_stub = derailed_pb2_grpc.GuildStub(guild_channel)


def publish_to_user(user_id: str, event: str, data: dict[str, Any]) -> None:
    user_stub.publish.future(UPubl(user_id=user_id, message=Message(event=event, data=json.dumps(data))))


def publish_to_guild(guild_id: str, event: str, data: dict[str, Any]) -> None:
    guild_stub.publish.future(Publ(guild_id=guild_id, message=Message(event=event, data=json.dumps(data))))


def get_guild_info(guild_id: str) -> RepliedGuildInfo:
    return guild_stub.get_guild_info(GetGuildInfo(guild_id=guild_id))


def prepare_guild(guild_id: int) -> Guild:
    guild_id = str(guild_id)

    guild = db.guilds.find_one({'_id': guild_id})

    if guild is None:
        abort(jsonify({'_errors': 'Guild does not exist'}), status=404)

    return guild


def prepare_membership(guild_id: int) -> tuple[Guild, Member]:
    if g.user is None:
        abort_auth()

    guild = prepare_guild(guild_id)

    member = db.members.find_one({'user_id': g.user['_id']})

    if member is None:
        abort(jsonify({'_errors': 'User is not a member of Guild'}), status=403)

    member = dict(member)
    member.pop('_id')

    member['user'] = db.users.find_one({'_id': member['user_id']})

    return (dict(guild), member)


def prepare_permissions(member: Member, guild: Guild, required_permissions: list[int]) -> None:
    if guild['owner_id'] == member['user_id']:
        return

    roles = member['role_ids']
    permsl: list[GuildPermission] = []

    for role_id in roles:
        role: Role = db.roles.find_one({'_id': role_id})

        permsl.append(
            unwrap_guild_permissions(
                allow=role['permissions']['allows'], deny=role['permissions']['deny'], pos=role['position']
            )
        )

    perms = merge_permissions(*permsl)

    for perm in required_permissions:
        if not has_bit(perms, perm):
            abort(jsonify({'_errors': ['Invalid Permissions']}), status=403)


CHANNEL_REGEX = re.compile(r'^[a-z0-9](?:[a-z0-9-_]{0,30}[a-z0-9])?$')


def prepare_channel_position(wanted_position: int, parent_id: int, guild: Guild) -> None:
    guild_id = guild['_id']

    c = db.channels.find_one({'guild_id': guild_id, 'position': wanted_position})

    if c is None:
        return

    guild_channels = db.channels.find({'guild_id': guild_id, 'parent_id': parent_id})

    for channel in guild_channels:
        if channel['position'] >= wanted_position:
            channel['position'] += 1

        db.channels.update_one({'_id': channel['_id'], 'parent_id': parent_id}, channel)


def prepare_category_position(wanted_position: int, guild: Guild) -> None:
    guild_id = guild['_id']

    c = db.channels.find_one({'guild_id': guild_id, 'position': wanted_position})

    if c is None:
        return

    guild_channels = db.channels.find({'guild_id': guild_id})

    for channel in guild_channels:
        if channel['type'] != 0:
            continue

        if channel['position'] >= wanted_position:
            channel['position'] += 1

        db.channels.update_one({'_id': channel['_id']}, channel)


def prepare_guild_channel(channel_id: int, guild: Guild) -> Channel:
    channel_id = str(channel_id)

    channel = db.channels.find_one({'_id': channel_id, 'guild_id': guild['_id']})

    if channel is None:
        abort(jsonify({'_errors': ['Channel not found']}), status=404)

    return channel


def plain_resp() -> Response:
    return Response('', 204)


def prepare_default_channels(guild: Guild) -> None:
    cat = {
        '_id': medium.snowflake(),
        'name': 'general',
        'parent_id': None,
        'type': 0,
        'last_message_id': None,
        'guild_id': guild['_id'],
        'position': 1,
    }
    general = {
        '_id': medium.snowflake(),
        'name': 'general',
        'parent_id': cat['_id'],
        'type': 1,
        'last_message_id': None,
        'guild_id': guild['_id'],
        'position': 1,
    }

    db.channels.insert_one(cat)
    db.channels.insert_one(general)
