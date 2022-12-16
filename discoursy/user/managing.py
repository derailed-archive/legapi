from random import randint
from typing import Any

from argon2 import PasswordHasher
from sanic import Blueprint, Request, exceptions
from webargs import fields, validate
from webargs_sanic.sanicparser import use_kwargs

from ..database import Settings, User, authorize_user, client

user_managing = Blueprint(__name__)

password_hasher: PasswordHasher = PasswordHasher()


def generate_discriminator() -> str:
    discrim_number = randint(1, 9999)
    return '%04d' % discrim_number


@user_managing.post('/register', ctx_rate_limit='3/hour')
@use_kwargs(
    {
        'user': {
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
        }
    },
    location='json_or_form',
)
async def register_user(request: Request, user: dict[str, Any]) -> None:
    # checks
    if await User.find_one(User.email == user['email']).exists():
        raise exceptions.BadRequest('A user with this email already exists', 400)

    discrim: str | None = None
    for _ in range(9):
        d = generate_discriminator()
        if await User.find_one(User.username == user['username'], discriminator=d).exists():
            continue
        else:
            discrim = d

    if discrim is None:
        raise exceptions.BadRequest('Unable to find valid discriminator for this username', 400)

    user['password'] = password_hasher.hash(user['password'])

    # user creation process
    async with client.start_session() as s:
        await s.start_transaction()
        user_id = request.app.ctx.snowflake.form()
        userd: User = await User(id=user_id, **user)
        userd.insert(session=s)
        await Settings(id=user_id, status='online', guild_order=[]).insert(session=s)
        await s.commit_transaction()

    data = userd.dict()
    data['token'] = request.app.ctx.exchange.form(userd.id, userd.password)
    return data


@user_managing.get('/users/@me', ctx_rate_limit='10/minute')
async def get_myself(request: Request) -> None:
    user = await authorize_user(request)
    return user.dict()
