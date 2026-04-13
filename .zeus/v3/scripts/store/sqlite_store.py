"""
SQLite-backed async state store.
"""
from __future__ import annotations

from db.engine import make_async_engine, get_async_session
from store.sqlalchemy_base import _SqlAlchemyStateStore


class SQLiteStateStore(_SqlAlchemyStateStore):
    """Async state store backed by SQLite (via aiosqlite)."""

    def __init__(self, database_url: str | None = None) -> None:
        if database_url is None:
            database_url = "sqlite+aiosqlite:///./zeus_open_v3.sqlite"
        engine = make_async_engine(database_url)
        session_factory = get_async_session(engine)
        super().__init__(session_factory)
        self._engine = engine

    async def close(self) -> None:
        await self._engine.dispose()
