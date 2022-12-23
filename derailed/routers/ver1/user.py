from random import randint

from argon2 import PasswordHasher
from flask import Blueprint, abort, g, jsonify
from webargs import fields, flaskparser, validate

from ...database import User, _client, db
from ...identification import medium
from ...powerbase import abort_auth, prepare_user

router_v1 = Blueprint('user-v1', __name__, url_prefix='/v1')
pswd_hasher = PasswordHasher()


def generate_discriminator() -> str:
    discrim_number = randint(1, 9999)
    return '%04d' % discrim_number


@router_v1.post('/register')
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

    return jsonify(dict(user), status=201)


@router_v1.get('/users/@me')
def get_me() -> None:
    if g.user is None:
        abort_auth()

    return prepare_user(g.user, True)
