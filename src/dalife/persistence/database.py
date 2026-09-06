from __future__ import annotations

import sqlite3
from pathlib import Path

from dalife.persistence.schema import SCHEMA
from dalife.persistence.search_index import migrate_db


class SqliteDatabase:
    """Own the database path, connections, schema initialization, and migration."""

    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "dalife.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            migrate_db(conn)


class RepositoryBase:
    def __init__(self, database: SqliteDatabase) -> None:
        self.database = database

    def connect(self) -> sqlite3.Connection:
        return self.database.connect()

    def init_db(self) -> None:
        self.database.init_db()

