import pytest

from app.utils.errors import AiProviderError, DatabaseError, InvalidAiResponse
from tests.helpers import upload


@pytest.mark.parametrize('error,code', [
    (AiProviderError('provider secret must not leak'), 'AI_PROVIDER_ERROR'),
    (InvalidAiResponse('Invalid AI output'), 'INVALID_AI_RESPONSE'),
])
def test_ai_errors(client, app, monkeypatch, error, code):
    def fail(path):
        raise error
    monkeypatch.setattr(app.extensions['meal_dependencies'], 'analyze_food', fail)
    response = upload(client)
    assert response.status_code == 502
    assert response.json['error']['code'] == code


def test_database_error(client, app, payload, monkeypatch):
    def fail(data):
        raise DatabaseError('Unable to save meal.')
    monkeypatch.setattr(app.extensions['meal_dependencies'], 'save_meal', fail)
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 500
    assert response.json['error']['code'] == 'DATABASE_ERROR'


def test_internal_error(client, app, monkeypatch):
    def fail(date):
        raise RuntimeError('API_KEY=secret')
    monkeypatch.setattr(app.extensions['meal_dependencies'], 'get_daily_summary', fail)
    response = client.get('/api/v1/dashboard/daily')
    assert response.status_code == 500
    assert response.json['error']['code'] == 'INTERNAL_ERROR'
    assert 'secret' not in response.get_data(as_text=True)


def test_unsupported_media(client):
    response = upload(client, content=b'%PDF', mime='application/pdf')
    assert response.status_code == 415
    assert response.json['error']['code'] == 'UNSUPPORTED_MEDIA_TYPE'


@pytest.mark.parametrize('result', [None, {}, {'schema_version': '1.0', 'status': 'success', 'foods': ['bad'], 'warnings': []}])
def test_malformed_ai_response(client, app, monkeypatch, result):
    monkeypatch.setattr(app.extensions['meal_dependencies'], 'analyze_food', lambda _: result)
    response = upload(client)
    assert response.status_code == 502
    assert response.json['error']['code'] == 'INVALID_AI_RESPONSE'


def test_unrecognized_still_200(client, app, monkeypatch):
    monkeypatch.setattr(app.extensions['meal_dependencies'], 'analyze_food', lambda _: {
        'schema_version': '1.0', 'status': 'error', 'foods': [], 'warnings': ['No food recognized.']})
    response = upload(client)
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert response.json['data']['status'] == 'error'


def test_http_errors(client):
    response = client.get('/api/v1/does-not-exist')
    assert response.status_code == 404 and response.is_json
    response = client.put('/api/v1/meals', json={})
    assert response.status_code == 405 and response.is_json
    assert 'POST' in response.headers['Allow']
    assert client.get('/missing-page').mimetype == 'text/html'


def test_invalid_daily_date(client):
    assert client.get('/api/v1/dashboard/daily?date=2026-02-30').status_code == 400


def test_false_content_type(client):
    response = upload(client, mime='image/jpeg')  # PNG bytes with JPEG header.
    assert response.status_code == 400
    assert response.json['error']['code'] == 'INVALID_IMAGE'


@pytest.mark.parametrize('case,status,code', [
    ('request', 400, 'INVALID_REQUEST'),
    ('image', 400, 'INVALID_IMAGE'),
    ('size', 413, 'IMAGE_TOO_LARGE'),
    ('weight', 422, 'INVALID_WEIGHT'),
    ('food', 422, 'FOOD_NOT_FOUND'),
    ('meal', 404, 'MEAL_NOT_FOUND'),
])
def test_remaining_error_envelopes(client, payload, case, status, code):
    if case == 'request':
        response = client.post('/api/v1/meals', json={})
    elif case == 'image':
        response = upload(client, content=b'not an image')
    elif case == 'size':
        response = upload(client, content=b'x' * (9 * 1024 * 1024))
    elif case == 'weight':
        payload['items'][0]['weight_g'] = 0
        response = client.post('/api/v1/meals', json=payload)
    elif case == 'food':
        payload['items'][0]['food_name'] = 'xxx'
        response = client.post('/api/v1/meals', json=payload)
    else:
        response = client.get('/api/v1/meals/99999')
    assert response.status_code == status
    assert response.json['status'] == 'error'
    assert response.json['error']['code'] == code
    assert set(response.json['error']) == {'code', 'message', 'details'}
    assert response.content_type == 'application/json; charset=utf-8'
