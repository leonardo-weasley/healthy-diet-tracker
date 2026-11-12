"""Explicit offline fixtures, NOT production AI, nutrition data or a database.

This module is replaceable through BACKEND_DEPENDENCIES or BACKEND_MODE=real.
Each Flask app gets its own repository. Restarting the app clears all meals.
"""
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock

from ..utils.timeutil import to_local_iso

NUTRIENTS = ('calories_kcal', 'protein_g', 'fat_g', 'carbs_g')
# Synthetic integration fixtures per 100 g; not an authoritative food database.
FIXTURES = {
    'cooked_white_rice': (130., 2.7, .3, 28.2),
    'grilled_chicken_breast': (165., 31., 3.6, 0.),
}


def totals(items):
    return {key: round(sum(item[key] for item in items), 1 if key == 'calories_kcal' else 2)
            for key in NUTRIENTS}


class DemoBackend:
    def __init__(self):
        self._meals = {}
        self._next_id = 1
        self._lock = RLock()

    def analyze_food(self, image_path):
        return dict(schema_version='1.0', status='success', foods=[dict(
            food_name='cooked_white_rice', display_name='White rice',
            estimated_weight_g=180., confidence=.95, notes='DEMO fixture; not image recognition.')],
            warnings=['demo_mode: fixed recognition result; not real AI'])

    def calculate_meal_nutrition(self, foods):
        items, warnings = [], []
        for food in foods:
            fixture = FIXTURES.get(food.get('food_name'))
            if fixture is None:
                warnings.append('food_not_matched: ' + food['display_name'])
                continue
            weight = food['estimated_weight_g']
            item = {key: food[key] for key in ('food_name', 'display_name')}
            item.update(weight_g=weight, food_data_source='custom')
            item.update({key: value * weight / 100
                         for key, value in zip(NUTRIENTS, fixture)})
            items.append(item)
        aggregate = totals(items)
        for item in items:
            for key in NUTRIENTS:
                item[key] = round(item[key], 1 if key == 'calories_kcal' else 2)
        return dict(schema_version='1.0', items=items, totals=aggregate, warnings=warnings)

    def save_meal(self, meal_data):
        with self._lock:
            meal_id = self._next_id
            self._next_id += 1
            meal = deepcopy(meal_data)
            meal['meal_id'] = meal_id
            meal['meal_datetime'] = to_local_iso(meal.pop('meal_datetime_utc'))
            meal['created_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
            meal['totals'] = deepcopy(meal_data.get('totals', totals(meal['items'])))
            self._meals[meal_id] = meal
            return meal_id

    def get_meal(self, meal_id):
        with self._lock:
            return deepcopy(self._meals.get(meal_id))

    def get_meals(self, date_from=None, date_to=None):
        with self._lock:
            meals = [deepcopy(m) for m in self._meals.values()
                     if date_from is None or date_from <= m['meal_date'] <= date_to]
        meals.sort(key=lambda m: (m['meal_datetime'], m['meal_id']), reverse=True)
        summaries = []
        for meal in meals:
            items = meal['items']
            summary = ', '.join(item['display_name'] for item in items[:3])
            if len(items) > 3:
                summary += f' +{len(items) - 3}'
            summaries.append(dict(meal_id=meal['meal_id'], meal_type=meal['meal_type'],
                meal_datetime=meal['meal_datetime'], meal_date=meal['meal_date'],
                display_summary=summary, calories_kcal=meal['totals']['calories_kcal'],
                item_count=len(items)))
        return summaries

    def delete_meal(self, meal_id):
        with self._lock:
            return self._meals.pop(meal_id, None) is not None

    def get_daily_summary(self, date):
        with self._lock:
            meals = [m for m in self._meals.values() if m['meal_date'] == date]
            return dict(date=date, meal_count=len(meals),
                        totals=totals([meal['totals'] for meal in meals]))
