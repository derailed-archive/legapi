"""
Copyright (C) 2021-2023 Derailed.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ...database import AsyncSession, uses_db
from ...identification import medium, version
from ...models.guild import DefaultPermissions, Guild
from ...models.member import Member
from ...models.user import User
from ...permissions import DEFAULT_PERMISSIONS, GuildPermissions
from ...powerbase import (
    prepare_default_channels,
    prepare_membership,
    prepare_permissions,
    publish_to_guild,
    publish_to_user,
    uses_auth,
)
from ...undefinable import UNDEFINED, Undefined

router = APIRouter()


class CreateGuild(BaseModel):
    name: str = Field(min_length=1, max_length=32)


@version('/guilds', 1, router, 'POST', status_code=201)
async def create_guild(
    request: Request,
    data: CreateGuild,
    session: AsyncSession = Depends(uses_db),
    user: User = Depends(uses_auth),
) -> None:
    permissions = DefaultPermissions(allow=DEFAULT_PERMISSIONS, deny=0)
    guild = Guild(
        id=medium.snowflake(),
        name=data.name,
        owner_id=user.id,
        flags=0,
        permissions=permissions,
    )
    member = Member(user=user, guild=guild, nick=None, roles=[])

    session.add_all([permissions, guild, member])

    prepare_default_channels(guild)

    await session.commit()

    publish_to_user(user_id=user.id, event='GUILD_CREATE', data=guild)

    return dict(guild)


class ModifyGuild(BaseModel):
    name: str | Undefined = Field(UNDEFINED, min_length=1, max_length=30)


@version('/guilds/{guild_id}', 1, router, 'PATCH')
async def modify_guild(
    request: Request, guild_id: int, data: CreateGuild, session: AsyncSession = Depends(uses_db)
) -> None:
    guild, member = await prepare_membership(guild_id)

    if not data.name:
        return dict(guild)

    await prepare_permissions(member, guild, [GuildPermissions.MODIFY_GUILD])

    guild.name = data.name

    session.add(guild)

    await session.commit()

    publish_to_guild(guild.id, 'GUILD_UPDATE', dict(guild))

    return dict(guild)
