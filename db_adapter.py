"""Small PostgreSQL adapter for the existing SQLite-oriented Flask queries.

Uses psycopg 3 and translates the small set of SQLite-specific SQL constructs
still used by app.py. PostgreSQL remains the production source of truth.
"""
import re

import psycopg
from psycopg.rows import dict_row


class HybridRow(dict):
    """Mapping row that also supports SQLite-style integer indexing."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class CursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        row = self._cursor.fetchone()
        return HybridRow(row) if row is not None else None

    def fetchall(self):
        return [HybridRow(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        for row in self._cursor:
            yield HybridRow(row)


class ConnectionAdapter:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        sql = sql.strip()

        # SQLite schema introspection used by the existing migrations.
        pragma = re.fullmatch(r"PRAGMA\s+table_info\((\w+)\)", sql, re.I)
        if pragma:
            table = pragma.group(1).lower()
            sql = (
                "SELECT column_name AS name "
                "FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = %s "
                "ORDER BY ordinal_position"
            )
            params = (table,)

        # SQLite DDL -> PostgreSQL DDL.
        sql = re.sub(
            r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "BIGSERIAL PRIMARY KEY",
            sql,
            flags=re.I,
        )
        sql = re.sub(r"\bDATETIME\b", "TIMESTAMP", sql, flags=re.I)

        # SQLite convenience functions / syntax.
        sql = re.sub(r"last_insert_rowid\(\)", "lastval()", sql, flags=re.I)
        sql = re.sub(r"\bMAX\s*\(", "GREATEST(", sql, flags=re.I)

        ignored_insert = bool(
            re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", sql, re.I)
        )
        if ignored_insert:
            sql = re.sub(
                r"\bINSERT\s+OR\s+IGNORE\s+INTO\b",
                "INSERT INTO",
                sql,
                flags=re.I,
            )
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

        # The application uses qmark placeholders throughout.
        sql = sql.replace("?", "%s")

        return CursorAdapter(self._connection.execute(sql, params))

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def connect_database(database_url):
    """Open a short-lived serverless-safe PostgreSQL connection."""
    connection = psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=10,
        sslmode="require",
        # Supabase transaction pooler compatibility.
        prepare_threshold=None,
    )
    return ConnectionAdapter(connection)
