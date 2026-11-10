"""Application factory.

NOTE (handoff): this module is owned by member 1 in the team plan.  The
version here is the minimal, contract-compatible factory that the database
and test layers need.  Member 1 replaces/extents it without changing the
public entry point ``create_app(config=None)``.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask

from .extensions import db


def create_app(test_config: dict | None = None) -> Flask:
    """Build a Flask application.

    ``test_config`` is applied on top of the defaults, which is how the test
    suite injects ``sqlite:///:memory:``.
    """
    app = Flask(__name__, instance_relative_config=True)

    instance_dir = Path(app.instance_path)
    default_db_uri = "sqlite:///" + (instance_dir / "diet_tracker.db").as_posix()

    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=default_db_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        APP_TIMEZONE="Asia/Shanghai",
        # Upload limit for POST /analyze (10 MiB).
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        MAX_IMAGE_BYTES=10 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    # The in-memory test database does not need the instance directory.
    if ":memory:" not in app.config["SQLALCHEMY_DATABASE_URI"]:
        instance_dir.mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    # Imported lazily: the blueprint imports models, which import ``db`` from
    # this package's ``extensions`` module.
    from .api.routes import api_bp

    app.register_blueprint(api_bp)

    from .api.errors import register_error_handlers

    register_error_handlers(app)

    return app
