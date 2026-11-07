import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(dict(TESTING=True, BACKEND_MODE='demo',
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', UPLOAD_ROOT=str(tmp_path)))


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def payload():
    return dict(meal_type='lunch', meal_datetime='2026-11-01T12:30:00+08:00',
                items=[dict(food_name='cooked_white_rice', display_name='White rice', weight_g=180)])
