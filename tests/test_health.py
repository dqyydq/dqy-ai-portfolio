from fastapi.testclient import TestClient

from app.main import app
from app.api import health as health_api


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_returns_503_when_dependency_is_down(monkeypatch) -> None:
    async def database_down() -> bool:
        return False

    async def redis_up() -> bool:
        return True

    monkeypatch.setattr(health_api, "check_database", database_down)
    monkeypatch.setattr(health_api, "check_redis", redis_up)
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
