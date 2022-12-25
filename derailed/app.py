from gevent import monkey

if monkey.is_anything_patched() is False:
    monkey.patch_all()

import marshmallow
from flask import Flask, Response, g, jsonify
from msgspec import json
from webargs.flaskparser import parser

from .database import User as _
from .powerbase import limiter

app = Flask(__name__)
app.json_encoder = json.encode
app.json_decoder = json.decode
limiter.init_app(app)
parser.DEFAULT_VALIDATION_STATUS = 400
parser.DEFAULT_LOCATION = 'json_or_form'


@app.errorhandler(422)
@app.errorhandler(400)
def handle_error(err: marshmallow.ValidationError):
    headers = err.data.get('headers', None)
    messages = err.data.get('messages', [])

    if messages != []:
        messages = messages['json_or_form']
    if headers:
        return jsonify({'_errors': messages}), err.code, headers
    else:
        return jsonify({'_errors': messages}), err.code


@app.errorhandler(404)
def handle_404(*args):
    return jsonify({'message': '404: Not Found', 'code': 0})


@app.errorhandler(405)
def handle_405(*args):
    return jsonify({'message': '405: Invalid Method', 'code': 0})


@app.errorhandler(500)
def handle_500(*args):
    return jsonify({'message': '500: Internal Server Error', 'code': 0})


@app.after_request
def after_request(resp: Response) -> None:
    g.pop('user', None)
    return resp
