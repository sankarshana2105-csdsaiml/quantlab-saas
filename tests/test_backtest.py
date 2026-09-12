import numpy as np
import pandas as pd
import pytest

from quantlab.backtest import run_backtest


def bars(closes, opens=None):
    closes = np.asarray(closes, dtype=float)
    opens = closes if opens is None else np.asarray(opens, dtype=float)
    return pd.DataFrame(
        {
            "open": opens,
            "high": np.maximum(opens, closes),
            "low": np.minimum(opens, closes),
            "close": closes,
            "volume": np.ones(len(closes)),
        },
        index=pd.bdate_range("2024-01-01", periods=len(closes), tz="UTC"),
    )


def test_signal_is_delayed_one_bar_to_prevent_lookahead():
    data = bars([100, 200, 100])
    signal = pd.Series([1.0, 0.0, 0.0], index=data.index)
    result = run_backtest(data, signal)
    assert result.frame["position"].tolist() == [0.0, 1.0, 0.0]
    assert result.frame["strategy_return"].tolist() == [0.0, 0.0, -0.5]


def test_cost_and_slippage_apply_to_each_unit_of_turnover():
    data = bars([100, 100, 100, 100])
    signal = pd.Series([1.0, 1.0, 0.0, 0.0], index=data.index)
    result = run_backtest(data, signal, transaction_cost_bps=10, slippage_bps=5)
    entry = result.frame.iloc[1]
    exit_ = result.frame.iloc[3]
    assert entry["commission"] == pytest.approx(abs(entry["shares"]) * 100.05 * 0.001)
    assert entry["slippage"] == pytest.approx(abs(entry["shares"]) * 0.05)
    assert exit_["commission"] > 0
    assert result.metrics["turnover"] == pytest.approx(result.frame["turnover"].sum())


def test_compounded_return_drawdown_and_profit_metrics():
    data = bars([100, 110, 99, 108.9, 108.9], opens=[100, 100, 110, 99, 108.9])
    signal = pd.Series([1, 1, 1, 0, 0], index=data.index, dtype=float)
    result = run_backtest(data, signal)
    assert result.metrics["total_return"] == pytest.approx(0.089)
    assert result.metrics["maximum_drawdown"] == pytest.approx(-0.1)
    assert result.metrics["win_rate"] == 1
    assert result.metrics["profit_factor"] == float("inf")
    assert result.metrics["trade_count"] == 1


def test_annualized_volatility_sharpe_and_sortino_formulas():
    data = bars([100, 101, 99.99, 100.9899], opens=[100, 100, 101, 99.99])
    signal = pd.Series(1.0, index=data.index)
    metrics = run_backtest(data, signal, periods_per_year=3).metrics
    returns = np.array([0.01, -0.01, 0.01])
    assert metrics["annualized_return"] == pytest.approx(np.prod(1 + returns) - 1)
    assert metrics["volatility"] == pytest.approx(returns.std(ddof=1) * np.sqrt(3))
    assert metrics["sharpe_ratio"] == pytest.approx(returns.mean() / returns.std(ddof=1) * np.sqrt(3))
    downside = np.sqrt(np.mean(np.minimum(returns, 0) ** 2))
    assert metrics["sortino_ratio"] == pytest.approx(returns.mean() / downside * np.sqrt(3))


def test_invalid_unaligned_signal_is_rejected():
    data = bars([100, 101])
    with pytest.raises(ValueError, match="align"):
        run_backtest(data, pd.Series([1.0]))


def test_constant_prices_and_zero_trades_have_finite_zero_metrics():
    data = bars([100, 100, 100, 100])
    signal = pd.Series(0.0, index=data.index)
    metrics = run_backtest(data, signal).metrics
    assert metrics["total_return"] == 0
    assert metrics["volatility"] == 0
    assert metrics["sharpe_ratio"] == 0
    assert metrics["sortino_ratio"] == 0
    assert metrics["profit_factor"] == 0
    assert metrics["win_rate"] == 0
    assert metrics["turnover"] == 0


def test_zero_volatility_positive_returns_do_not_divide_by_zero():
    data = bars([100, 110, 121, 133.1], opens=[100, 100, 110, 121])
    signal = pd.Series(1.0, index=data.index)
    metrics = run_backtest(data, signal).metrics
    assert metrics["volatility"] == pytest.approx(0)
    assert metrics["sharpe_ratio"] == float("inf")
    assert metrics["sortino_ratio"] == float("inf")
    assert metrics["profit_factor"] == 0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"transaction_cost_bps": -1}, "non-negative"),
        ({"slippage_bps": -1}, "non-negative"),
        ({"transaction_cost_bps": float("nan")}, "finite"),
        ({"initial_capital": 0}, "positive"),
    ],
)
def test_invalid_backtest_parameters_are_rejected(kwargs, message):
    data = bars([100, 100])
    with pytest.raises(ValueError, match=message):
        run_backtest(data, pd.Series(0.0, index=data.index), **kwargs)


def test_costs_are_not_charged_without_trades():
    data = bars([100, 100, 100])
    result = run_backtest(
        data, pd.Series(0.0, index=data.index), transaction_cost_bps=9_999, slippage_bps=9_999
    )
    assert result.frame["cost"].sum() == 0
    assert result.metrics["total_return"] == 0


def test_cost_that_exhausts_capital_is_rejected():
    data = bars([100, 100, 100])
    signal = pd.Series([1.0, -1.0, -1.0], index=data.index)
    with pytest.raises(ValueError, match="below 100%"):
        run_backtest(data, signal, transaction_cost_bps=10_000)
