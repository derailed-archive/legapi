from flask import Blueprint, jsonify
from ...powerbase import get_guild_info, prepare_guild, prepare_membership
from ...identification import version

router = Blueprint('guild_information', __name__)

@version('/guilds/<int:guild_id>/preview', 1, router, 'GET')
def get_guild_preview(guild_id: int) -> None:
    guild = prepare_guild(guild_id)

    guild_info = get_guild_info(str(guild_id))

    gid = dict(guild)
    gid['approximate_presence_count'] = guild_info.presences
    gid['available'] = guild_info.available

    return jsonify(gid)

@version('/guilds/<int:guild_id>', 1, router, 'GET')
def get_guild(guild_id: int) -> None:
    guild, _ = prepare_membership(guild_id)

    return jsonify(guild)
