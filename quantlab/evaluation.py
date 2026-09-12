from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import BacktestResult, _metrics, run_backtest

Strategy = Callable[..., pd.Series]


@dataclass(frozen=True)
class WalkForwardResult:
    folds: pd.DataFrame
    oos: BacktestResult


def _causal_signals(
    data: pd.DataFrame, strategy: Strategy, params: Mapping[str, object]
) -> pd.Series:
    """Call a strategy only with observations available at each decision close."""
    values: list[float] = []
    warmup = 0
    for stop in range(1, len(data) + 1):
        prefix = data.iloc[:stop]
        produced = strategy(prefix, **params)
        if not isinstance(produced, pd.Series) or prefix.index[-1] not in produced.index:
            raise ValueError("Strategy must return a Series containing the current timestamp")
        values.append(produced.loc[prefix.index[-1]])
        warmup = max(warmup, int(produced.attrs.get("warmup_periods", 0)))
    signal = pd.Series(values, index=data.index, name="signal", dtype=float)
    signal.attrs["warmup_periods"] = warmup
    return signal


def _window_result(
    full: BacktestResult,
    index: pd.Index,
    *,
    baseline_time: pd.Timestamp,
    periods_per_year: int,
) -> BacktestResult:
    frame = full.frame.loc[index].copy()
    trades = full.trades[full.trades["exit_time"].isin(index)].copy()
    elapsed_years = (frame.index[-1] - baseline_time).total_seconds() / (365.2425 * 86_400)
    metrics = _metrics(
        frame["strategy_return"], frame["turnover"], periods_per_year,
        trades=trades, positions=frame["position"], elapsed_years=elapsed_years,
    )
    return BacktestResult(frame=frame, metrics=metrics, trades=trades)


def train_test_evaluate(
    data: pd.DataFrame,
    strategy: Strategy,
    *,
    train_fraction: float = 0.7,
    strategy_params: Mapping[str, object] | None = None,
    backtest_params: Mapping[str, object] | None = None,
) -> dict[str, BacktestResult]:
    """Run causal chronological train and fresh-cash test evaluations."""
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    split = int(len(data) * train_fraction)
    if split < 2 or len(data) - split < 2:
        raise ValueError("Train and test sets must each contain at least two rows")
    strategy_params = strategy_params or {}
    backtest_params = backtest_params or {}
    signals = _causal_signals(data, strategy, strategy_params)
    train = run_backtest(data.iloc[:split], signals.iloc[:split], **backtest_params)

    context_data = data.iloc[split - 1:]
    context_signal = signals.iloc[split - 1:]
    test_full = run_backtest(context_data, context_signal, **backtest_params)
    test = _window_result(
        test_full, data.index[split:], baseline_time=data.index[split - 1],
        periods_per_year=int(backtest_params.get("periods_per_year", 252)),
    )
    return {"train": train, "test": test}


def walk_forward_evaluate(
    data: pd.DataFrame,
    strategy: Strategy,
    parameter_grid: Iterable[Mapping[str, object]],
    *,
    train_size: int,
    test_size: int,
    score: str = "sharpe_ratio",
    backtest_params: Mapping[str, object] | None = None,
) -> WalkForwardResult:
    """Select on rolling training windows and execute one continuous OOS account."""
    if train_size < 2 or test_size < 1:
        raise ValueError("train_size must be at least two and test_size positive")
    if len(data) <= train_size:
        raise ValueError("No out-of-sample rows are available")
    candidates = list(parameter_grid)
    if not candidates:
        raise ValueError("parameter_grid must not be empty")
    maximize = {"total_return", "annualized_return", "cagr", "sharpe_ratio", "sortino_ratio", "maximum_drawdown"}
    minimize = {"volatility", "turnover"}
    if score not in maximize | minimize:
        raise ValueError(f"Unsupported optimization score: {score}")
    backtest_params = backtest_params or {}
    periods_per_year = int(backtest_params.get("periods_per_year", 252))
    decisions = pd.Series(np.nan, index=data.index[train_size - 1:], dtype=float, name="signal")
    fold_rows: list[dict[str, object]] = []

    for start in range(0, len(data) - train_size, test_size):
        train_end = start + train_size
        test_end = min(train_end + test_size, len(data))
        train = data.iloc[start:train_end]
        scored: list[tuple[float, Mapping[str, object]]] = []
        for params in candidates:
            train_signal = _causal_signals(train, strategy, params)
            result = run_backtest(train, train_signal, **backtest_params)
            value = float(result.metrics[score])
            if not np.isnan(value):
                scored.append((value, params))
        if not scored:
            raise ValueError(f"No candidate has a defined {score} on the training window")
        choose = max if score in maximize else min
        train_score, best_params = choose(scored, key=lambda item: item[0])

        for decision in range(train_end - 1, test_end):
            history = data.iloc[start:decision + 1]
            produced = strategy(history, **best_params)
            if not isinstance(produced, pd.Series) or history.index[-1] not in produced.index:
                raise ValueError("Strategy must return a Series containing the current timestamp")
            decisions.loc[history.index[-1]] = produced.loc[history.index[-1]]
        fold_rows.append({
            "train_start": train.index[0], "test_start": data.index[train_end],
            "test_end": data.index[test_end - 1], "parameters": dict(best_params),
            "train_score": train_score,
        })

    decisions = decisions.ffill().fillna(0.0)
    execution_data = data.iloc[train_size - 1:]
    full = run_backtest(execution_data, decisions, **backtest_params)
    oos = _window_result(
        full, data.index[train_size:], baseline_time=data.index[train_size - 1],
        periods_per_year=periods_per_year,
    )
    folds = pd.DataFrame(fold_rows)
    for row_number, row in folds.iterrows():
        index = data.loc[row["test_start"]:row["test_end"]].index
        fold = _window_result(
            full, index, baseline_time=data.index[data.index.get_loc(index[0]) - 1],
            periods_per_year=periods_per_year,
        )
        folds.loc[row_number, "test_score"] = fold.metrics[score]
        folds.loc[row_number, "test_total_return"] = fold.metrics["total_return"]
    return WalkForwardResult(folds=folds, oos=oos)
