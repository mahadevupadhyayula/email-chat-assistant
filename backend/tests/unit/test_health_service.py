import asyncio
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import health


class StalledSession:
    rolled_back = False

    async def rollback(self) -> None:
        self.rolled_back = True

    async def execute(self, *args: object, **kwargs: object) -> None:
        await asyncio.sleep(10)


async def test_check_database_false_when_probe_stalls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "PROBE_TIMEOUT_SECONDS", 0.05)
    session = StalledSession()
    assert await health.check_database(cast(AsyncSession, cast(Any, session))) is False
    assert session.rolled_back
