"""Context-local dependencies, bound only by the Flask application boundary."""
from contextvars import ContextVar

_runtime = ContextVar('meal_backend_runtime')


def bind_runtime(config, dependencies):
    return _runtime.set((config, dependencies))


def reset_runtime(token):
    _runtime.reset(token)


def settings():
    return _runtime.get()[0]


def backend():
    return _runtime.get()[1]
