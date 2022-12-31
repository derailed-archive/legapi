from flask import Blueprint, g, jsonify

from ...permissions import DEFAULT_PERMISSIONS, GuildPermissions
from ...powerbase import abort_auth, prepare_membership, prepare_permissions, publish_to_guild
from ...identification import version, medium
from webargs import flaskparser, validate, fields
from ...database import db

router = Blueprint('guild_management', __name__)

@version('/guilds', 1, router, 'POST')
@flaskparser.use_args({
    'name': fields.String(required=True, allow_none=False, validate=validate.Length(1, 30))
})
def create_guild(data: dict) -> None:
    if g.user is None:
        abort_auth()

    guild = {'_id': medium.snowflake(), 'name': data['name'], 'owner_id': g.user['_id'], 'flags': 0, 'permissions': {'allow': DEFAULT_PERMISSIONS}}

    db.guilds.insert_one(guild)
    db.members.insert_one({'user_id': g.user['_id'], 'guild_id': guild['_id'], 'nick': None, 'role_ids': guild['_id']})

    return jsonify(dict(guild)), 201

@version('/guilds/<int:guild_id>', 1, router, 'PATCH')
@flaskparser.use_args({
    'name': fields.String(required=False, allow_none=False, validate=validate.Length(1, 30))
})
def modify_guild(guild_id: int, data: dict) -> None:
    guild, member = prepare_membership(guild_id)

    if data == {}:
        return jsonify(dict(guild))

    prepare_permissions(member, guild, [GuildPermissions.MODIFY_GUILD])

    gid = dict(guild)
    gid['name'] = data['name']

    publish_to_guild(gid['_id'], 'GUILD_UPDATE', gid)

    return jsonify(gid)
