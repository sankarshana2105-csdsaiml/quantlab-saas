"""Generate the deterministic sample data, report, and chart used in SAMPLE_BACKTEST.md."""

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from quantlab import moving_average_crossover, run_backtest

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def synthetic_ohlcv(seed: int = 7, periods: int = 756) -> pd.DataFrame:
    """Create three years of plausible daily bars with changing market regimes."""
    rng = np.random.default_rng(seed)
    thirds = np.array_split(np.arange(periods), 3)
    drift = np.empty(periods)
    drift[thirds[0]], drift[thirds[1]], drift[thirds[2]] = 0.0007, -0.00025, 0.00045
    close = 100 * np.exp(np.cumsum(drift + rng.normal(0, 0.012, periods)))
    previous = np.r_[close[0], close[:-1]]
    open_ = previous * np.exp(rng.normal(0, 0.002, periods))
    spread = rng.uniform(0.001, 0.012, periods)
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.lognormal(mean=np.log(1_000_000), sigma=0.25, size=periods).round()
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=pd.bdate_range("2023-01-02", periods=periods, tz="UTC", name="timestamp"),
    )


def main() -> None:
    data = synthetic_ohlcv()
    signal = moving_average_crossover(data, fast_window=20, slow_window=80)
    result = run_backtest(data, signal, transaction_cost_bps=5, slippage_bps=2)

    data_dir, results_dir = ROOT / "data", ROOT / "results"
    data_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)
    data.to_csv(data_dir / "sample_ohlcv.csv")
    (results_dir / "sample_metrics.json").write_text(
        json.dumps(result.metrics, indent=2, allow_nan=False), encoding="utf-8"
    )

    frame = result.frame
    fast = frame["close"].rolling(20).mean()
    slow = frame["close"].rolling(80).mean()
    buy_hold = 10_000 * frame["close"] / frame["close"].iloc[0]
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    axes[0].plot(frame.index, frame["close"], label="Close", linewidth=1)
    axes[0].plot(frame.index, fast, label="20-day MA", linewidth=1)
    axes[0].plot(frame.index, slow, label="80-day MA", linewidth=1)
    axes[0].set_ylabel("Synthetic price")
    axes[0].legend(loc="upper left")
    axes[1].plot(frame.index, frame["equity"], label="Strategy")
    axes[1].plot(frame.index, buy_hold, label="Buy & hold", alpha=0.7)
    axes[1].set_ylabel("Equity ($)")
    axes[1].legend(loc="upper left")
    axes[2].fill_between(frame.index, frame["drawdown"] * 100, 0, color="#c44e52")
    axes[2].set_ylabel("Drawdown (%)")
    axes[2].set_xlabel("Date")
    fig.suptitle("QuantLab sample: 20/80 moving-average crossover")
    fig.tight_layout()
    fig.savefig(results_dir / "sample_backtest.png", dpi=150)
    plt.close(fig)
    print(json.dumps(result.metrics, indent=2))


if __name__ == "__main__":
    main()
