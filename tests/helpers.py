import io

from PIL import Image


def upload(client, data=None, content=None, mime='image/png'):
    if content is None:
        stream = io.BytesIO()
        Image.new('RGB', (40, 20), 'white').save(stream, 'PNG')
        content = stream.getvalue()
    fields = dict(meal_type='lunch', image=(io.BytesIO(content), 'meal.png', mime))
    fields.update(data or {})
    return client.post('/api/v1/analyze', data=fields)
