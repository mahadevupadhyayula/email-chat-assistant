import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

PROBE_TIMEOUT_SECONDS = 3.0


async def check_database(session: AsyncSession) -> bool:
    try:
        # TimeoutError is an OSError, so a stalled probe is reported as unreachable.
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        # Leave the session usable so get_db's commit doesn't hit PendingRollbackError.
        await session.rollback()
        return False
    return True
