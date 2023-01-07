from datetime import datetime

import pymongo
from flask import Blueprint, g, jsonify, request
from webargs import fields, flaskparser, validate

from ...database import db
from ...identification import medium, version
from ...permissions import GuildPermissions
from ...powerbase import (
    abort_forb,
    plain_resp,
    prepare_channel,
    prepare_membership,
    prepare_permissions,
    publish_to_guild,
)

router = Blueprint('messages', __name__)


@version('/channels/<int:channel_id>/messages', 1, router, 'GET')
def get_messages(channel_id: int) -> None:
    channel = prepare_channel(channel_id)

    if channel.get('guild_id') is not None:
        guild, member = prepare_membership(channel['guild_id'])

        prepare_permissions(member, guild, [GuildPermissions.VIEW_MESSAGE_HISTORY])

    try:
        limit = request.args.get('limit', 50, int)

        if limit > 100:
            return {'_errors': {'limit': ['Limit over 100']}}
    except ValueError:
        return {'_errors': {'limit': ['Invalid Limit field']}}

    messages = list(db.messages.find({'channel_id': channel_id}).sort('_id', pymongo.DESCENDING).limit(limit))

    return jsonify(messages)


@version('/channels/<int:channel_id>/messages/<int:message_id>', 1, router, 'GET')
def get_messages(channel_id: int, message_id: int) -> None:
    channel = prepare_channel(channel_id)

    if channel.get('guild_id') is not None:
        guild, member = prepare_membership(channel['guild_id'])

        prepare_permissions(member, guild, [GuildPermissions.VIEW_MESSAGE_HISTORY])

    message = db.messages.find_one({'_id': message_id, 'channel_id': channel['_id']})

    if message is None:
        return {'_errors': {'message_id': ['Not Found']}}

    return dict(message)


@version('/channels/<int:channel_id>/messages', 1, router, 'POST')
@flaskparser.use_args(
    {'content': fields.String(validate=validate.Length(1, 1024), required=True, allow_none=False)}
)
def create_message(data: dict, channel_id: int) -> None:
    channel = prepare_channel(channel_id)

    if channel.get('guild_id') is not None:
        guild, member = prepare_membership(channel['guild_id'])

        prepare_permissions(member, guild, [GuildPermissions.CREATE_MESSAGES.value])

    message = {
        '_id': medium.snowflake(),
        'author_id': g['user']['_id'],
        'content': data['content'],
        'channel_id': channel['_id'],
        'timestamp': datetime.now(),
        'edited_timestamp': None,
    }
    db.messages.insert_one(message)

    if channel.get('guild_id') is not None:
        publish_to_guild(channel['guild_id'], 'MESSAGE_CREATE', message)

    return message, 201


@version('/channels/<int:channel_id>/messages/<int:message_id>', 1, router, 'PATCH')
@flaskparser.use_args(
    {'content': fields.String(validate=validate.Length(1, 1024), required=True, allow_none=False)}
)
def edit_message(data: dict, channel_id: int, message_id: int) -> None:
    channel = prepare_channel(channel_id)

    message = db.messages.find_one({'_id': str(message_id), 'channel_id': channel_id})

    if message is None:
        return {'_errors': ['Message does not exist']}, 404

    if message['author_id'] != g.user['id']:
        abort_forb()

    message = dict(message)
    message['content'] = data['content']
    db.messages.update_one({'_id': str(message_id)}, message)

    if channel.get('guild_id') is not None:
        publish_to_guild(channel['guild_id'], 'MESSAGE_EDIT', message)

    return message, 201


@version('/channels/<int:channel_id>/messages/<int:message_id>', 1, router, 'DELETE')
def delete_message(channel_id: int, message_id: int) -> None:
    channel = prepare_channel(channel_id)

    message = db.messages.find_one({'_id': str(message_id), 'channel_id': channel_id})

    if message is None:
        return {'_errors': ['Message does not exist']}, 404

    if message['author_id'] == g.user['id']:
        db.messages.delete_one({'_id': message_id})
        return plain_resp()

    if channel.get('guild_id') is not None:
        guild, member = prepare_membership(channel['guild_id'])

        prepare_permissions(member, guild, [GuildPermissions.MODIFY_MESSAGES.value])

    db.messages.delete_one({'_id': str(message_id)})

    if channel.get('guild_id') is not None:
        publish_to_guild(
            channel['guild_id'],
            'MESSAGE_DELETE',
            {'message_id': str(message_id), 'guild_id': channel['guild_id'], 'channel_id': channel['_id']},
        )

    return plain_resp()
