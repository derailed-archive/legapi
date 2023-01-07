from flask import Blueprint, g, jsonify
from webargs import fields, flaskparser, validate

from ...database import db
from ...identification import medium, version
from ...permissions import DEFAULT_PERMISSIONS, GuildPermissions
from ...powerbase import (
    abort_auth,
    prepare_default_channels,
    prepare_membership,
    prepare_permissions,
    publish_to_guild,
    publish_to_user,
)

router = Blueprint('guild_management', __name__)


@version('/guilds', 1, router, 'POST')
@flaskparser.use_args(
    {'name': fields.String(required=True, allow_none=False, validate=validate.Length(1, 30))}
)
def create_guild(data: dict) -> None:
    if g.user is None:
        abort_auth()

    guild = {
        '_id': medium.snowflake(),
        'name': data['name'],
        'owner_id': g.user['_id'],
        'flags': 0,
        'permissions': {'allow': str(DEFAULT_PERMISSIONS)},
    }

    db.guilds.insert_one(guild)
    db.members.insert_one({'user_id': g.user['_id'], 'guild_id': guild['_id'], 'nick': None, 'role_ids': []})
    db.settings.update_one({'_id': g.user['_id']}, {'$push': {'guild_order': guild['_id']}})

    prepare_default_channels(guild)

    publish_to_user(user_id=g.user['_id'], event='GUILD_CREATE', data=guild)

    return dict(guild), 201


@version('/guilds/<int:guild_id>', 1, router, 'PATCH')
@flaskparser.use_args(
    {'name': fields.String(required=False, allow_none=False, validate=validate.Length(1, 30))}
)
def modify_guild(data: dict, guild_id: int) -> None:
    guild, member = prepare_membership(guild_id)

    if data == {}:
        return dict(guild)

    prepare_permissions(member, guild, [GuildPermissions.MODIFY_GUILD])

    gid = dict(guild)
    gid['name'] = data['name']

    publish_to_guild(gid['_id'], 'GUILD_UPDATE', gid)

    return gid
