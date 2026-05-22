from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def begin_sqlite_immediate(db: AsyncSession) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        return
    if db.in_transaction():
        raise RuntimeError("BEGIN IMMEDIATE requires no active transaction")
    await db.execute(text("BEGIN IMMEDIATE"))
