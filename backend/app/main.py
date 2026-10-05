import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.config import Settings, get_settings
from app.db.session import create_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        try:
            app.state.engine = engine
            app.state.session_factory = create_session_factory(engine)
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Email Assistant Chat API", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    return app


app = create_app()
