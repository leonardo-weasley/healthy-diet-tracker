import pytest

from app import create_app
from app.services.demo import DemoBackend


def test_real_mode_never_falls_back(tmp_path, monkeypatch):
    def unavailable(name):
        raise ModuleNotFoundError('No module named app.ai')
    monkeypatch.setattr('app.services.dependencies.import_module', unavailable)
    with pytest.raises(ModuleNotFoundError, match='app.ai'):
        create_app(dict(BACKEND_MODE='real', UPLOAD_ROOT=str(tmp_path),
                        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:'))


def test_dependency_injection(tmp_path):
    backend = DemoBackend()
    names = ('analyze_food', 'calculate_meal_nutrition', 'save_meal', 'get_meal',
             'get_meals', 'delete_meal', 'get_daily_summary')
    dependencies = {name: getattr(backend, name) for name in names}
    app = create_app(dict(BACKEND_MODE='real', BACKEND_DEPENDENCIES=dependencies,
                         UPLOAD_ROOT=str(tmp_path), SQLALCHEMY_DATABASE_URI='sqlite:///:memory:'))
    assert app.extensions['meal_dependencies'] is dependencies
    assert app.test_client().get('/api/v1/dashboard/daily').status_code == 200


def test_missing_dependency_fails_early(tmp_path):
    with pytest.raises(ValueError, match='Missing backend dependency'):
        create_app(dict(BACKEND_DEPENDENCIES={}, UPLOAD_ROOT=str(tmp_path),
                        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:'))
