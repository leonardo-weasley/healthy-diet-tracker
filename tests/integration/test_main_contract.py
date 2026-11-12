import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from inspect import signature
from pathlib import Path

import pytest

from app import create_app
from app.runtime import settings
from app.services.demo import DemoBackend
from tests.helpers import upload


def test_repository_two_arguments_and_service_pagination(client, app, monkeypatch):
    calls = []
    rows = [dict(meal_id=i, meal_type='lunch', meal_datetime='2026-11-01T12:00:00+08:00',
                 meal_date='2026-11-01', display_summary='Rice', calories_kcal=234., item_count=1)
            for i in range(5, 0, -1)]

    def get_meals(date_from=None, date_to=None):
        calls.append((date_from, date_to))
        return rows

    monkeypatch.setattr(app.extensions['meal_dependencies'], 'get_meals', get_meals)
    response = client.get('/api/v1/meals?date_from=2026-11-01&date_to=2026-11-02&limit=2&offset=1')
    assert response.status_code == 200
    assert [m['meal_id'] for m in response.json['data']['meals']] == [4, 3]
    assert calls == [('2026-11-01', '2026-11-02')]
    assert list(signature(DemoBackend.get_meals).parameters) == ['self', 'date_from', 'date_to']


def test_confirmed_weight_translated_to_nutrition_input(client, app, monkeypatch, payload):
    original = app.extensions['meal_dependencies'].calculate_meal_nutrition
    captured = []

    def calculate(foods):
        captured.extend(deepcopy(foods))
        assert foods[0]['estimated_weight_g'] == pytest.approx(180, abs=.01)
        assert 'weight_g' not in foods[0]
        assert 'calories_kcal' not in foods[0]
        return original(foods)

    monkeypatch.setattr(app.extensions['meal_dependencies'], 'calculate_meal_nutrition', calculate)
    assert client.post('/api/v1/meals', json=payload).status_code == 201
    assert len(captured) == 1


@pytest.mark.parametrize('hours,expected', [(12, 201), (48, 400)])
def test_future_datetime_limit(client, payload, hours, expected):
    payload['meal_datetime'] = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == expected


def test_food_name_required_but_null_allowed(client, payload):
    del payload['items'][0]['food_name']
    assert client.post('/api/v1/meals', json=payload).status_code == 400
    payload['items'][0]['food_name'] = None
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 422
    assert response.json['error']['code'] == 'FOOD_NOT_FOUND'


@pytest.mark.parametrize('meal_id', ['0', '-1', 'abc', '1.5'])
def test_invalid_detail_ids_are_400(client, meal_id):
    response = client.get('/api/v1/meals/' + meal_id)
    assert response.status_code == 400
    assert response.json['error']['code'] == 'INVALID_REQUEST'


def test_summary_first_three_names(client, payload):
    payload['items'] = [dict(food_name='cooked_white_rice', display_name=f'Rice {i}', weight_g=100)
                        for i in range(5)]
    assert client.post('/api/v1/meals', json=payload).status_code == 201
    summary = client.get('/api/v1/meals').json['data']['meals'][0]
    assert summary['display_summary'] == 'Rice 0, Rice 1, Rice 2 +2'
    assert summary['item_count'] == 5


def test_record_creation_source_and_snapshot(client, app, monkeypatch, payload):
    created = client.post('/api/v1/meals', json=payload).json['data']
    assert created['created_at'].endswith('Z')
    assert created['items'][0]['food_data_source'] == 'custom'

    def forbidden(items):
        raise AssertionError('Reading a meal must not recalculate nutrition')

    monkeypatch.setattr(app.extensions['meal_dependencies'], 'calculate_meal_nutrition', forbidden)
    detail = client.get(f"/api/v1/meals/{created['meal_id']}").json['data']
    assert detail == created


def test_single_final_rounding(client, payload):
    # Each 0.1 g portion is 0.13 kcal; rounding each first would yield 0.2,
    # whereas the required total is round(0.13 + 0.13, 1) = 0.3.
    payload['items'] = [dict(food_name='cooked_white_rice', display_name='Rice', weight_g=.1)
                        for _ in range(2)]
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 201
    assert response.json['data']['totals']['calories_kcal'] == pytest.approx(.3, abs=.01)


@pytest.mark.parametrize('change', [
    {'food_name': 'White Rice'}, {'food_name': 'a' * 61}, {'display_name': ''},
    {'display_name': 'x' * 101}, {'estimated_weight_g': 5001},
    {'estimated_weight_g': True}, {'confidence': '0.95'}, {'notes': 'x' * 201},
])
def test_ai_field_constraints(client, app, monkeypatch, change):
    backend = app.extensions['meal_dependencies']
    result = backend.analyze_food('unused')
    result['foods'][0].update(change)
    monkeypatch.setattr(backend, 'analyze_food', lambda _: result)
    response = upload(client)
    assert response.status_code == 502
    assert response.json['error']['code'] == 'INVALID_AI_RESPONSE'


def test_optional_ai_notes(client, app, monkeypatch):
    backend = app.extensions['meal_dependencies']
    result = backend.analyze_food('unused')
    del result['foods'][0]['notes']
    monkeypatch.setattr(backend, 'analyze_food', lambda _: result)
    assert upload(client).status_code == 200


def test_ai_food_limit(client, app, monkeypatch):
    backend = app.extensions['meal_dependencies']
    result = backend.analyze_food('unused')
    result['foods'] = result['foods'] * 21
    monkeypatch.setattr(backend, 'analyze_food', lambda _: result)
    assert upload(client).status_code == 502


def test_bad_database_record_rejected(client, app, monkeypatch):
    monkeypatch.setattr(app.extensions['meal_dependencies'], 'get_meal', lambda _: {'meal_id': 1})
    response = client.get('/api/v1/meals/1')
    assert response.status_code == 500
    assert response.json['error']['code'] == 'DATABASE_ERROR'


def test_bad_nutrition_boundary_rejected(client, app, monkeypatch, payload):
    monkeypatch.setattr(app.extensions['meal_dependencies'], 'calculate_meal_nutrition',
                        lambda _: {'items': [], 'totals': {}, 'warnings': []})
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 500
    assert response.json['error']['code'] == 'INTERNAL_ERROR'


def test_delete_keeps_uploaded_image(client, app, payload):
    path = upload(client).json['data']['image_path']
    payload['image_path'] = path
    created = client.post('/api/v1/meals', json=payload).json['data']
    assert client.delete(f"/api/v1/meals/{created['meal_id']}").status_code == 200
    assert (Path(app.config['UPLOAD_ROOT']) / path).is_file()


def test_pure_backend_modules_do_not_import_flask():
    root = Path(__file__).resolve().parents[2] / 'app'
    for path in root.rglob('*.py'):
        if path == root / '__init__.py' or 'routes' in path.relative_to(root).parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != 'flask', str(path)
            elif isinstance(node, ast.Import):
                assert all(name.name != 'flask' for name in node.names), str(path)


def test_nested_context_settings_are_restored(app, tmp_path):
    other = create_app(dict(APP_TIMEZONE='UTC', BACKEND_MODE='demo', UPLOAD_ROOT=str(tmp_path),
                            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:'))
    with app.app_context():
        assert settings()['APP_TIMEZONE'] == 'Asia/Shanghai'
        with other.app_context():
            assert settings()['APP_TIMEZONE'] == 'UTC'
        assert settings()['APP_TIMEZONE'] == 'Asia/Shanghai'


def test_internal_error_logs_stack_locations_without_secret(client, app, monkeypatch, caplog):
    def broken(date):
        raise RuntimeError('API_KEY=never-log-this')
    monkeypatch.setattr(app.extensions['meal_dependencies'], 'get_daily_summary', broken)
    assert client.get('/api/v1/dashboard/daily').status_code == 500
    assert 'stack=' in caplog.text and 'broken' in caplog.text
    assert 'never-log-this' not in caplog.text
