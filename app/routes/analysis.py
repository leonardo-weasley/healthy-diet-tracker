from flask import Blueprint, jsonify, request

from ..services import meal_service
from ..services.schemas import MEAL_TYPES
from ..utils.errors import InvalidRequest
from ..utils.images import save_upload

bp = Blueprint('analysis', __name__)


@bp.post('/analyze')
def analyze():
    if 'image' not in request.files:
        raise InvalidRequest("Field 'image' is required.")
    meal_type = request.form.get('meal_type')
    if meal_type not in MEAL_TYPES:
        raise InvalidRequest('Invalid meal_type.', details={'allowed': sorted(MEAL_TYPES)})
    path = save_upload(request.files['image'])
    return jsonify(status='success', data=meal_service.analyze_uploaded_meal(path, meal_type))
