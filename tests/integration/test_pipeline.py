from tests.helpers import upload


def test_complete_pipeline(client):
    analyzed = upload(client)
    assert analyzed.status_code == 200
    analysis = analyzed.json['data']
    foods = analysis['foods']
    payload = dict(meal_type='lunch', meal_datetime='2026-11-01T12:30:00+08:00',
        image_path=analysis['image_path'], items=[dict(food_name=f['food_name'],
            display_name=f['display_name'], weight_g=f['estimated_weight_g']) for f in foods])
    response = client.post('/api/v1/meals', json=payload)
    assert response.status_code == 201
    meal_id = response.json['data']['meal_id']
    assert client.get(f'/api/v1/meals/{meal_id}').status_code == 200
    assert client.get('/api/v1/meals').json['data']['pagination']['count'] == 1
    before = client.get('/api/v1/dashboard/daily?date=2026-11-01').json['data']
    assert before['meal_count'] == 1 and before['totals']['calories_kcal'] == 234
    assert client.delete(f'/api/v1/meals/{meal_id}').status_code == 200
    after = client.get('/api/v1/dashboard/daily?date=2026-11-01').json['data']
    assert after['meal_count'] == 0 and after['totals']['calories_kcal'] == 0
