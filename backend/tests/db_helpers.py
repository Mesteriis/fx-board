import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base

POSTGRES_TEST_DATABASE_URL = "postgresql+asyncpg://fx_board:fx_board@localhost:15432/fx_board_test"


def get_test_database_url() -> str:
    return os.getenv("TEST_DATABASE_URL", POSTGRES_TEST_DATABASE_URL)


async def reset_database(engine: AsyncEngine, *, create_tables: bool = True) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
        if create_tables:
            await connection.run_sync(Base.metadata.create_all)
