from flask import Blueprint

from . import analysis, dashboard, meals, pages


def register_blueprints(app):
    api = Blueprint('api_v1', __name__, url_prefix='/api/v1')
    for blueprint in (analysis.bp, meals.bp, dashboard.bp):
        api.register_blueprint(blueprint)
    app.register_blueprint(api)
    app.register_blueprint(pages.bp)
