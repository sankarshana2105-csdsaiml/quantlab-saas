import pandas as pd
import pytest

from quantlab.data import clean_ohlcv, load_csv, validate_ohlcv


def test_clean_ohlcv_rejects_conflicting_duplicates():
    raw = pd.DataFrame(
        {
            "Timestamp": ["2024-01-02", "2024-01-01", "2024-01-01", "bad"],
            "Open": [10, 9, 10, 1],
            "High": [11, 10, 12, 1],
            "Low": [9, 8, 9, 1],
            "Close": [10, 9, 11, 1],
            "Volume": [100, 100, 110, 1],
        }
    )
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        clean_ohlcv(raw)


def test_validation_rejects_inconsistent_high():
    index = pd.to_datetime(["2024-01-01"], utc=True)
    frame = pd.DataFrame(
        {"open": [10], "high": [9], "low": [8], "close": [10], "volume": [1]},
        index=index,
    )
    with pytest.raises(ValueError, match="High"):
        validate_ohlcv(frame)


def test_load_csv_parses_timestamp_and_numeric_columns(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n2024-01-01,10,11,9,10.5,100\n",
        encoding="utf-8",
    )
    loaded = load_csv(path)
    assert isinstance(loaded.index, pd.DatetimeIndex)
    assert loaded.iloc[0]["close"] == 10.5


@pytest.mark.parametrize("bad_value", [0, -1])
def test_validation_rejects_nonpositive_prices(bad_value):
    index = pd.date_range("2024-01-01", periods=2, tz="UTC")
    frame = pd.DataFrame(
        {"open": [10, bad_value], "high": [10, 10], "low": [10, 1], "close": [10, 5], "volume": 1},
        index=index,
    )
    with pytest.raises(ValueError, match="Prices"):
        validate_ohlcv(frame)


def test_validation_rejects_empty_nan_infinite_and_invalid_timestamps():
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([]))
    with pytest.raises(ValueError, match="empty"):
        validate_ohlcv(empty)

    for bad in [float("nan"), float("inf")]:
        frame = pd.DataFrame(
            {"open": [10], "high": [10], "low": [10], "close": [bad], "volume": [1]},
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        with pytest.raises(ValueError, match="missing"):
            validate_ohlcv(frame)

    frame = pd.DataFrame(
        {"open": [10], "high": [10], "low": [10], "close": [10], "volume": [1]},
        index=pd.DatetimeIndex([pd.NaT]),
    )
    with pytest.raises(ValueError, match="timestamps"):
        validate_ohlcv(frame)


def test_cleaning_removes_bad_timestamps_and_exact_duplicates():
    raw = pd.DataFrame(
        {
            "timestamp": ["bad", "2024-01-01", "2024-01-01"],
            "open": [10, 11, 11],
            "high": [10, 11, 11],
            "low": [10, 11, 11],
            "close": [10, 11, 11],
            "volume": [1, 2, 2],
        }
    )
    clean = clean_ohlcv(raw)
    assert len(clean) == 1
    assert clean.iloc[0]["close"] == 11


def test_validation_rejects_duplicate_rows():
    index = pd.to_datetime(["2024-01-01", "2024-01-01"], utc=True)
    frame = pd.DataFrame(
        {"open": 10, "high": 10, "low": 10, "close": 10, "volume": 1}, index=index
    )
    with pytest.raises(ValueError, match="unique"):
        validate_ohlcv(frame)
