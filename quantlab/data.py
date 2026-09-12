from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype


REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
PRICE_COLUMNS = ("open", "high", "low", "close")


def clean_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize OHLCV rows, dropping values that cannot represent a market bar."""
    frame = data.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    frame = frame.loc[:, REQUIRED_COLUMNS]
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce", format="mixed")
    for column in (*PRICE_COLUMNS, "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna().sort_values("timestamp")
    duplicate_times = frame["timestamp"].duplicated(keep=False)
    if duplicate_times.any():
        conflicting = frame.loc[duplicate_times].groupby("timestamp", sort=False).nunique(dropna=False)
        if (conflicting > 1).any(axis=None):
            raise ValueError("Conflicting duplicate OHLCV timestamps require explicit correction")
        frame = frame.drop_duplicates("timestamp")
    valid = (frame[list(PRICE_COLUMNS)] > 0).all(axis=1) & (frame["volume"] >= 0)
    valid &= frame["high"] >= frame[list(PRICE_COLUMNS)].max(axis=1)
    valid &= frame["low"] <= frame[list(PRICE_COLUMNS)].min(axis=1)
    return frame.loc[valid].set_index("timestamp")


def validate_ohlcv(data: pd.DataFrame) -> None:
    """Raise ValueError unless data is clean, chronological OHLCV data."""
    if data.empty:
        raise ValueError("OHLCV data is empty")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("OHLCV data must use a DatetimeIndex")
    if data.index.hasnans:
        raise ValueError("OHLCV timestamps must not contain NaT")
    if data.index.has_duplicates or not data.index.is_monotonic_increasing:
        raise ValueError("OHLCV timestamps must be unique and increasing")
    missing = set(REQUIRED_COLUMNS[1:]) - set(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    numeric = data[list(REQUIRED_COLUMNS[1:])]
    if not all(is_numeric_dtype(numeric[column]) for column in numeric):
        raise ValueError("OHLCV values must be numeric")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("OHLCV data contains missing values")
    if (data[list(PRICE_COLUMNS)] <= 0).any().any() or (data["volume"] < 0).any():
        raise ValueError("Prices must be positive and volume non-negative")
    if (data["high"] < data[list(PRICE_COLUMNS)].max(axis=1)).any():
        raise ValueError("High price is inconsistent with the bar")
    if (data["low"] > data[list(PRICE_COLUMNS)].min(axis=1)).any():
        raise ValueError("Low price is inconsistent with the bar")


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load, clean, and validate an OHLCV CSV file."""
    frame = clean_ohlcv(pd.read_csv(path))
    validate_ohlcv(frame)
    return frame
