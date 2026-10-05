from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


async def test_health_reports_database_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_degraded_when_db_unreachable() -> None:
    app = create_app(
        Settings(
            app_env="test", database_url="postgresql+asyncpg://app:app@localhost:1/email_assistant"
        )
    )
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "unreachable"}
