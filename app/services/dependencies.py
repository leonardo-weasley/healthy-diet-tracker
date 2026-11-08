from importlib import import_module

from ..runtime import backend as current_backend


def init_dependencies(app):
    injected = app.config.get('BACKEND_DEPENDENCIES')
    if injected is not None:
        dependencies = injected
    elif app.config['BACKEND_MODE'] == 'demo':
        from .demo import DemoBackend
        dependencies = DemoBackend()
        app.logger.warning('DEMO MODE: fixed AI/nutrition fixtures and volatile in-memory storage.')
    elif app.config['BACKEND_MODE'] == 'real':
        # Import failures are intentional: never silently fall back to mock data.
        ai = import_module('app.ai.image_analyzer')
        nutrition = import_module('app.nutrition.calculator')
        repository = import_module('app.database.repository')
        dependencies = dict(analyze_food=ai.analyze_food,
                            calculate_meal_nutrition=nutrition.calculate_meal_nutrition,
                            **{name: getattr(repository, name) for name in (
                                'save_meal', 'get_meal', 'get_meals', 'delete_meal', 'get_daily_summary')})
    else:
        raise ValueError('BACKEND_MODE must be demo or real.')
    required = ('analyze_food', 'calculate_meal_nutrition', 'save_meal', 'get_meal',
                'get_meals', 'delete_meal', 'get_daily_summary')
    for name in required:
        function = dependencies.get(name) if isinstance(dependencies, dict) else getattr(dependencies, name, None)
        if not callable(function):
            raise ValueError(f'Missing backend dependency: {name}')
    app.extensions['meal_dependencies'] = dependencies


def dependency(name):
    backend = current_backend()
    return backend[name] if isinstance(backend, dict) else getattr(backend, name)
