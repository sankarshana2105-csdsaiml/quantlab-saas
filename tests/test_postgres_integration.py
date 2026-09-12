import os
from urllib.parse import urlparse

import pytest
from pandas.testing import assert_frame_equal
from alembic import command
from alembic.config import Config

from quantlab import load_csv, moving_average_crossover, run_backtest
from quantlab.api.models import BacktestParameters, OHLCVBar, StrategyConfig
from quantlab.api.service import QuantService
from quantlab.auth import AuthService, DuplicateEmail


POSTGRES_URL = os.getenv("QUANTLAB_POSTGRES_TEST_URL")


@pytest.mark.skipif(not POSTGRES_URL, reason="QUANTLAB_POSTGRES_TEST_URL is not configured")
def test_real_postgres_migration_restart_and_round_trip():
    assert POSTGRES_URL is not None
    assert urlparse(POSTGRES_URL.replace("postgresql+psycopg://", "postgresql://")).path == "/quantlab_test"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", POSTGRES_URL.replace("%", "%%"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    service = QuantService(database_url=POSTGRES_URL)
    auth = AuthService(service.repository)
    user = auth.register("postgres@example.com", "correct-horse-123")
    with pytest.raises(DuplicateEmail):
        auth.register("postgres@example.com", "correct-horse-123")
    data = load_csv("data/sample_ohlcv.csv")
    bars = [OHLCVBar(timestamp=timestamp, **row.to_dict()) for timestamp, row in data.iterrows()]
    dataset_id, _ = service.upload_dataset(bars, user.id)
    backtest_id, _ = service.run(
        dataset_id,
        StrategyConfig(name="moving_average_crossover", parameters={"fast_window": 20, "slow_window": 80}),
        BacktestParameters(transaction_cost_bps=5, slippage_bps=2),
        user.id,
    )
    restarted = QuantService(database_url=POSTGRES_URL)
    stored = restarted.result(backtest_id, user.id)
    direct = run_backtest(data, moving_average_crossover(data, fast_window=20, slow_window=80), transaction_cost_bps=5, slippage_bps=2)
    assert stored.result.metrics == direct.metrics
    assert_frame_equal(stored.result.frame, direct.frame[["equity", "drawdown"]], check_dtype=False, rtol=0, atol=0)
    assert_frame_equal(stored.result.trades, direct.trades, check_dtype=False, rtol=0, atol=0)
    restarted.delete_backtest(backtest_id, user.id)
    assert restarted.list_backtests(user.id) == []
