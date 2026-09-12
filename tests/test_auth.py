from uuid import uuid4

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from quantlab import load_csv
from quantlab.api import create_app
from quantlab.api.service import QuantService
from quantlab.security import verify_password


PASSWORD = "correct-horse-123"


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-with-at-least-32-characters")


@pytest.fixture
def client():
    return TestClient(create_app(QuantService(database_url="sqlite:///:memory:", initialize_schema=True)))


def register(client: TestClient, email: str) -> dict:
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


def token(client: TestClient, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def headers(client: TestClient, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(client, email)}"}


def payload(data: pd.DataFrame) -> dict:
    return {"bars": [
        {"timestamp": timestamp.isoformat(), **{column: float(row[column]) for column in row.index}}
        for timestamp, row in data.iterrows()
    ]}


def create_backtest(client: TestClient, auth: dict[str, str]) -> str:
    dataset = client.post("/datasets", json=payload(load_csv("data/sample_ohlcv.csv")), headers=auth)
    assert dataset.status_code == 201, dataset.text
    response = client.post("/backtests", headers=auth, json={
        "dataset_id": dataset.json()["dataset_id"],
        "strategy": {"name": "moving_average_crossover", "parameters": {"fast_window": 20, "slow_window": 80}},
        "backtest": {"transaction_cost_bps": 5, "slippage_bps": 2},
    })
    assert response.status_code == 201, response.text
    return response.json()["backtest_id"]


def test_registration_hashes_password(client):
    user = register(client, "User@Example.com")
    stored = client.app.state.quant_service.repository.find_user_by_email("user@example.com")
    assert user["email"] == "user@example.com"
    assert "password" not in user and "password_hash" not in user
    assert stored.password_hash != PASSWORD
    assert stored.password_hash.startswith("$argon2")
    assert verify_password(PASSWORD, stored.password_hash)


def test_duplicate_registration_is_case_insensitive(client):
    register(client, "user@example.com")
    response = client.post("/auth/register", json={"email": "USER@example.com", "password": PASSWORD})
    assert response.status_code == 409


def test_login_success_and_failure(client):
    register(client, "user@example.com")
    assert client.post("/auth/login", json={"email": "user@example.com", "password": PASSWORD}).json()["token_type"] == "bearer"
    for email, password in (("user@example.com", "wrong-password"), ("unknown@example.com", PASSWORD)):
        response = client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid email or password"}


def test_protected_endpoints_require_authentication(client):
    assert client.get("/health").status_code == 200
    assert client.post("/datasets", json=payload(load_csv("data/sample_ohlcv.csv"))).status_code == 401
    assert client.get("/backtests").status_code == 401
    assert client.get(f"/backtests/{uuid4()}").status_code == 401
    assert client.delete(f"/backtests/{uuid4()}").status_code == 401


def test_current_user_and_invalid_token(client):
    user = register(client, "user@example.com")
    assert client.get("/auth/me", headers=headers(client, "user@example.com")).json() == user
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_cross_user_access_is_hidden_and_lists_are_scoped(client):
    register(client, "a@example.com")
    register(client, "b@example.com")
    auth_a, auth_b = headers(client, "a@example.com"), headers(client, "b@example.com")
    backtest_a = create_backtest(client, auth_a)
    backtest_b = create_backtest(client, auth_b)
    assert [row["backtest_id"] for row in client.get("/backtests", headers=auth_a).json()] == [backtest_a]
    assert [row["backtest_id"] for row in client.get("/backtests", headers=auth_b).json()] == [backtest_b]
    for suffix in ("", "/metrics", "/equity", "/drawdown", "/trades"):
        assert client.get(f"/backtests/{backtest_b}{suffix}", headers=auth_a).status_code == 404
    assert client.post(
        "/backtests/compare", headers=auth_a,
        json={"backtest_ids": [backtest_a, backtest_b]},
    ).status_code == 404
    assert client.delete(f"/backtests/{backtest_b}", headers=auth_a).status_code == 404
    assert client.get(f"/backtests/{backtest_b}", headers=auth_b).status_code == 200


def test_auth_and_ownership_survive_restart(tmp_path):
    database = f"sqlite:///{(tmp_path / 'auth.db').as_posix()}"
    first = TestClient(create_app(QuantService(database_url=database, initialize_schema=True)))
    user = register(first, "user@example.com")
    auth = headers(first, "user@example.com")
    backtest_id = create_backtest(first, auth)
    second = TestClient(create_app(QuantService(database_url=database, initialize_schema=True)))
    assert second.get("/auth/me", headers=auth).json() == user
    assert second.get(f"/backtests/{backtest_id}", headers=auth).status_code == 200
