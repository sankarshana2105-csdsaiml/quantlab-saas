from uuid import uuid4

import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from quantlab import load_csv, moving_average_crossover, run_backtest
from quantlab.api import create_app
from quantlab.api.models import BacktestParameters, OHLCVBar, StrategyConfig
from quantlab.api.service import PersistenceError, QuantService
from quantlab.auth import AuthService
from quantlab.database import create_database
from quantlab.db_models import BacktestModel
from quantlab.repository import RepositoryError, SQLAlchemyRepository


def url(path) -> str:
    return f"sqlite:///{path.as_posix()}"


def bars(data: pd.DataFrame) -> list[OHLCVBar]:
    return [OHLCVBar(timestamp=timestamp, **row.to_dict()) for timestamp, row in data.iterrows()]


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-with-at-least-32-characters")


def authenticated_client(service: QuantService, email: str = "owner@example.com") -> TestClient:
    client = TestClient(create_app(service))
    token = client.post("/auth/login", json={"email": email, "password": "correct-horse-123"}).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def run_sample(service: QuantService, email: str = "owner@example.com"):
    data = load_csv("data/sample_ohlcv.csv")
    user = AuthService(service.repository).register(email, "correct-horse-123")
    dataset_id, _ = service.upload_dataset(bars(data), user.id)
    backtest_id, _ = service.run(
        dataset_id,
        StrategyConfig(name="moving_average_crossover", parameters={"fast_window": 20, "slow_window": 80}),
        BacktestParameters(transaction_cost_bps=5, slippage_bps=2),
        user.id,
    )
    return data, dataset_id, backtest_id, user


def test_save_read_round_trip_and_direct_reconciliation(tmp_path):
    service = QuantService(database_url=url(tmp_path / "roundtrip.db"), initialize_schema=True)
    data, dataset_id, backtest_id, user = run_sample(service)
    stored = service.result(backtest_id, user.id)
    direct = run_backtest(
        data, moving_average_crossover(data, fast_window=20, slow_window=80),
        transaction_cost_bps=5, slippage_bps=2,
    )
    assert stored.dataset_id == dataset_id
    assert stored.result.metrics == direct.metrics
    assert stored.result.frame["equity"].tolist() == direct.frame["equity"].tolist()
    assert stored.result.frame["drawdown"].tolist() == direct.frame["drawdown"].tolist()
    assert stored.result.trades["pnl"].tolist() == direct.trades["pnl"].tolist()
    client = authenticated_client(service)
    assert client.get(f"/backtests/{backtest_id}/metrics").json() == direct.metrics
    assert [row["equity"] for row in client.get(f"/backtests/{backtest_id}/equity").json()] == direct.frame["equity"].tolist()
    assert [row["drawdown"] for row in client.get(f"/backtests/{backtest_id}/drawdown").json()] == direct.frame["drawdown"].tolist()
    assert [row["pnl"] for row in client.get(f"/backtests/{backtest_id}/trades").json()] == direct.trades["pnl"].tolist()


def test_results_survive_recreated_service_and_app(tmp_path):
    database = url(tmp_path / "restart.db")
    first = QuantService(database_url=database, initialize_schema=True)
    _, _, backtest_id, _ = run_sample(first)
    second = QuantService(database_url=database, initialize_schema=True)
    client = authenticated_client(second)
    assert client.get(f"/backtests/{backtest_id}/metrics").status_code == 200
    assert client.get(f"/backtests/{backtest_id}").json()["backtest_id"] == str(backtest_id)
    assert client.get("/backtests").json()[0]["backtest_id"] == str(backtest_id)


def test_database_url_environment_is_used(tmp_path, monkeypatch):
    database = tmp_path / "environment.db"
    monkeypatch.setenv("DATABASE_URL", url(database))
    service = QuantService(initialize_schema=True)
    user = AuthService(service.repository).register("environment@example.com", "correct-horse-123")
    service.upload_dataset(bars(load_csv("data/sample_ohlcv.csv")), user.id)
    assert database.exists()


def test_delete_and_unknown_ids(tmp_path):
    service = QuantService(database_url=url(tmp_path / "delete.db"), initialize_schema=True)
    _, _, backtest_id, _ = run_sample(service)
    client = authenticated_client(service)
    assert client.delete(f"/backtests/{backtest_id}").status_code == 204
    assert client.get(f"/backtests/{backtest_id}/metrics").status_code == 404
    missing = uuid4()
    response = client.delete(f"/backtests/{missing}")
    assert response.status_code == 404


def test_failed_transaction_rolls_back(tmp_path):
    engine, sessions = create_database(url(tmp_path / "rollback.db"), initialize=True)
    repository = SQLAlchemyRepository(sessions)
    service = QuantService(repository)
    data = load_csv("data/sample_ohlcv.csv")
    user = AuthService(repository).register("rollback@example.com", "correct-horse-123")
    dataset_id, _ = service.upload_dataset(bars(data), user.id)

    def fail_flush(*_):
        raise SQLAlchemyError("forced failure")

    event.listen(sessions.class_, "before_flush", fail_flush)
    with pytest.raises(PersistenceError, match="Database operation failed"):
        service.run(
            dataset_id,
            StrategyConfig(name="moving_average_crossover", parameters={"fast_window": 20, "slow_window": 80}),
            BacktestParameters(),
            user.id,
        )
    event.remove(sessions.class_, "before_flush", fail_flush)
    with sessions() as session:
        assert session.scalar(select(BacktestModel.id)) is None
    engine.dispose()


def test_repository_failure_is_clean_api_503(tmp_path):
    service = QuantService(database_url=url(tmp_path / "failure.db"), initialize_schema=True)
    AuthService(service.repository).register("failure@example.com", "correct-horse-123")
    client = authenticated_client(service, "failure@example.com")
    service.repository.get_backtest = lambda *_: (_ for _ in ()).throw(RepositoryError("secret detail"))  # type: ignore[method-assign]
    client = TestClient(create_app(service), raise_server_exceptions=False, headers=dict(client.headers))
    response = client.get(f"/backtests/{uuid4()}/metrics")
    assert response.status_code == 503
    assert response.json() == {"detail": "Persistence service unavailable"}
    assert "secret" not in response.text


def test_invalid_persistence_state_is_clean_api_503(tmp_path):
    database = url(tmp_path / "invalid.db")
    service = QuantService(database_url=database, initialize_schema=True)
    _, _, backtest_id, _ = run_sample(service)
    with service.repository.sessions.begin() as session:
        session.get(BacktestModel, backtest_id).status = "partial"
    response = authenticated_client(QuantService(database_url=database, initialize_schema=True)).get(f"/backtests/{backtest_id}/metrics")
    assert response.status_code == 503
    assert response.json() == {"detail": "Persistence service unavailable"}


def test_alembic_initializes_schema_from_scratch(tmp_path):
    database = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url(database))
    command.upgrade(config, "0001")
    engine, _ = create_database(url(database), initialize=False)
    dataset_id, backtest_id = uuid4().hex, uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO datasets (id,row_count,start_at,end_at,created_at,updated_at) "
            "VALUES (:id,1,:at,:at,:at,:at)"
        ), {"id": dataset_id, "at": "2024-01-01 00:00:00"})
        connection.execute(text(
            "INSERT INTO backtests (id,dataset_id,strategy_name,strategy_parameters,backtest_parameters,status,"
            "result_row_count,result_start_at,result_end_at,created_at,updated_at) "
            "VALUES (:id,:dataset_id,'moving_average_crossover','{}','{}','completed',1,:at,:at,:at,:at)"
        ), {"id": backtest_id, "dataset_id": dataset_id, "at": "2024-01-01 00:00:00"})
    engine.dispose()
    command.upgrade(config, "head")
    command.check(config)
    engine, _ = create_database(url(database), initialize=False)
    assert {
        "alembic_version", "datasets", "dataset_bars", "backtests",
        "performance_metrics", "completed_trades", "backtest_series", "users",
    } <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.execute(text("SELECT owner_id FROM datasets")).scalar_one()
        assert connection.execute(text("SELECT owner_id FROM backtests")).scalar_one()
    engine.dispose()
