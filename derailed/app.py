import dotenv
from gevent import monkey

if monkey.is_anything_patched() is False:
    monkey.patch_all()

import marshmallow
from flask import Flask, Response, g, request
from flask_cors import CORS
from webargs.flaskparser import parser
import werkzeug.exceptions

dotenv.load_dotenv()

from .json import Decoder, Encoder
from .powerbase import authorize_user, limiter
from .routers import user
from .routers.guilds import guild_information, guild_management
from .routers.channels import guild_channel, message

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.json_encoder = Encoder
app.json_decoder = Decoder
limiter.init_app(app)
parser.DEFAULT_VALIDATION_STATUS = 400
parser.DEFAULT_LOCATION = 'json_or_form'

# connect blueprints
app.register_blueprint(user.router)
app.register_blueprint(guild_information.router)
app.register_blueprint(guild_management.router)
app.register_blueprint(guild_channel.router)
app.register_blueprint(message.router)


@app.errorhandler(422)
@app.errorhandler(400)
def handle_error(err: werkzeug.exceptions.BadRequest):
    if not isinstance(err, marshmallow.ValidationError):
        return {'_error': 'Bad Request'}, 400

    headers = err.data.get('headers', None)
    messages = err.data.get('messages', [])

    if messages != []:
        new_messages = messages.get('json_or_form')

        if new_messages is None:
            return {'_error': messages}, err.code, headers
        else:
            messages = new_messages
    if headers:
        return {'_errors': messages}, err.code, headers
    else:
        return {'_errors': messages}, err.code


@app.errorhandler(404)
def handle_404(*args):
    return {'message': '404: Not Found', 'code': 0}, 404


@app.errorhandler(405)
def handle_405(*args):
    return {'message': '405: Invalid Method', 'code': 0}, 405


@app.errorhandler(500)
def handle_500(*args):
    return {'message': '500: Internal Server Error', 'code': 0}, 500


@app.before_request
def before_request() -> None:
    g.user = authorize_user()


@app.after_request
def after_request(resp: Response) -> None:
    g.pop('user', None)
    resp.headers.add('Via', '1.1 cf + py')
    return resp
