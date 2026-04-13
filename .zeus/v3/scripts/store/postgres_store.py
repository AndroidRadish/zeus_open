"""
PostgreSQL-backed async state store.
"""
from __future__ import annotations

from db.engine import make_async_engine, get_async_session
from store.sqlalchemy_base import _SqlAlchemyStateStore


class PostgresStateStore(_SqlAlchemyStateStore):
    """Async state store backed by PostgreSQL (via asyncpg)."""

    def __init__(self, database_url: str | None = None) -> None:
        if database_url is None:
            raise ValueError("PostgresStateStore requires a database_url")
        engine = make_async_engine(database_url)
        session_factory = get_async_session(engine)
        super().__init__(session_factory)
        self._engine = engine

    async def close(self) -> None:
        await self._engine.dispose()
