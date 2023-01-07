import base64
import binascii
from typing import NoReturn

import itsdangerous
import msgspec
import urllib3
from flask import abort

from .database import User, db
from .json import proper

_pool = urllib3.HTTPConnectionPool('localhost:4600', headers={'Content-Type': 'application/json'})


class AuthMedium:
    def form(self, user_id: str, password: str) -> str:
        user_id = base64.urlsafe_b64encode(user_id.encode())

        signer = itsdangerous.TimestampSigner(password)
        return signer.sign(user_id).decode()

    def _abort(self) -> NoReturn:
        abort(proper({'_errors': ['Invalid Authentication']}, status=401))

    def verify(self, token: str) -> User | None:
        splits = token.split('.')

        try:
            user_id = splits[0]
            user_id = base64.urlsafe_b64decode(user_id).decode()
        except (binascii.Error, UnicodeDecodeError, IndexError):
            return

        user = db.users.find_one({'_id': user_id})

        if user is None:
            return

        json = msgspec.json.encode({'token': token, 'user_id': user['_id'], 'password': user['password']})

        req: urllib3.response.HTTPResponse = _pool.request('POST', '/validate', body=json)

        resp = msgspec.json.decode(req.data, type=dict)

        if resp['is_valid'] == True:
            return user
        else:
            return


auth = AuthMedium()
