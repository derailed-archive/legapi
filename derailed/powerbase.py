import json
import os
from typing import Any, NoReturn, TypedDict

import flask_limiter.util
import grpc
from flask import abort, g, jsonify, request
from flask_limiter import HEADERS, Limiter

from .grpc.derailed_pb2 import GetGuildInfo, Message, Publ, RepliedGuildInfo, UPubl

from .permissions import GuildPermission, has_bit, merge_permissions, unwrap_guild_permissions

from .authorizer import auth as auth_medium
from .database import Guild, Member, Role, User, db
from .grpc import derailed_pb2_grpc


def authorize_user() -> User | None:
    auth = request.headers.get('Authorization', None)

    if auth is None:
        return None

    return dict(auth_medium.verify(auth))


def get_key_value() -> str:
    user = g.get('user', None)

    if user is None:
        return flask_limiter.util.get_remote_address()
    else:
        return user['_id']


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

        permsl.append(unwrap_guild_permissions(allow=role['permissions']['allows'], deny=role['permissions']['deny'], pos=role['position']))

    perms = merge_permissions(*permsl)

    for perm in required_permissions:
        if not has_bit(perms, perm):
            abort(jsonify({'_errors': ['Invalid Permissions']}), status=403)
