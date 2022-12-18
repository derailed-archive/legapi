from datetime import datetime
from random import randint
from typing import Any

from argon2 import PasswordHasher
from sanic import Blueprint, Request, exceptions, response
from webargs import fields, validate
from webargs_sanic.sanicparser import use_args

from ..constants import jobber
from ..database import Settings, User, authorize_user, client

user_managing = Blueprint('user-management')

password_hasher: PasswordHasher = PasswordHasher()


def generate_discriminator() -> str:
    discrim_number = randint(1, 9999)
    return '%04d' % discrim_number


@user_managing.post('/register', ctx_rate_limit='3/hour')
@use_args(
    {
        'username': fields.String(
            required=True,
            allow_none=False,
            validate=validate.Length(1, 30, error='Username length is too big'),
        ),
        'email': fields.String(
            required=True,
            allow_none=False,
            validate=(validate.Email(error='Unidentifiable Email Given'), validate.Length(min=5, max=25)),
        ),
        # does sex
        'password': fields.String(
            required=True,
            allow_none=False,
            validate=(
                validate.Length(
                    min=8,
                    max=30,
                    error='Password is either under the length of 8 or over the length of 30',
                )
            ),
        ),
        'pronouns': fields.String(
            required=False,
            allow_none=True,
            default=None,
            validate=validate.OneOf(['he/him', 'she/her', 'undefined', 'they/them', 'it/is']),
        ),
    },
    location='json_or_form',
)
async def register_user(request: Request, user: dict[str, Any]) -> response.HTTPResponse:
    # checks
    if await User.find_one(User.email == user['email']).exists():
        raise exceptions.BadRequest('A user with this email already exists', 400)

    discrim: str | None = None
    for _ in range(9):
        d = generate_discriminator()
        if await User.find_one(User.username == user['username'], User.discriminator == d).exists():
            continue
        discrim = d
        break

    if discrim is None:
        raise exceptions.BadRequest('Unable to find valid discriminator for this username', 400)

    user['password'] = password_hasher.hash(user['password'])

    # user creation process
    async with await client.start_session() as s:
        s.start_transaction()
        user_id = request.app.ctx.snowflake.form()
        userd: User = User(id=user_id, discriminator=discrim, flags=0, system=False, suspended=False, **user)
        await userd.insert(session=s)
        await Settings(id=user_id, status='online', guild_order=[]).insert(session=s)
        await s.commit_transaction()

    data = userd.dict()
    data['token'] = request.app.ctx.exchange.form(userd.id, userd.password)
    return response.json(data)


@user_managing.get('/users/@me', ctx_rate_limit='10/minute')
async def get_myself(request: Request) -> response.HTTPResponse:
    user = await authorize_user(request)
    return response.json(user.dict())


@user_managing.post('/users/@me/delete')
@use_args(
    {
        'password': fields.String(
            required=True,
            allow_none=False,
            validate=(
                validate.Length(
                    min=8,
                    max=30,
                    error='Password is either under the length of 8 or over the length of 30',
                )
            ),
        )
    }
)
async def delete_myself(request: Request, delete_details: dict[str, str]) -> response.HTTPResponse:
    user = await authorize_user(request)

    match = password_hasher.verify(user.password, delete_details['password'])

    if match is False:
        raise exceptions.Unauthorized('Password does not match', 401)

    deletor_id = request.app.ctx.snowflake.form()

    user.deletor_job_id = deletor_id
    await user.update()
    await jobber.enqueue_job('delete_user', user_id=user.id, _job_id=deletor_id, _defer_by=7_776_000)
    return response.json('', 204)
