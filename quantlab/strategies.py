import pandas as pd


def moving_average_crossover(
    data: pd.DataFrame, *, fast_window: int = 20, slow_window: int = 50
) -> pd.Series:
    """Return a causal long/cash target signal from closing prices."""
    if not 0 < fast_window < slow_window:
        raise ValueError("Windows must satisfy 0 < fast_window < slow_window")
    fast = data["close"].rolling(fast_window, min_periods=fast_window).mean()
    slow = data["close"].rolling(slow_window, min_periods=slow_window).mean()
    signal = (fast > slow).astype(float)
    signal.name = "signal"
    signal.attrs["warmup_periods"] = slow_window - 1
    return signal
