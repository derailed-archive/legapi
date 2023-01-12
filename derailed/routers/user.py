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
from random import randint

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, exceptions
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import uses_db
from ..identification import medium, version
from ..models import Settings, User
from ..powerbase import (
    abort_auth,
    create_token,
    prepare_user,
    publish_to_user,
    uses_auth,
)
from ..undefinable import UNDEFINED, Undefined

router = APIRouter()


def generate_discriminator() -> str:
    discrim_number = randint(1, 9999)
    return '%04d' % discrim_number


class Register(BaseModel):
    username: str = Field(min_length=1, max_length=30)
    email: str = EmailStr
    password: str = Field(min_length=8, max_length=82)


@version('/register', 1, router, 'POST')
async def register_user(data: Register, session: AsyncSession = Depends(uses_db)) -> User:
    discrim: str | None = None
    for _ in range(9):
        d = generate_discriminator()
        if await User.exists(session, data['username'], discrim):
            continue
        discrim = d
        break

    if discrim is None:
        raise exceptions.HTTPException(400, 'No discriminator found')

    user_id = medium.snowflake()
    password = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt(14)).decode()

    usr = {
        'id': user_id,
        'username': data['username'],
        'discriminator': discrim,
        'email': data['email'],
        'password': password,
        'flags': 0,
        'system': False,
        'suspended': False,
    }

    user = User(
        id=user_id,
        username=data['username'],
        discriminator=discrim,
        email=data['email'],
        password=password,
        flags=0,
        system=False,
        suspended=False,
    )
    settings = Settings(user_id=user_id, status='online')

    await session.add_all([user, settings])

    await session.commit()

    usr['token'] = await create_token(str(user_id), password)

    return usr, 201


class PatchMe(BaseModel):
    username: str | Undefined = Field(UNDEFINED, min_length=1, max_length=30)
    email: str | Undefined = Field(UNDEFINED)
    password: str | Undefined = Field(UNDEFINED, min_length=8, max_length=82)
    old_password: str | Undefined = Field(UNDEFINED, min_length=8, max_length=82)


@version('/users/@me', 1, router, 'PATCH')
async def patch_me(
    request: Request, data: PatchMe, user: User = Depends(uses_auth), session: AsyncSession = Depends(uses_db)
) -> None:
    if data == {}:
        return prepare_user(user, True)

    password = data.get('password')
    old_password = data.get('old_password')

    if password and not old_password:
        raise HTTPException(400, 'Missing old password')

    is_pw = bcrypt.checkpw(old_password.encode(), user.password.encode())

    if not is_pw:
        raise HTTPException(401, 'Invalid password')

    muser = {}
    muser['password'] = password

    if data.get('email'):
        muser['email'] = data['email']

    if data.get('username'):
        other_user = await User.exists(session, data['username'], user['discriminator'])

        if other_user is False:
            muser['username'] = data['username']
        else:
            discrim: str | None = None
            for _ in range(9):
                d = generate_discriminator()
                if await User.exists(session, data['username'], discrim):
                    continue
                discrim = d
                break

            if discrim is None:
                raise HTTPException(400, 'Discriminator unavailable')

            muser['username'] = data['username']
            muser['discriminator'] = discrim

    await user.modify(session, **muser)

    usr = prepare_user(user, True)
    publish_to_user(user.id, 'USER_UPDATE', usr)

    return usr


@version('/users/@me', 1, router, 'GET')
async def get_me(request: Request, user: User = Depends(uses_auth)) -> None:
    return prepare_user(user, True)


class Login(BaseModel):
    email: str
    password: str


@version('/login', 1, router, 'POST')
async def login(request: Request, data: Login, session: AsyncSession = Depends(uses_db)) -> None:
    user = await User.get_email(session, data.email)

    if user is None:
        abort_auth()

    true_pw = bcrypt.checkpw(data.email.encode(), user.password.encode())

    if not true_pw:
        abort_auth()

    usr = dict(user)
    usr['token'] = await create_token(user.id, user.password)

    return prepare_user(usr, True)
