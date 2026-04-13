"""
Async database engine and session factory for ZeusOpen v3.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


def make_async_engine(database_url: str | None = None):
    """Create an async SQLAlchemy engine.

    Supports:
      - sqlite+aiosqlite:///path/to/db.sqlite
      - postgresql+asyncpg://user:pass@host/dbname
    """
    if database_url is None:
        database_url = "sqlite+aiosqlite:///./zeus_open_v3.sqlite"
    engine = create_async_engine(database_url, echo=False, future=True)
    return engine


def get_async_session(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
