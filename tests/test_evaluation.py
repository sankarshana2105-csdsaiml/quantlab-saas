import numpy as np
import pandas as pd

from quantlab.evaluation import train_test_evaluate, walk_forward_evaluate
from quantlab.strategies import moving_average_crossover


def bars(count=30):
    close = np.linspace(100, 130, count)
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1.0},
        index=pd.bdate_range("2024-01-01", periods=count, tz="UTC"),
    )


def test_train_test_split_is_chronological_and_disjoint():
    result = train_test_evaluate(
        bars(), moving_average_crossover, strategy_params={"fast_window": 2, "slow_window": 3}
    )
    assert result["train"].frame.index.max() < result["test"].frame.index.min()


def test_walk_forward_uses_only_earlier_training_rows():
    result = walk_forward_evaluate(
        bars(),
        moving_average_crossover,
        [{"fast_window": 2, "slow_window": 3}, {"fast_window": 3, "slow_window": 5}],
        train_size=10,
        test_size=5,
    )
    assert len(result.folds) == 4
    assert (result.folds["train_start"] < result.folds["test_start"]).all()
    assert result.oos.frame.index.equals(bars().index[10:])


def test_moving_average_signal_has_warmup_and_is_causal():
    data = bars(8)
    original = moving_average_crossover(data, fast_window=2, slow_window=3)
    changed = data.copy()
    changed.iloc[-1, changed.columns.get_loc("close")] = 1_000
    revised = moving_average_crossover(changed, fast_window=2, slow_window=3)
    assert original.iloc[:2].eq(0).all()
    pd.testing.assert_series_equal(original.iloc[:-1], revised.iloc[:-1])
