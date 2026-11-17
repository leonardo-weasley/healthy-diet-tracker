from flask import Blueprint, jsonify, request

from ..services import meal_service

bp = Blueprint('dashboard', __name__)


@bp.get('/dashboard/daily')
def daily():
    return jsonify(status='success', data=meal_service.get_daily_dashboard(request.args.get('date') or None))
