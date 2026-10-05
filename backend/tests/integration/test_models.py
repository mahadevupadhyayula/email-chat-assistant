from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OAuthCredential, Session
from tests.conftest import UserFactory


def _credential(user_id: object) -> OAuthCredential:
    return OAuthCredential(
        user_id=user_id, provider="google", encrypted_refresh_token="x", scopes=["openid"]
    )


async def test_user_email_unique(db_session: AsyncSession, user_factory: UserFactory) -> None:
    await user_factory(email="a@example.com")
    with pytest.raises(IntegrityError):
        await user_factory(email="a@example.com")


async def test_credential_unique_per_provider(
    db_session: AsyncSession, user_factory: UserFactory
) -> None:
    user = await user_factory()
    db_session.add_all([_credential(user.id), _credential(user.id)])
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_deleting_user_cascades(db_session: AsyncSession, user_factory: UserFactory) -> None:
    user = await user_factory()
    db_session.add_all(
        [
            _credential(user.id),
            Session(
                user_id=user.id,
                token_hash="h" * 64,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            ),
        ]
    )
    await db_session.commit()

    await db_session.delete(user)
    await db_session.commit()

    for model in (Session, OAuthCredential):
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0
