import os
from collections.abc import AsyncIterator

from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.base import Base

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/app.db"

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    try:
        return get_settings().database_url
    except ValidationError:
        return DEFAULT_DATABASE_URL


def create_engine(database_url: str | None = None) -> AsyncEngine:
    resolved_url = database_url or get_database_url()
    engine = create_async_engine(resolved_url, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        if _supports_wal(resolved_url):
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def _supports_wal(database_url: str) -> bool:
    return (
        database_url.startswith("sqlite")
        and ":memory:" not in database_url
        and "mode=memory" not in database_url
    )


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def create_all_for_tests(test_engine: AsyncEngine) -> None:
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
