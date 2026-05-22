import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import create_engine


@pytest.fixture
async def test_session():
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
