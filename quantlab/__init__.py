"""QuantLab's public quantitative research API."""

from .backtest import BacktestResult, compare, run_backtest
from .data import clean_ohlcv, load_csv, validate_ohlcv
from .evaluation import WalkForwardResult, train_test_evaluate, walk_forward_evaluate
from .strategies import moving_average_crossover

__all__ = [
    "BacktestResult",
    "WalkForwardResult",
    "clean_ohlcv",
    "compare",
    "load_csv",
    "moving_average_crossover",
    "run_backtest",
    "train_test_evaluate",
    "validate_ohlcv",
    "walk_forward_evaluate",
]
