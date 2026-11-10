"""Shared Flask extension instances.

``db`` is defined here (not in ``app/__init__.py``) so that models and the
repository can import it without a circular import.
"""

from __future__ import annotations

import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Turn on ``PRAGMA foreign_keys`` for every SQLite connection.

    SQLite ships with foreign-key enforcement disabled.  Without this hook
    ``ON DELETE CASCADE`` / ``ON DELETE SET NULL`` are just comments in the
    schema (see D2 in the test suite).
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
