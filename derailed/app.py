import dotenv
from gevent import monkey

if monkey.is_anything_patched() is False:
    monkey.patch_all()

import marshmallow
from flask import Flask, Response, g, jsonify
from webargs.flaskparser import parser

dotenv.load_dotenv()

from .database import User as _
from .powerbase import authorize_user, limiter
from .routers import user
from .routers.guilds import guild_information, guild_management

app = Flask(__name__)
limiter.init_app(app)
parser.DEFAULT_VALIDATION_STATUS = 400
parser.DEFAULT_LOCATION = 'json_or_form'

# connect blueprints
app.register_blueprint(user.router)
app.register_blueprint(guild_information.router)
app.register_blueprint(guild_management.router)


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
    return jsonify({'message': '404: Not Found', 'code': 0}), 404


@app.errorhandler(405)
def handle_405(*args):
    return jsonify({'message': '405: Invalid Method', 'code': 0}), 405


@app.errorhandler(500)
def handle_500(*args):
    return jsonify({'message': '500: Internal Server Error', 'code': 0}), 500


@app.before_request
def before_request(*args, **kwargs) -> None:
    g.user = authorize_user()


@app.after_request
def after_request(resp: Response) -> None:
    g.pop('user', None)
    return resp
