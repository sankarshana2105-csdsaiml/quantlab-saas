import pytest
from fastapi.testclient import TestClient

from quantlab.api import create_app
from quantlab.api.service import QuantService
from quantlab.config import ConfigurationError, Settings
from quantlab.database import database_url, normalize_database_url
from quantlab.repository import RepositoryError


def test_provider_postgres_urls_use_psycopg3(monkeypatch):
    assert normalize_database_url("postgres://u:p@db/app") == "postgresql+psycopg://u:p@db/app"
    assert normalize_database_url("postgresql://u:p@db/app") == "postgresql+psycopg://u:p@db/app"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/app")
    assert database_url() == "postgresql+psycopg://u:p@db/app"


def test_production_configuration_requires_postgres_secret_and_cors(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="JWT_SECRET"):
        Settings.from_environment()
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unsafe.db")
    with pytest.raises(ConfigurationError, match="PostgreSQL"):
        Settings.from_environment()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db/quantlab")
    with pytest.raises(ConfigurationError, match="CORS_ORIGINS"):
        Settings.from_environment()
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ConfigurationError, match="explicit"):
        Settings.from_environment()


def test_positive_runtime_limits_are_validated(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "0")
    with pytest.raises(ConfigurationError, match="JWT_EXPIRE_MINUTES"):
        Settings.from_environment()


def test_health_checks_database_and_hides_failure(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    service = QuantService(database_url="sqlite:///:memory:", initialize_schema=True)
    client = TestClient(create_app(service), raise_server_exceptions=False)
    assert client.get("/health").json() == {"status": "ok"}
    service.repository.ping = lambda: (_ for _ in ()).throw(RepositoryError("private DSN"))  # type: ignore[method-assign]
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Persistence service unavailable"}
    assert "private DSN" not in response.text


def test_upload_limit_is_enforced_by_service(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("MAX_DATASET_BARS", "1")
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-with-at-least-32-characters")
    client = TestClient(create_app(QuantService(database_url="sqlite:///:memory:", initialize_schema=True)))
    client.post("/auth/register", json={"email": "limit@example.com", "password": "correct-horse-123"})
    token = client.post("/auth/login", json={"email": "limit@example.com", "password": "correct-horse-123"}).json()["access_token"]
    response = client.post("/datasets", headers={"Authorization": f"Bearer {token}"}, json={"bars": [
        {"timestamp": "2024-01-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
        {"timestamp": "2024-01-02", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
    ]})
    assert response.status_code == 422
    assert "1-bar limit" in response.json()["detail"]
