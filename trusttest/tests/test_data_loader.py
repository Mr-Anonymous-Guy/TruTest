"""
tests/test_data_loader.py – Offline test for core/data_loader.py

Uses the cached CSVs only (no network required).
Run with:  python -m pytest trusttest/tests/test_data_loader.py -v
"""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

# Allow running from repo root
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from trusttest.core.data_loader import _cache_path, _load_from_csv, _validate, load_prices


CACHE_DIR = ROOT / "trusttest" / "data" / "cache"

# Tickers that should have cache files after build_cache.py
CACHED_TICKERS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "NSEI", "AAPL"]


class TestCacheOffline:
    """Tests that work purely from the CSV cache (network=off)."""

    @pytest.mark.parametrize("ticker", ["RELIANCE.NS", "TCS.NS", "AAPL"])
    def test_cache_file_exists(self, ticker):
        path = _cache_path(ticker)
        assert path.exists(), f"Cache missing for {ticker}. Run build_cache.py first."

    @pytest.mark.parametrize("ticker", ["RELIANCE.NS", "TCS.NS", "AAPL"])
    def test_cache_loads_as_dataframe(self, ticker):
        path = _cache_path(ticker)
        if not path.exists():
            pytest.skip(f"No cache for {ticker}")
        df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
        assert not df.empty
        assert "Close" in df.columns

    @pytest.mark.parametrize("ticker", ["RELIANCE.NS", "TCS.NS", "AAPL"])
    def test_cache_has_enough_rows(self, ticker):
        path = _cache_path(ticker)
        if not path.exists():
            pytest.skip(f"No cache for {ticker}")
        df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
        # Should have several years of data
        assert len(df) >= 1000, f"{ticker} only has {len(df)} rows"

    @pytest.mark.parametrize("ticker", ["RELIANCE.NS", "TCS.NS", "AAPL"])
    def test_cache_no_large_gaps(self, ticker):
        path = _cache_path(ticker)
        if not path.exists():
            pytest.skip(f"No cache for {ticker}")
        df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
        nan_rate = df["Close"].isna().mean()
        assert nan_rate < 0.03, f"{ticker} has {nan_rate:.1%} NaN Close values"

    def test_load_from_csv_slices_dates(self):
        """load_prices in cache mode should respect date slicing."""
        ticker = "AAPL"
        path = _cache_path(ticker)
        if not path.exists():
            pytest.skip("No AAPL cache")
        df = _load_from_csv(ticker, "2020-01-01", "2021-12-31")
        assert not df.empty
        assert df.index.min() >= pd.Timestamp("2020-01-01")
        assert df.index.max() <= pd.Timestamp("2022-01-01")  # small buffer for weekends

    def test_missing_ticker_raises(self):
        with pytest.raises(FileNotFoundError):
            _load_from_csv("FAKE_TICKER_XYZ", "2020-01-01", "2023-01-01")
