import os
from typing import Any, NoReturn

import flask_limiter.util
from flask import abort, g, jsonify, request
from flask_limiter import HEADERS, Limiter

from .authorizer import auth as auth_medium
from .database import User


def authorize_user() -> User | None:
    auth = request.headers.get('Authorization', None)

    if auth is None:
        return None

    return dict(auth_medium.verify(auth))


def get_key_value() -> str:
    user = authorize_user(False)

    g.user = user

    if user is None:
        return flask_limiter.util.get_remote_address()
    else:
        return user['_id']


limiter = Limiter(
    key_func=get_key_value,
    default_limits=['50/second'],
    headers_enabled=True,
    header_name_mapping={HEADERS.RETRY_AFTER: 'X-RateLimit-Retry-After'},
    storage_uri=os.getenv('STORAGE_URI', 'memory://'),
    strategy='moving-window',
    # I'd rather 500 than unsync'd rate limits
    in_memory_fallback_enabled=False,
    key_prefix='security.derailed.',
)


def prepare_user(user: User, own: bool = False) -> dict[str, Any]:
    if not own:
        user.pop('email')

    user.pop('password')
    return user


def abort_auth() -> NoReturn:
    abort(jsonify({'_errors': {'headers': {'authorization': ['missing']}}}), status=401)
