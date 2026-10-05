from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


def _diff(connection: Connection) -> list[object]:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return list(compare_metadata(context, Base.metadata))


async def test_no_pending_model_changes(db_session: AsyncSession) -> None:
    connection = await db_session.connection()
    diff: list[object] = await connection.run_sync(_diff)
    assert diff == []
