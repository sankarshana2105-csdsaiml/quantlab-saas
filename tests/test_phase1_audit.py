"""Independent regression evidence for the repaired Phase 1 engine."""

import csv
import json
import math
import statistics
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantlab import clean_ohlcv, moving_average_crossover, run_backtest, walk_forward_evaluate
from quantlab.backtest import _metrics
from quantlab.evaluation import train_test_evaluate


ROOT = Path(__file__).resolve().parents[1]


def bars(closes, opens=None):
    close = np.asarray(closes, dtype=float)
    opening = close if opens is None else np.asarray(opens, dtype=float)
    return pd.DataFrame(
        {"open": opening, "high": np.maximum(opening, close),
         "low": np.minimum(opening, close), "close": close, "volume": 100},
        index=pd.bdate_range("2024-01-01", periods=len(close), tz="UTC"),
    )


def fixed(data, side=1):
    return pd.Series(float(side), index=data.index)


def independent_metrics(returns, equity, turnover, trade_pnl, positions, elapsed_years):
    count = len(returns)
    mean = statistics.mean(returns)
    std = statistics.stdev(returns)
    downside = math.sqrt(sum(min(r, 0) ** 2 for r in returns) / count)
    peak, drawdown = equity[0], 0.0
    for value in equity:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    wins = [pnl for pnl in trade_pnl if pnl > 0]
    losses = [pnl for pnl in trade_pnl if pnl < 0]
    return {
        "total_return": equity[-1] / equity[0] - 1,
        "cumulative_return": equity[-1] / equity[0] - 1,
        "annualized_return": (equity[-1] / equity[0]) ** (252 / count) - 1,
        "cagr": (equity[-1] / equity[0]) ** (1 / elapsed_years) - 1,
        "volatility": std * math.sqrt(252),
        "sharpe_ratio": mean / std * math.sqrt(252),
        "sortino_ratio": mean / downside * math.sqrt(252),
        "maximum_drawdown": drawdown,
        "win_rate": sum(pnl > 0 for pnl in trade_pnl) / len(trade_pnl) if trade_pnl else 0,
        "profit_factor": sum(wins) / -sum(losses) if losses else (math.inf if wins else 0),
        "trade_count": len(trade_pnl),
        "exposure": sum(side != 0 for side in positions) / len(positions),
        "turnover": turnover,
    }


def sample_evidence():
    with (ROOT / "data/sample_ohlcv.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    closes = [float(row["close"]) for row in rows]
    signals = [int(i >= 79 and sum(closes[i-19:i+1]) / 20 > sum(closes[i-79:i+1]) / 80)
               for i in range(len(closes))]
    cash, shares, entry_equity = 10_000.0, 0.0, None
    equity, returns, trade_pnl, positions, turnover = [cash], [], [], [], 0.0
    for i in range(1, len(closes)):
        opening = float(rows[i]["open"])
        equity_before_trade = cash + shares * opening
        traded_notional = 0.0
        if signals[i-1] and shares == 0:
            entry_equity = cash
            fill = opening * (1 + 0.0002)
            shares = cash / (fill * (1 + 0.0005))
            traded_notional = shares * opening
            cash = 0.0
        elif not signals[i-1] and shares:
            fill = opening * (1 - 0.0002)
            traded_notional = shares * opening
            cash = shares * fill * (1 - 0.0005)
            trade_pnl.append(cash - entry_equity)
            shares = 0.0
        turnover += traded_notional / equity_before_trade
        value = cash + shares * closes[i]
        returns.append(value / equity[-1] - 1)
        equity.append(value)
        positions.append(int(shares > 0))
    timestamps = pd.to_datetime([row["timestamp"] for row in rows], utc=True)
    years = (timestamps[-1] - timestamps[0]).total_seconds() / (365.2425 * 86_400)
    metrics = independent_metrics(returns, equity, turnover, trade_pnl, positions, years)
    return metrics, trade_pnl, signals, equity


def test_sample_metrics_reproduce_with_independent_scalar_arithmetic():
    saved = json.loads((ROOT / "results/sample_metrics.json").read_text(encoding="utf-8"))
    independently_computed, trade_pnl, signals, equity = sample_evidence()
    assert independently_computed == pytest.approx(saved, abs=1e-12)
    data = pd.read_csv(ROOT / "data/sample_ohlcv.csv", index_col=0, parse_dates=True)
    result = run_backtest(data, moving_average_crossover(data, fast_window=20, slow_window=80),
                          transaction_cost_bps=5, slippage_bps=2)
    assert result.frame.signal.tolist() == signals
    np.testing.assert_allclose(result.frame.equity, equity, rtol=1e-12)
    assert result.trades.pnl.tolist() == pytest.approx(trade_pnl)


def test_entry_does_not_earn_the_gap_before_next_open():
    data = bars([100, 120, 120])
    result = run_backtest(data, fixed(data))
    assert result.metrics["total_return"] == pytest.approx(0)


def test_exit_still_owns_the_gap_until_next_open():
    data = bars([100, 100, 80])
    signal = pd.Series([1, 0, 0], index=data.index)
    result = run_backtest(data, signal)
    assert result.metrics["total_return"] == pytest.approx(-0.2)


def test_unchanged_short_quantity_round_trip_price_has_zero_pnl():
    data = bars([100, 90, 100], opens=[100, 100, 90])
    result = run_backtest(data, fixed(data, -1), initial_capital=100)
    assert result.frame.equity.iloc[-1] == pytest.approx(100)


def test_entry_commission_reserves_cash_before_buying_shares():
    data = bars([100, 110], opens=[100, 100])
    result = run_backtest(data, fixed(data), initial_capital=1000, transaction_cost_bps=100)
    shares = 1000 / (100 * 1.01)
    assert result.frame.equity.iloc[-1] == pytest.approx(shares * 110)


def test_entry_cost_cannot_consume_more_than_available_capital():
    data = bars([100, 400], opens=[100, 100])
    with pytest.raises(ValueError):
        run_backtest(data, fixed(data), transaction_cost_bps=20_000)


def test_short_fill_must_be_solvent_before_same_bar_gain():
    data = bars([100, 1], opens=[100, 100])
    with pytest.raises(ValueError, match="fill"):
        run_backtest(data, fixed(data, -1), slippage_bps=6_000)


def test_one_completed_winning_trade_has_trade_win_rate_one():
    data = bars([100, 100, 110, 99, 108.9, 108.9], opens=[100, 100, 100, 110, 99, 108.9])
    result = run_backtest(data, pd.Series([1, 1, 1, 1, 0, 0], index=data.index))
    assert result.metrics["win_rate"] == pytest.approx(1)


def test_one_completed_winning_trade_has_no_losing_trade_denominator():
    data = bars([100, 100, 110, 99, 108.9, 108.9], opens=[100, 100, 100, 110, 99, 108.9])
    result = run_backtest(data, pd.Series([1, 1, 1, 1, 0, 0], index=data.index))
    assert result.metrics["profit_factor"] == math.inf


def test_future_test_mutation_cannot_change_earlier_test_position():
    def full_sample_mean(frame):
        return (frame.close > frame.close.mean()).astype(float)

    data = bars([100, 101, 102, 103, 104, 105, 106, 107])
    changed = bars([100, 101, 102, 103, 104, 105, 106, 10_000])
    before = train_test_evaluate(data, full_sample_mean, train_fraction=0.5)["test"]
    after = train_test_evaluate(changed, full_sample_mean, train_fraction=0.5)["test"]
    pd.testing.assert_series_equal(before.frame.position.iloc[:-1], after.frame.position.iloc[:-1])


def test_walk_forward_cold_start_pays_entry_cost():
    data = bars([100] * 6)
    folds = walk_forward_evaluate(data, fixed, [{"side": 1}], train_size=4, test_size=2,
                                  backtest_params={"transaction_cost_bps": 100})
    assert folds.folds.iloc[0].test_total_return < 0


def test_walk_forward_parameter_switch_pays_reversal():
    data = bars([100, 110, 120, 130, 120, 110, 110, 110])
    folds = walk_forward_evaluate(data, fixed, [{"side": 1}, {"side": -1}],
                                  train_size=4, test_size=2, score="total_return",
                                  backtest_params={"transaction_cost_bps": 100})
    assert [params["side"] for params in folds.folds.parameters] == [1, -1]
    assert folds.folds.iloc[1].test_total_return < 0


def test_walk_forward_scores_or_explicitly_accounts_for_tail():
    data = bars([100] * 9)
    folds = walk_forward_evaluate(data, fixed, [{"side": 0}], train_size=4, test_size=2)
    assert folds.folds.iloc[-1].test_end == data.index[-1]


def test_walk_forward_rejects_no_evaluable_folds():
    with pytest.raises(ValueError):
        walk_forward_evaluate(bars([100] * 3), fixed, [{"side": 0}], train_size=4, test_size=2)


def test_one_return_does_not_get_infinite_sharpe():
    result = run_backtest(bars([100, 110]), fixed(bars([100, 110])))
    assert math.isnan(result.metrics["sharpe_ratio"])


def test_insufficient_strategy_history_is_reported():
    with pytest.raises(ValueError):
        train_test_evaluate(bars([100] * 10), moving_average_crossover,
                            strategy_params={"fast_window": 20, "slow_window": 80})


def test_cleaned_missing_periods_do_not_silently_get_daily_annualization():
    raw = bars([100, 110, 121]).reset_index(names="timestamp")
    raw.loc[1, "volume"] = np.nan
    cleaned = clean_ohlcv(raw)
    with pytest.raises(ValueError):
        run_backtest(cleaned, fixed(cleaned), periods_per_year=252)


def test_derived_nonfinite_returns_are_rejected():
    data = bars([1e-300, 1e300])
    with np.errstate(all="ignore"), pytest.raises(ValueError):
        run_backtest(data, fixed(data, 0))


def test_volatility_selection_prefers_lower_risk():
    data = bars([100, 110, 99, 108.9, 109, 110])
    folds = walk_forward_evaluate(data, fixed, [{"side": 0}, {"side": 1}],
                                  train_size=4, test_size=2, score="volatility")
    assert folds.folds.iloc[0].parameters["side"] == 0


def test_trade_count_and_exposure_are_available():
    data = bars([100] * 4)
    result = run_backtest(data, pd.Series([1, 0, 0, 0], index=data.index))
    assert result.metrics["trade_count"] == 1
    assert result.metrics["exposure"] == pytest.approx(1 / 3)


def test_reversal_cost_counts_two_sides_at_flat_prices():
    data = bars([100] * 4)
    result = run_backtest(data, pd.Series([1, -1, 0, 0], index=data.index),
                          transaction_cost_bps=5, slippage_bps=2)
    assert result.frame.position.tolist() == [0, 1, -1, 0]
    assert result.frame.traded_notional.iloc[2] > result.frame.traded_notional.iloc[1]
    assert result.frame.commission.sum() == pytest.approx(
        sum(result.frame.traded_notional * 0.0005), rel=3e-4
    )
    assert result.metrics["turnover"] == pytest.approx(result.frame.turnover.sum())


def test_completed_long_short_trades_reconcile_to_account_equity():
    data = bars([100] * 4)
    result = run_backtest(
        data, pd.Series([1, -1, 0, 0], index=data.index),
        initial_capital=10_000, transaction_cost_bps=5, slippage_bps=2,
    )
    assert result.metrics["trade_count"] == 2
    assert result.trades.pnl.sum() == pytest.approx(result.frame.equity.iloc[-1] - 10_000)
    assert result.metrics["win_rate"] == 0
    assert result.metrics["profit_factor"] == 0


@pytest.mark.parametrize("returns, sharpe, sortino", [
    ([0, 0, 0], 0, 0),
    ([0.01, 0.01, 0.01], math.inf, math.inf),
    ([-0.01, -0.01, -0.01], -math.inf, -math.sqrt(252)),
])
def test_defined_constant_return_ratio_conventions(returns, sharpe, sortino):
    metrics = _metrics(pd.Series(returns), pd.Series([0] * len(returns)), 252)
    assert metrics["sharpe_ratio"] == pytest.approx(sharpe)
    assert metrics["sortino_ratio"] == pytest.approx(sortino)
    assert metrics["profit_factor"] == 0


def test_bankruptcy_is_explicitly_rejected_instead_of_compounding_negative_equity():
    data = bars([100, 200], opens=[100, 100])
    with pytest.raises(ValueError, match="exhausts capital"):
        run_backtest(data, fixed(data, -1))


def test_nan_signal_is_rejected():
    data = bars([100, 101])
    with pytest.raises(ValueError, match="Signal"):
        run_backtest(data, pd.Series([np.nan, 1], index=data.index))


def test_builtin_strategy_is_prefix_invariant_at_every_timestamp():
    data = bars([100, 120, 90, 100, 115, 85, 110, 95])
    full = moving_average_crossover(data, fast_window=2, slow_window=3)
    for stop in range(1, len(data) + 1):
        prefix = moving_average_crossover(data.iloc[:stop], fast_window=2, slow_window=3)
        pd.testing.assert_series_equal(full.iloc[:stop], prefix)


def test_complete_walk_forward_test_windows_are_adjacent_and_disjoint():
    data = bars([100] * 10)
    folds = walk_forward_evaluate(data, fixed, [{"side": 0}], train_size=4, test_size=2)
    scored_dates = []
    for row in folds.folds.itertuples():
        scored_dates.extend(data.loc[row.test_start:row.test_end].index)
    assert scored_dates == list(data.index[4:])
    assert len(set(scored_dates)) == len(scored_dates)


if __name__ == "__main__":
    metrics, trades, _, _ = sample_evidence()
    print(json.dumps({"independent_next_open_ledger": metrics, "closed_trade_pnl": trades}, indent=2))
