from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def test_health_returns_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        response = await c.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
