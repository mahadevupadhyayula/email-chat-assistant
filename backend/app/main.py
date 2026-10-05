import logging

from fastapi import FastAPI

from app.api import health
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    app = FastAPI(title="Email Assistant Chat API")
    app.state.settings = settings
    app.include_router(health.router)
    return app


app = create_app()
