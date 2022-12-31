from random import randint

import argon2
from argon2 import PasswordHasher
from flask import Blueprint, abort, g, jsonify
from webargs import fields, flaskparser, validate

from ..authorizer import auth
from ..database import User, _client, db
from ..identification import medium, version
from ..powerbase import abort_auth, limiter, prepare_user, publish_to_user

router = Blueprint('user', __name__, url_prefix='/v1')
pswd_hasher = PasswordHasher()


def generate_discriminator() -> str:
    discrim_number = randint(1, 9999)
    return '%04d' % discrim_number


@version('/register', 1, router, 'POST')
@flaskparser.use_args(
    {
        'username': fields.String(required=True, allow_none=False, validate=validate.Length(1, 30)),
        'email': fields.String(
            required=True,
            allow_none=False,
            validate=(validate.Email(), validate.Length(min=5, max=25)),
        ),
        'password': fields.String(
            required=True,
            allow_none=False,
            validate=validate.Length(
                min=8,
                max=30,
            ),
        ),
    }
)
@limiter.limit('3/hour')
def register_user(data: dict) -> User:
    q = len(list(db.users.find({'username': data['username'], 'discriminator': data['discriminator']})))
    if q >= 1:
        abort(jsonify({'_errors': {'username': ['Username already taken']}}, 400))

    discrim: str | None = None
    for _ in range(9):
        d = generate_discriminator()
        q = len(list(db.users.find({'username': data['username'], 'discriminator': data['discriminator']})))
        if q >= 1:
            continue
        discrim = d
        break

    if discrim is None:
        abort(jsonify({'_errors': {'username': ['Discriminator not available']}}, 400))

    user_id = medium.snowflake()
    password = pswd_hasher.hash(data['password'])

    with _client.start_session() as s:
        s.start_transaction()
        user = db.users.insert_one(
            {
                '_id': user_id,
                'username': data['username'],
                'discriminator': discrim,
                'email': data['email'],
                'password': password,
            },
            session=s,
        )
        db.settings.insert_one({'_id': user_id, 'status': 'online', 'guild_order': []}, session=s)
        s.commit_transaction()

    usr = dict(user)
    usr['token'] = auth.form(user_id, password)

    return jsonify(usr, status=201)


@version('/users/@me', 1, router, 'PATCH')
@flaskparser.use_args(
    {
        'username': fields.String(required=False, allow_none=False, validate=validate.Length(1, 30)),
        'email': fields.String(
            required=False,
            allow_none=False,
            validate=(validate.Email(), validate.Length(min=5, max=25)),
        ),
        'password': fields.String(
            required=False,
            allow_none=False,
            validate=validate.Length(
                min=8,
                max=30,
            ),
        ),
        'old_password': fields.String(
            required=False,
            allow_none=False,
            validate=validate.Length(
                min=8,
                max=30,
            ),
        ),
    }
)
def patch_me(data: dict) -> None:
    if g.user is None:
        abort_auth()

    if data == {}:
        return prepare_user(g.user, True)

    password = data.get('password')
    old_password = data.get('old_password')

    if password is None and old_password:
        abort(jsonify({'_errors': {'password': ['Missing field']}}))

    if password and not old_password:
        abort(jsonify({'_errors': {'old_password': ['Missing field']}}))

    try:
        pswd_hasher.verify(g.user['password'], old_password)
    except argon2.exceptions.Argon2Error:
        abort(jsonify({'_errors': {'old_password': ['Invalid']}}))

    user = g.user
    user['password'] = password

    if data.get('email'):
        user['email'] = data['email']

    if data.get('username'):
        other_user = db.users.find_one({'username': data['username'], 'discriminator': user['discriminator']})

        if other_user is None:
            user['username'] = data['username']
        else:
            discrim: str | None = None
            for _ in range(9):
                d = generate_discriminator()
                q = len(
                    list(
                        db.users.find({'username': data['username'], 'discriminator': data['discriminator']})
                    )
                )
                if q >= 1:
                    continue
                discrim = d
                break

            if discrim is None:
                abort(jsonify({'_errors': {'username': ['Discriminator not available']}}, 400))

            user['username'] = data['username']
            data['discriminator'] = discrim

    db.users.update_one({'_id': g.user['_id']}, user)

    usr = prepare_user(user, True)
    publish_to_user(user['_id'], 'USER_UPDATE', usr)

    return jsonify(usr)


@version('/users/@me', 1, router, 'GET')
@limiter.limit('5/second')
def get_me() -> None:
    if g.user is None:
        abort_auth()

    return prepare_user(g.user, True)


@version('/login', 1, router, 'POST')
@limiter.limit('2/minute')
@flaskparser.use_args(
    {
        'email': fields.String(
            required=True,
            allow_none=False,
            validate=(validate.Email(), validate.Length(min=5, max=25)),
        ),
        'password': fields.String(
            required=True,
            allow_none=False,
            validate=validate.Length(
                min=8,
                max=30,
            ),
        ),
    }
)
def login(data: dict) -> None:
    if g.user is not None:
        abort_auth()

    user = db.users.find_one({'email': data['email']})

    if user is None:
        abort_auth()

    try:
        pswd_hasher.verify(user['password'], data['password'])
    except argon2.exceptions.Argon2Error:
        abort_auth()

    usr = dict(user)
    usr['token'] = auth.form(user['_id'], user['password'])
    return usr
