"""
tests/test_data_agent.py – Offline Unit Tests for Data Source & Fallback Logic
"""

import pytest
from unittest.mock import patch
from core.data import DataQualityError
from agents.data_source import fetch_prices


def test_live_failure_falls_back_to_cache():
    """When live yfinance fails, it should seamlessly fallback to cache."""
    with patch("yfinance.Ticker", side_effect=Exception("Network timeout")):
        df, source, note = fetch_prices("RELIANCE.NS", enable_live=True)
        assert source == "cache"
        assert "cached" in note.lower()
        assert len(df) > 500
        assert "close" in df.columns


def test_unknown_ticker_friendly_error():
    """Unknown ticker raises DataQualityError listing cached tickers."""
    with pytest.raises(DataQualityError) as exc_info:
        fetch_prices("NONEXISTENT_TICKER_XYZ", enable_live=False)
    err_msg = str(exc_info.value)
    assert "Available cached tickers" in err_msg
    assert "RELIANCE.NS" in err_msg


def test_too_short_slice_errors_cleanly():
    """Querying a date range with fewer than min_bars raises DataQualityError."""
    with pytest.raises(DataQualityError) as exc_info:
        fetch_prices("RELIANCE.NS", start="2026-10-01", end="2026-10-15", enable_live=False)
    assert "Insufficient price history" in str(exc_info.value)
