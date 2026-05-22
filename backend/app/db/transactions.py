from sqlalchemy.ext.asyncio import AsyncSession


async def begin_write_transaction(_db: AsyncSession) -> None:
    return None
