import io
from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image

from app.utils.images import is_safe_image_path
from app.utils.timeutil import local_date_of, to_local_iso, to_utc_iso


def upload(client, data=None, content=None, mime='image/png'):
    if content is None:
        stream = io.BytesIO()
        Image.new('RGB', (40, 20), 'white').save(stream, 'PNG')
        content = stream.getvalue()
    fields = dict(meal_type='lunch', image=(io.BytesIO(content), 'meal.png', mime))
    fields.update(data or {})
    return client.post('/api/v1/analyze', data=fields)


def test_b1_analyze(client, app):
    response = upload(client)
    assert response.status_code == 200
    data = response.json['data']
    assert data['foods'] and data['image_path'].startswith('uploads/')
    assert response.content_type == 'application/json; charset=utf-8'
    with app.app_context():
        assert is_safe_image_path(data['image_path'])
    with Image.open(Path(app.config['UPLOAD_ROOT']) / data['image_path']) as img:
        assert img.format == 'JPEG' and not img.getexif()


def test_b2_missing_image(client):
    response = client.post('/api/v1/analyze', data={'meal_type': 'lunch'})
    assert response.status_code == 400
    assert response.json['error']['code'] == 'INVALID_REQUEST'


def test_b3_invalid_image(client):
    response = upload(client, content=b'not an image')
    assert response.status_code == 400
    assert response.json['error']['code'] == 'INVALID_IMAGE'


def test_b4_large_image(client):
    response = upload(client, content=b'x' * (9 * 1024 * 1024))
    assert response.status_code == 413
    assert response.json['error']['code'] == 'IMAGE_TOO_LARGE'


def test_b5_invalid_meal_type(client):
    response = upload(client, {'meal_type': 'pizza'})
    assert response.status_code == 400


def test_b6_create_meal(client, payload):
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 201
    assert isinstance(response.json['data']['meal_id'], int)
    assert response.json['data']['totals']['calories_kcal'] == pytest.approx(234)


@pytest.mark.parametrize('weight', [0, -1, 5001, None, 'bad', True, '180', float('inf'), float('nan')])
def test_b7_invalid_weight(client, payload, weight):
    payload['items'][0]['weight_g'] = weight
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 422
    assert response.json['error']['code'] == 'INVALID_WEIGHT'


def test_b8_all_unmatched(client, payload):
    payload['items'][0]['food_name'] = 'xxx'
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 422
    assert response.json['error']['code'] == 'FOOD_NOT_FOUND'


def test_b9_partial_match(client, payload):
    unknown = deepcopy(payload['items'][0])
    unknown['food_name'] = 'xxx'
    payload['items'].append(unknown)
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 201
    assert response.json['data']['warnings']
    assert len(response.json['data']['items']) == 1


def test_b10_missing_meal(client):
    response = client.get('/api/v1/meals/99999')
    assert response.status_code == 404
    assert response.json['error']['code'] == 'MEAL_NOT_FOUND'


def test_b11_delete(client, payload):
    meal_id = client.post('/api/v1/meals', json=payload).json['data']['meal_id']
    assert client.delete(f'/api/v1/meals/{meal_id}').json['data']['deleted'] is True
    assert client.get(f'/api/v1/meals/{meal_id}').status_code == 404
    assert client.delete(f'/api/v1/meals/{meal_id}').status_code == 404


@pytest.mark.parametrize('query', [
    '?date_from=2026-11-01', '?date_to=2026-11-01',
    '?date_from=2026-02-30&date_to=2026-11-01',
    '?date_from=2026-11-02&date_to=2026-11-01',
    '?date_from=&date_to=', '?limit=0', '?limit=201', '?limit=x',
    '?offset=-1', '?limit=1.5', '?offset=999999999999999999999999999999',
])
def test_b12_invalid_query(client, query):
    response = client.get('/api/v1/meals' + query)
    assert response.status_code == 400
    assert response.json['error']['code'] == 'INVALID_REQUEST'


def test_b13_dashboard(client, payload):
    assert client.get('/api/v1/dashboard/daily?date=').status_code == 200
    client.post('/api/v1/meals', json=payload)
    data = client.get('/api/v1/dashboard/daily?date=2026-11-01').json['data']
    assert data['meal_count'] == 1
    assert data['totals']['calories_kcal'] == pytest.approx(234)
    empty = client.get('/api/v1/dashboard/daily?date=2000-01-01').json['data']
    assert empty['meal_count'] == 0 and all(v == 0 for v in empty['totals'].values())


def test_b14_ignore_client_calories(client, payload):
    payload['items'][0]['calories_kcal'] = 99999
    payload['totals'] = {'calories_kcal': 99999}
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 201
    assert response.json['data']['totals']['calories_kcal'] == pytest.approx(234)


@pytest.mark.parametrize('body', [{}, [], None, {'items': []}])
def test_b15_empty_body(client, body):
    response = client.post('/api/v1/meals', json=body)
    assert response.status_code == 400


@pytest.mark.parametrize('path', ['../secret', '/etc/passwd', 'uploads/../secret',
    'uploads/missing.jpg', 'C:/secret', 'uploads\\bad.jpg', 'uploads//bad.jpg'])
def test_unsafe_image_path(client, payload, path):
    payload['image_path'] = path
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 201
    assert response.json['data']['image_path'] is None


def test_timezone(app):
    with app.app_context():
        assert to_utc_iso('2026-11-01T12:30:00+08:00') == '2026-11-01T04:30:00Z'
        assert to_utc_iso('2026-11-01T12:30:00') == '2026-11-01T04:30:00Z'
        assert local_date_of('2026-11-01T18:00:00Z') == '2026-11-02'
        assert to_local_iso('2026-11-01T04:30:00Z') == '2026-11-01T12:30:00+08:00'


def test_list_pagination(client, payload):
    for _ in range(3):
        assert client.post('/api/v1/meals', json=payload).status_code == 201
    data = client.get('/api/v1/meals?limit=1&offset=1&date_from=2026-11-01&date_to=2026-11-01').json['data']
    assert data['pagination'] == {'limit': 1, 'offset': 1, 'count': 1}
    assert data['meals'][0]['display_summary'] == 'White rice'
    assert data['meals'][0]['item_count'] == 1


@pytest.mark.parametrize('path', ['/', '/upload', '/result', '/history'])
def test_pages(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.mimetype == 'text/html'


def test_resize_exif(client, app):
    image = Image.new('RGB', (1600, 800), 'white')
    exif = Image.Exif()
    exif[274] = 6
    stream = io.BytesIO()
    image.save(stream, 'JPEG', exif=exif)
    response = upload(client, content=stream.getvalue(), mime='image/jpeg')
    with Image.open(Path(app.config['UPLOAD_ROOT']) / response.json['data']['image_path']) as saved:
        assert saved.size == (512, 1024)
        assert not saved.getexif()


def test_exact_file_limit(client, app):
    stream = io.BytesIO()
    Image.new('RGB', (10, 10)).save(stream, 'PNG')
    raw = stream.getvalue()
    app.config['UPLOAD_MAX_BYTES'] = len(raw)
    assert upload(client, content=raw).status_code == 200
    assert upload(client, content=raw + b'x').status_code == 413


def test_apps_isolated(client, payload, tmp_path):
    from app import create_app
    client.post('/api/v1/meals', json=payload)
    other = create_app(dict(TESTING=True, BACKEND_MODE='demo', UPLOAD_ROOT=str(tmp_path),
                            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:'))
    assert other.test_client().get('/api/v1/meals').json['data']['meals'] == []
