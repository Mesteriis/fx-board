import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import DEFAULT_DATABASE_URL, get_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = (
    os.getenv("DATABASE_URL")
    or get_database_url()
    or config.get_main_option("sqlalchemy.url")
    or DEFAULT_DATABASE_URL
)
config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
