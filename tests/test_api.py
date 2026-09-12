from uuid import UUID, uuid4

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from quantlab import load_csv, moving_average_crossover, run_backtest
from quantlab.api import create_app
from quantlab.api.service import QuantService


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-with-at-least-32-characters")
    service = QuantService(database_url="sqlite:///:memory:", initialize_schema=True)
    client = TestClient(create_app(service))
    client.post("/auth/register", json={"email": "api@example.com", "password": "correct-horse-123"})
    token = client.post("/auth/login", json={"email": "api@example.com", "password": "correct-horse-123"}).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, service


def payload_from_frame(frame: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    bars = []
    for timestamp, row in frame.iterrows():
        bars.append({"timestamp": timestamp.isoformat(), **{column: float(row[column]) for column in row.index}})
    return {"bars": bars}


def upload(client: TestClient, frame: pd.DataFrame) -> str:
    response = client.post("/datasets", json=payload_from_frame(frame))
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def run_request(dataset_id: str, fast=20, slow=80) -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "strategy": {
            "name": "moving_average_crossover",
            "parameters": {"fast_window": fast, "slow_window": slow},
        },
        "backtest": {
            "initial_capital": 10_000,
            "transaction_cost_bps": 5,
            "slippage_bps": 2,
            "periods_per_year": 252,
        },
    }


def test_health_strategy_catalog_and_openapi(api):
    client, _ = api
    assert client.get("/health").json() == {"status": "ok"}
    strategies = client.get("/strategies")
    assert strategies.status_code == 200
    assert strategies.json()[0]["name"] == "moving_average_crossover"
    schema = client.get("/openapi.json").json()
    assert schema["info"]["description"]
    assert schema["paths"]["/backtests"]["post"]["summary"] == "Run a backtest"


def test_complete_sample_matches_direct_engine_exactly(api):
    client, _ = api
    data = load_csv("data/sample_ohlcv.csv")
    dataset_id = upload(client, data)
    created = client.post("/backtests", json=run_request(dataset_id))
    assert created.status_code == 201, created.text
    body = created.json()
    backtest_id = body["backtest_id"]

    direct = run_backtest(
        data,
        moving_average_crossover(data, fast_window=20, slow_window=80),
        transaction_cost_bps=5,
        slippage_bps=2,
    )
    assert body["metrics"] == direct.metrics

    metrics = client.get(f"/backtests/{backtest_id}/metrics")
    equity = client.get(f"/backtests/{backtest_id}/equity")
    drawdown = client.get(f"/backtests/{backtest_id}/drawdown")
    trades = client.get(f"/backtests/{backtest_id}/trades")
    assert metrics.status_code == equity.status_code == drawdown.status_code == trades.status_code == 200
    assert metrics.json() == direct.metrics
    assert [point["equity"] for point in equity.json()] == direct.frame["equity"].tolist()
    assert [point["drawdown"] for point in drawdown.json()] == direct.frame["drawdown"].tolist()
    assert [trade["pnl"] for trade in trades.json()] == direct.trades["pnl"].tolist()
    assert len(trades.json()) == direct.metrics["trade_count"] == 4


def test_compare_uses_stored_engine_results(api):
    client, service = api
    data = load_csv("data/sample_ohlcv.csv")
    dataset_id = upload(client, data)
    first = client.post("/backtests", json=run_request(dataset_id, 20, 80)).json()
    second = client.post("/backtests", json=run_request(dataset_id, 10, 40)).json()
    identifiers = [first["backtest_id"], second["backtest_id"]]
    response = client.post("/backtests/compare", json={"backtest_ids": identifiers})
    assert response.status_code == 200
    rows = response.json()["results"]
    assert [row["backtest_id"] for row in rows] == identifiers
    user_id = UUID(client.get("/auth/me").json()["id"])
    for row in rows:
        expected = service.result(UUID(row["backtest_id"]), user_id).result.metrics
        assert row["metrics"] == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"bars": [{"timestamp": "2024-01-01", "open": 1, "high": 1, "low": 1, "close": 1}]},
        {"bars": [{"timestamp": "not-a-date", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]},
        {"bars": [{"timestamp": "2024-01-01", "open": 0, "high": 1, "low": 1, "close": 1, "volume": 1}]},
    ],
)
def test_malformed_ohlcv_returns_422(api, payload):
    response = api[0].post("/datasets", json=payload)
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()


def test_inconsistent_or_duplicate_ohlcv_returns_clean_422(api):
    client, _ = api
    inconsistent = {"bars": [
        {"timestamp": "2024-01-01", "open": 10, "high": 9, "low": 8, "close": 10, "volume": 1}
    ]}
    response = client.post("/datasets", json=inconsistent)
    assert response.status_code == 422
    assert response.json()["detail"] == "High price is inconsistent with the bar"

    duplicate = {"bars": [
        {"timestamp": "2024-01-01", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 1},
        {"timestamp": "2024-01-01", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 1},
    ]}
    response = client.post("/datasets", json=duplicate)
    assert response.status_code == 422
    assert "unique" in response.json()["detail"]


@pytest.mark.parametrize(
    "change",
    [
        {"strategy": {"name": "unknown", "parameters": {}}},
        {"strategy": {"name": "moving_average_crossover", "parameters": {"fast_window": 10, "slow_window": 5}}},
        {"strategy": {"name": "moving_average_crossover", "parameters": {"fast_window": 10, "slow_window": 20, "future_window": 5}}},
        {"backtest": {"initial_capital": 0}},
        {"backtest": {"transaction_cost_bps": -1}},
        {"backtest": {"slippage_bps": 10_000}},
    ],
)
def test_invalid_backtest_requests_return_422(api, change):
    client, _ = api
    dataset_id = upload(client, load_csv("data/sample_ohlcv.csv"))
    request = run_request(dataset_id)
    request.update(change)
    response = client.post("/backtests", json=request)
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()


def test_missing_resources_and_duplicate_comparison_ids(api):
    client, _ = api
    missing = uuid4()
    assert client.get(f"/backtests/{missing}/metrics").status_code == 404
    response = client.post("/backtests", json=run_request(str(missing)))
    assert response.status_code == 404

    dataset_id = upload(client, load_csv("data/sample_ohlcv.csv"))
    backtest_id = client.post("/backtests", json=run_request(dataset_id)).json()["backtest_id"]
    response = client.post("/backtests/compare", json={"backtest_ids": [backtest_id, backtest_id]})
    assert response.status_code == 422


def test_internal_errors_do_not_expose_tracebacks(api):
    _, service = api
    service.result = lambda *_: 1 / 0  # type: ignore[method-assign]
    client = TestClient(create_app(service), raise_server_exceptions=False)
    client.headers.update({"Authorization": api[0].headers["Authorization"]})
    response = client.get(f"/backtests/{uuid4()}/metrics")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
