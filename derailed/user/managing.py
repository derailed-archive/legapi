import string
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


@user_managing.patch('/users/@me', ctx_rate_limit='3/second')
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
        'password': fields.String(
            required=False,
            allow_none=False,
            validate=(
                validate.Length(
                    min=8,
                    max=30,
                    error='Password is either under the length of 8 or over the length of 30',
                )
            ),
        ),
        # does more sex
        'old_password': fields.String(
            required=False,
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
            validate=validate.OneOf(['he/him', 'she/her', 'undefined', 'they/them', 'it/is']),
        ),
    },
    location='json_or_form',
)
async def modify_myself(request: Request, modifications: dict[str, Any]) -> response.HTTPResponse:
    if modifications.get('password') and not modifications.get('old_password'):
        raise exceptions.BadRequest('old_password field is not included with password change', 400)

    user = await authorize_user(request)

    if modifications.get('pronouns', str) != str:
        user.pronouns = modifications['pronouns']

    if modifications.get('username'):
        user.username = modifications['username']
        if await User.find_one(
            User.username == modifications['username'], User.discriminator == user.discriminator
        ).exists():
            for i in range(9):
                d = generate_discriminator()
                if await User.find_one(User.username == user['username'], User.discriminator == d).exists():
                    if i == 8:
                        raise exceptions.BadRequest('Unable to find discriminator for this username', 400)
                user.discriminator = d
                break
        else:
            user.username = modifications['username']

    if modifications.get('email'):
        if await User.find_one(User.email == modifications['email']).exists():
            raise exceptions.BadRequest('Email is already used', 400)
        user.email = modifications['email']

    if modifications.get('password'):
        if password_hasher.verify(user.password, modifications['old_password']) is False:
            raise exceptions.Unauthorized('Old Password is invalid', 401)

        user.password = modifications['password']

    await user.save()

    data = user.dict()

    await request.app.ctx.dispatcher.dispatch('user', 'user_update', data, user.id)

    return response.json(data)


@user_managing.patch('/users/@me/settings')
@use_args(
    {
        'status': fields.String(validate=validate.OneOf(['dnd', 'invisible', 'online'])),
        'guild_order': fields.List(
            fields.String(allow_none=False, validate=validate.ContainsNoneOf(string.ascii_letters))
        ),
    }
)
async def edit_settings(request: Request, setting_changes: dict[str, Any]) -> response.HTTPResponse:
    user = await authorize_user(request=request)
    settings = await Settings.find_one(Settings.id == user.id)

    if setting_changes.get('status'):
        settings.status = setting_changes['status']

    if setting_changes.get('guild_order'):
        guild_order = setting_changes['guild_order']

        same = all(i in guild_order for i in settings.guild_order)

        if same is False:
            raise exceptions.BadRequest(
                "guild_order doesn't contain the same items in the original guild_order"
            )

        settings.guild_order = guild_order

    await settings.save()
    data = settings.dict()

    await request.app.ctx.dispatcher.dispatch('user', 'settings_update', data, settings.id)

    return response.json(data)


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
    await user.save()
    await jobber.enqueue_job('delete_user', user_id=user.id, _job_id=deletor_id, _defer_by=7_776_000)

    await request.app.ctx.dispatcher.dispatch(
        'user', '_enqueued_deletion', {'id': user.id, 'type': 0, 'job_id': deletor_id}, user.id
    )

    return response.json('', 204)
