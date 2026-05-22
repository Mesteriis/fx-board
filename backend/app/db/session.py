import os
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base

DEFAULT_DATABASE_URL = "postgresql+asyncpg://fx_board:fx_board@localhost:15432/fx_board"

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    return os.getenv("DATABASE_URL") or _read_dotenv_database_url() or DEFAULT_DATABASE_URL


def _read_dotenv_database_url(dotenv_path: str = ".env") -> str | None:
    path = Path(dotenv_path)
    if not path.is_file():
        return None

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "DATABASE_URL":
            continue
        return _strip_env_value(value)

    return None


def _strip_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def create_engine(database_url: str | None = None) -> AsyncEngine:
    resolved_url = database_url or get_database_url()
    return create_async_engine(resolved_url, future=True)


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
