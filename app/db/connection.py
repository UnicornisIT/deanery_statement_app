from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PostgreSQLConnection
from psycopg2.extras import RealDictCursor

from app.config import DatabaseConfig


class DatabaseConnection:
    def __init__(self, config: DatabaseConfig):
        self.config = config

    def connect(self) -> PostgreSQLConnection:
        return psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            dbname=self.config.database,
        )

    @contextmanager
    def cursor(self, dictionary: bool = False) -> Iterator:
        connection = self.connect()
        cursor_factory = RealDictCursor if dictionary else None
        cursor = connection.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
