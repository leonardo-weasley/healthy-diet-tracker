"""Offline acceptance demo; temporary uploads are cleaned up automatically."""
from tempfile import TemporaryDirectory

from app import create_app
from tests.helpers import upload


def main():
    with TemporaryDirectory() as root:
        app = create_app(dict(TESTING=True, BACKEND_MODE='demo', UPLOAD_ROOT=root,
                              SQLALCHEMY_DATABASE_URI='sqlite:///:memory:'))
        client = app.test_client()
        analysis = upload(client)
        assert analysis.status_code == 200
        data = analysis.json['data']
        print('1. Upload and analyze: OK (fixed DEMO result)')
        payload = dict(meal_type='lunch', meal_datetime='2026-11-01T12:30:00+08:00',
            image_path=data['image_path'], items=[dict(food_name=f['food_name'],
                display_name=f['display_name'], weight_g=f['estimated_weight_g']) for f in data['foods']])
        created = client.post('/api/v1/meals', json=payload)
        assert created.status_code == 201
        meal_id = created.json['data']['meal_id']
        print('2. Save meal: OK, id =', meal_id)
        detail = client.get(f'/api/v1/meals/{meal_id}')
        assert detail.status_code == 200
        print('3. Meal detail: OK, calories =', detail.json['data']['totals']['calories_kcal'])
        listing = client.get('/api/v1/meals')
        assert listing.json['data']['pagination']['count'] == 1
        print('4. Meal list: OK')
        daily = client.get('/api/v1/dashboard/daily?date=2026-11-01')
        assert daily.json['data']['meal_count'] == 1
        print('5. Daily dashboard: OK')
        assert client.delete(f'/api/v1/meals/{meal_id}').status_code == 200
        assert client.get(f'/api/v1/meals/{meal_id}').status_code == 404
        assert client.get('/api/v1/dashboard/daily?date=2026-11-01').json['data']['meal_count'] == 0
        print('6. Delete and verify dashboard: OK')
        print('All six API operations passed. No real AI or database was used.')


if __name__ == '__main__':
    main()
