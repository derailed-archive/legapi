from flask import Blueprint, abort, jsonify
from webargs import fields, flaskparser, validate

from ...database import db
from ...identification import medium, version
from ...permissions import GuildPermissions
from ...powerbase import (
    CHANNEL_REGEX,
    plain_resp,
    prepare_category_position,
    prepare_channel_position,
    prepare_guild_channel,
    prepare_membership,
    prepare_permissions,
    publish_to_guild,
)

router = Blueprint('guild_channels', __name__)


@version('/guilds/<int:guild_id>/channels', 1, router, 'POST')
@flaskparser.use_args(
    {
        'type': fields.Integer(strict=True, validate=validate.OneOf([0, 1]), required=True, allow_none=False),
        'name': fields.String(
            required=True,
            allow_none=False,
            validate=(validate.Length(2, 32), validate.Regexp(CHANNEL_REGEX, error='Invalid channel name')),
        ),
        'position': fields.Integer(required=False, strict=True, validate=validate.Range(1, 100)),
        'parent_id': fields.Integer(required=False),
    }
)
def create_channel(data: dict, guild_id: int) -> None:
    guild, member = prepare_membership(guild_id)
    position = data.get('position')
    parent_id = str(data.get('parent_id'))

    prepare_permissions(member, guild, [GuildPermissions.CREATE_CHANNELS.value])

    if parent_id is not None:
        parent = db.channels.find_one({'guild_id': str(guild_id), '_id': str(parent_id)})

        if parent is None:
            abort(jsonify({'_errors': {'parent_id': ['Invalid channel']}}))

        if (parent['type'] != 0) or (data['type'] == 0):
            abort(jsonify({'_errors': {'parent_id': ['Invalid type']}}))

    channel_count = db.channels.count_documents({'guild_id': str(guild_id)})

    if channel_count == 100:
        abort(jsonify({'_errors': 'Channel limit reached'}))

    if data['type'] == 0:
        highest_channel = (
            db.channels.find({'guild_id': str(guild_id), 'type': 0}).sort({'position': -1}).limit(1)
        )
    else:
        highest_channel = db.channels.find({'guild_id': str(guild_id)}).sort({'position': -1}).limit(1)

    for c in highest_channel:
        if ((c['position'] + 1) < data['position']) and position is not None:
            abort(jsonify({'_errors': {'position': ['Invalid position']}}))
        elif position is None:
            position = c['position'] + 1

    if data['type'] == 0:
        prepare_category_position(position, guild)
    else:
        prepare_channel_position(position, parent_id, guild)

    channel = {
        '_id': medium.snowflake(),
        'type': data['type'],
        'parent_id': parent_id,
        'name': data['name'],
        'guild_id': str(guild_id),
        'last_message_id': None,
    }

    db.channels.insert_one(channel)

    publish_to_guild(str(guild_id), 'CHANNEL_CREATE', channel)

    return jsonify(channel), 201


@version('/guilds/<int:guild_id>/channels/<int:channel_id>', 1, router, 'PATCH')
@flaskparser.use_args(
    {
        'name': fields.String(
            required=True,
            allow_none=False,
            validate=(validate.Length(2, 32), validate.Regexp(CHANNEL_REGEX, error='Invalid channel name')),
        ),
        'position': fields.Integer(required=False, strict=True, validate=validate.Range(1, 100)),
        'parent_id': fields.Integer(required=False),
    }
)
def modify_channel(data: dict, guild_id: int, channel_id: int) -> None:
    guild, member = prepare_membership(guild_id)

    prepare_permissions(member, guild, [GuildPermissions.MODIFY_CHANNELS.value])

    channel = prepare_guild_channel(channel_id, guild)

    position = data.get('position')
    parent_id = data.get('parent_id', str)
    channel_copy = channel.copy()

    if data.get('name'):
        channel_copy['name'] = data['name']

    if parent_id != str or position:
        if data['type'] == 0:
            highest_channel = (
                db.channels.find({'guild_id': str(guild_id), 'type': 0}).sort({'position': -1}).limit(1)
            )
        else:
            highest_channel = db.channels.find({'guild_id': str(guild_id)}).sort({'position': -1}).limit(1)

    if parent_id != str:
        parent_id = str(parent_id)

        parent = db.channels.find_one({'guild_id': str(guild_id), '_id': str(parent_id)})

        if parent is None or (parent['type'] != 0) or (data['type'] == 0):
            abort(jsonify({'_errors': {'parent_id': ['Invalid type']}}))

        prepare_channel_position(highest_channel['position'] + 1, parent_id, guild)
        channel_copy['parent_id'] = parent_id

    if position:
        for c in highest_channel:
            if ((c['position'] + 1) < data['position']) and position is not None:
                abort(jsonify({'_errors': {'position': ['Invalid position']}}))
            elif position is None:
                position = c['position'] + 1

        if channel['type'] == 0:
            prepare_category_position(position, guild)
        else:
            prepare_channel_position(position, channel_copy['parent_id'], guild)
        channel_copy['position'] = position

    db.channels.update_one({'_id': channel['_id']}, channel_copy)

    publish_to_guild(guild['_id'], 'CHANNEL_UPDATE', channel_copy)

    return jsonify(channel_copy)


@version('/guilds/<int:guild_id>/channels/<int:channel_id>')
def delete_channel(guild_id: int, channel_id: int) -> None:
    guild, member = prepare_membership(guild_id)

    prepare_permissions(member, guild, [GuildPermissions.MODIFY_CHANNELS.value])

    channel = prepare_guild_channel(channel_id, guild)

    db.channels.delete_one({'_id': channel['_id']})

    publish_to_guild(guild['_id'], 'CHANNEL_DELETE', {'channel_id': channel['_id'], 'guild_id': guild['_id']})

    return plain_resp()
