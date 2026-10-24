"""
tests/test_data.py – Data Loader & Validator Unit Tests
"""

import pandas as pd
import pytest

from core.data import DataQualityError, list_available_tickers, load_cached, validate_prices


def test_missing_ticker_lists_available():
    """Missing ticker raises DataQualityError and lists available tickers."""
    with pytest.raises(DataQualityError) as exc_info:
        load_cached("NONEXISTENT_TICKER")
    msg = str(exc_info.value)
    assert "NONEXISTENT_TICKER" in msg
    assert "Available cached tickers:" in msg
    avail = list_available_tickers()
    assert "RELIANCE.NS" in avail or len(avail) > 0


def test_too_short_history_raises():
    """Series with fewer than min_bars raises DataQualityError."""
    dates = pd.bdate_range("2020-01-01", periods=100)
    df = pd.DataFrame({"close": [100.0] * 100}, index=dates)
    with pytest.raises(DataQualityError) as exc_info:
        validate_prices(df, min_bars=500)
    assert "Insufficient price history" in str(exc_info.value)


def test_too_many_nans_raises():
    """More than max_missing_pct NaNs raises DataQualityError."""
    dates = pd.bdate_range("2020-01-01", periods=600)
    prices = [100.0] * 600
    # Set 30 items (5%) to NaN
    for i in range(30):
        prices[i * 20] = float("nan")
    df = pd.DataFrame({"close": prices}, index=dates)

    with pytest.raises(DataQualityError) as exc_info:
        validate_prices(df, min_bars=500, max_missing_pct=3.0)
    assert "Data quality check failed" in str(exc_info.value)


def test_cached_reliance_loads_monotonically():
    """RELIANCE.NS loads with monotonic ascending DatetimeIndex."""
    df = load_cached("RELIANCE.NS")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    assert len(df) >= 500
    assert "close" in df.columns
    assert df.attrs["metadata"]["ticker"] == "RELIANCE.NS"


def test_cached_tcs_loads_monotonically():
    """TCS.NS loads with monotonic ascending DatetimeIndex."""
    df = load_cached("TCS.NS")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    assert len(df) >= 500
    assert "close" in df.columns
