import re

from flask import Blueprint, jsonify, request

from ..services import meal_service
from ..services.schemas import validate_payload
from ..utils.errors import InvalidRequest

bp = Blueprint('meals', __name__)


def _integer(name, default, minimum, maximum=None):
    value = request.args.get(name, str(default))
    if not re.fullmatch(r'\d{1,12}', value):
        raise InvalidRequest(f'{name} must be an integer.')
    number = int(value)
    if number < minimum or (maximum is not None and number > maximum):
        raise InvalidRequest(f'{name} is out of range.')
    return number


@bp.post('/meals')
def create():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise InvalidRequest('Request body must be a JSON object.')
    data = meal_service.create_meal(validate_payload(body))
    return jsonify(status='success', data=data), 201


@bp.get('/meals')
def index():
    data = meal_service.list_meals(request.args.get('date_from'), request.args.get('date_to'),
        _integer('limit', 50, 1, 200), _integer('offset', 0, 0))
    return jsonify(status='success', data=data)


@bp.get('/meals/<meal_id>')
def detail(meal_id):
    if not re.fullmatch(r'[0-9]+', meal_id) or len(meal_id) > 18 or int(meal_id) <= 0:
        raise InvalidRequest('meal_id must be a positive integer.')
    return jsonify(status='success', data=meal_service.get_meal_detail(int(meal_id)))


@bp.delete('/meals/<int:meal_id>')
def delete(meal_id):
    return jsonify(status='success', data=meal_service.delete_meal(meal_id))
