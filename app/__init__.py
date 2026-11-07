from pathlib import Path
import logging
import traceback
from zoneinfo import ZoneInfo

from flask import Flask, appcontext_pushed, g, jsonify, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from .config import Config
from .extensions import db
from .runtime import bind_runtime, reset_runtime
from .utils.errors import ApiError, ImageTooLarge


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(Config.values())
    app.config.update(test_config or {})
    ZoneInfo(app.config['APP_TIMEZONE'])
    if app.config['UPLOAD_MAX_BYTES'] <= 0 or app.config['UPLOAD_MAX_SIDE'] <= 0:
        raise ValueError('Upload limits must be positive.')
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    (Path(app.config['UPLOAD_ROOT']) / 'uploads').mkdir(parents=True, exist_ok=True)
    app.json.ensure_ascii = False
    app.logger.setLevel(logging.INFO)
    db.init_app(app)
    from .services.dependencies import init_dependencies
    init_dependencies(app)

    def bind_context(sender, **extra):
        g._meal_runtime_token = bind_runtime(app.config, app.extensions['meal_dependencies'])

    appcontext_pushed.connect(bind_context, app, weak=False)

    @app.teardown_appcontext
    def unbind_context(error):
        token = g.pop('_meal_runtime_token', None)
        if token is not None:
            reset_runtime(token)

    from .routes import register_blueprints
    register_blueprints(app)

    @app.after_request
    def json_charset(response):
        if response.is_json:
            response.content_type = 'application/json; charset=utf-8'
        return response

    @app.errorhandler(ApiError)
    def api_error(error):
        return jsonify(status='error', error=dict(
            code=error.code, message=str(error.message)[:200], details=error.details)), error.http_status

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return api_error(ImageTooLarge('Image exceeds the configured upload limit.'))

    @app.errorhandler(HTTPException)
    def http_error(error):
        if not request.path.startswith('/api/'):
            return error
        response = error.get_response()
        response.set_data(app.json.dumps(dict(status='error', error=dict(
            code='MEAL_NOT_FOUND' if error.code == 404 else 'INVALID_REQUEST',
            message=error.description, details=None))))
        response.content_type = 'application/json; charset=utf-8'
        return response

    @app.errorhandler(Exception)
    def unexpected(error):
        # Keep stack locations, but omit exception text, source lines and locals.
        frames = [dict(file=f.filename, line=f.lineno, function=f.name)
                  for f in traceback.extract_tb(error.__traceback__)]
        app.logger.error('Unhandled server error: %s stack=%s', type(error).__name__, frames)
        return api_error(ApiError('INTERNAL_ERROR', 'Unexpected server error.', 500))

    return app
