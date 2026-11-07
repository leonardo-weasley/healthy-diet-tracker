"""Orchestration only: validate -> call upstream modules -> assemble -> persist."""
import logging
from time import perf_counter

from .dependencies import dependency
from .contracts import AnalysisResult, DailyResult, MealRecord, MealSummary, NutritionResult, check_contract
from ..runtime import settings
from ..utils.errors import AiProviderError, DatabaseError, FoodNotFound, InvalidAiResponse, InvalidRequest, MealNotFound
from ..utils.images import is_safe_image_path
from ..utils.timeutil import local_date_of, to_utc_iso, today_local, validate_date

log = logging.getLogger(__name__)


def analyze_uploaded_meal(image_path, meal_type):
    started = perf_counter()
    try:
        result = check_contract(AnalysisResult, dependency('analyze_food')(image_path), 'ai')
    except AiProviderError:
        log.warning('AI provider failure image_path=%s provider_status=unavailable elapsed_ms=%.1f',
                    image_path, (perf_counter() - started) * 1000)
        raise
    except InvalidAiResponse:
        log.warning('AI validation failure image_path=%s reason=contract_A elapsed_ms=%.1f',
                    image_path, (perf_counter() - started) * 1000)
        raise
    log.info('Analyzed image_path=%s model=%s elapsed_ms=%.1f status=%s foods=%d',
             image_path, settings()['AI_MODEL'] or settings()['BACKEND_MODE'],
             (perf_counter() - started) * 1000, result['status'], len(result['foods']))
    return {**result, 'image_path': image_path}


def create_meal(payload):
    image_path = payload.get('image_path')
    if image_path is not None and not is_safe_image_path(image_path):
        image_path = None
    utc = to_utc_iso(payload['meal_datetime'])
    meal_date = local_date_of(payload['meal_datetime'])
    # G/G.1 specify the AI-style weight field at the nutrition boundary.
    foods = [dict(food_name=item['food_name'], display_name=item['display_name'],
                  estimated_weight_g=item['weight_g']) for item in payload['items']]
    nutrition = check_contract(NutritionResult,
        dependency('calculate_meal_nutrition')(foods), 'nutrition')
    if not nutrition['items']:
        raise FoodNotFound('No food could be matched.', details={'warnings': nutrition['warnings']})
    meal_data = dict(meal_type=payload['meal_type'], meal_datetime_utc=utc,
                     meal_date=meal_date, image_path=image_path,
                     items=nutrition['items'], warnings=nutrition['warnings'],
                     totals=nutrition['totals'])
    meal_id = _repository_call('save_meal', meal_data)
    return get_meal_detail(meal_id)


def get_meal_detail(meal_id):
    meal = _repository_call('get_meal', meal_id)
    if meal is None:
        raise MealNotFound('Meal not found.', details={'meal_id': meal_id})
    check_contract(MealRecord, meal, 'database')
    return meal


def list_meals(date_from, date_to, limit, offset):
    if (date_from is None) != (date_to is None):
        raise InvalidRequest('date_from and date_to must be provided together.')
    if date_from is not None:
        date_from, date_to = validate_date(date_from), validate_date(date_to)
        if date_from > date_to:
            raise InvalidRequest('date_from must not be later than date_to.')
    meals = _repository_call('get_meals', date_from, date_to)
    if not isinstance(meals, list):
        raise DatabaseError('Repository must return a list of meal summaries.')
    summaries = meals[offset:offset + limit]
    for summary in summaries:
        check_contract(MealSummary, summary, 'database')
    return dict(meals=summaries, pagination=dict(limit=limit, offset=offset, count=len(summaries)))


def delete_meal(meal_id):
    if not _repository_call('delete_meal', meal_id):
        raise MealNotFound('Meal not found.', details={'meal_id': meal_id})
    return dict(meal_id=meal_id, deleted=True)


def get_daily_dashboard(date):
    result = _repository_call('get_daily_summary', validate_date(date) if date else today_local())
    check_contract(DailyResult, result, 'database')
    return result


def _repository_call(name, *args):
    try:
        return dependency(name)(*args)
    except DatabaseError as error:
        meal_id = args[0] if name in ('get_meal', 'delete_meal') else None
        log.error('Database failure operation=%s meal_id=%s exception=%s',
                  name, meal_id, type(error).__name__)
        raise
