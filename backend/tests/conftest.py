import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.config import Settings
from app.db.base import Base
from app.db.models import User
from app.main import create_app

UserFactory = Callable[..., Awaitable[User]]


@pytest.fixture(scope="session")
async def migrated_db_url() -> str:
    url = Settings(app_env="test").test_database_url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    await asyncio.to_thread(command.upgrade, cfg, "head")
    return url


@pytest.fixture
async def app(migrated_db_url: str, clean_tables: None) -> AsyncIterator[FastAPI]:
    app = create_app(Settings(app_env="test", database_url=migrated_db_url))
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as session:
        yield session


@pytest.fixture
async def clean_tables(migrated_db_url: str) -> AsyncIterator[None]:
    yield
    from app.db.session import create_engine

    engine = create_engine(migrated_db_url)
    names = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytest.fixture
def user_factory(db_session: AsyncSession) -> UserFactory:
    async def make(email: str = "me@example.com", name: str | None = "Me") -> User:
        user = User(email=email, name=name)
        db_session.add(user)
        await db_session.commit()
        return user

    return make
