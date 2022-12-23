import marshmallow
from gevent import monkey
from webargs.flaskparser import parser

if monkey.is_anything_patched() is False:
    monkey.patch_all()

from flask import Flask, g, jsonify

from .database import User as _

app = Flask(__name__)
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


@app.after_request
def after_request(*args, **kwargs) -> None:
    g.pop('user', None)
