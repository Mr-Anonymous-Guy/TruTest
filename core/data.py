"""
core/data.py – Pure-Python Data Loader & Validator
==================================================
Reads cached OHLCV CSVs from data/cache/.
No network calls, no uagents dependencies.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


class DataQualityError(Exception):
    """Raised when cached price data is missing or fails quality validation."""
    pass


def _get_cache_dir(cache_dir: str = "data/cache") -> Path:
    """Resolve cache directory relative to current working dir or repo root."""
    p = Path(cache_dir)
    if not p.is_absolute():
        # Check current working dir first, then try trusttest/data/cache
        if not p.exists():
            alt = Path(__file__).resolve().parent.parent / "data" / "cache"
            if alt.exists():
                return alt
            alt2 = Path(__file__).resolve().parent.parent / "trusttest" / "data" / "cache"
            if alt2.exists():
                return alt2
    return p


def list_available_tickers(cache_dir: str = "data/cache") -> List[str]:
    """List all available tickers in the cache directory."""
    cd = _get_cache_dir(cache_dir)
    if not cd.exists():
        return []
    tickers = []
    for f in cd.glob("*.csv"):
        tickers.append(f.stem)
    return sorted(tickers)


def load_cached(ticker: str, cache_dir: str = "data/cache") -> pd.DataFrame:
    """
    Load a cached CSV file for ticker.
    Strips '^' from ticker for index symbols (e.g. ^NSEI -> NSEI.csv).
    Returns a DataFrame with DatetimeIndex (ascending, no duplicates)
    and lowercase float columns: 'open', 'high', 'low', 'close', 'volume'.
    """
    clean_ticker = ticker.replace("^", "")
    filename = f"{clean_ticker}.csv"
    cd = _get_cache_dir(cache_dir)
    filepath = cd / filename

    if not filepath.exists():
        avail = list_available_tickers(cache_dir)
        avail_str = ", ".join(avail) if avail else "none"
        raise DataQualityError(
            f"No cached data file found for ticker '{ticker}' (expected {filepath}). "
            f"Available cached tickers: {avail_str}."
        )

    # Read CSV
    df = pd.read_csv(filepath)

    # Check for Date column
    date_col = None
    for c in df.columns:
        if c.lower() == "date":
            date_col = c
            break

    if date_col is None:
        raise DataQualityError(f"CSV for {ticker} missing 'Date' column.")

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()

    # Drop duplicate dates
    df = df[~df.index.duplicated(keep="first")]

    # Normalize columns to lowercase
    rename_map = {}
    for c in df.columns:
        rename_map[c] = c.lower()
    df = df.rename(columns=rename_map)

    # Ensure 'close' exists
    if "close" not in df.columns:
        raise DataQualityError(f"CSV for {ticker} missing 'Close' price column.")

    # Convert numeric columns to float
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Store metadata on df.attrs
    start_str = str(df.index[0].date()) if len(df) > 0 else ""
    end_str = str(df.index[-1].date()) if len(df) > 0 else ""
    df.attrs["metadata"] = {
        "source": "cache",
        "ticker": ticker,
        "start_date": start_str,
        "end_date": end_str,
        "bar_count": len(df),
    }

    return df


def validate_prices(
    df: pd.DataFrame,
    min_bars: int = 500,
    max_missing_pct: float = 3.0,
) -> pd.DataFrame:
    """
    Validate that df has at least min_bars, and that missing business days
    do not exceed max_missing_pct. Forward-fills small gaps (never back-fills).
    Returns a cleaned copy of df.
    """
    if len(df) < min_bars:
        raise DataQualityError(
            f"Insufficient price history: found {len(df)} bars, need at least {min_bars} bars."
        )

    # Calculate expected business days
    start = df.index[0]
    end = df.index[-1]
    expected_bdays = pd.bdate_range(start, end)
    n_expected = len(expected_bdays)

    if n_expected > 0:
        missing_count = max(0, n_expected - len(df))
        missing_pct = (missing_count / n_expected) * 100.0
        # For equities/indices, holidays normally account for ~10-15 days a year (~4-6%).
        # If strict business day gap or missing Close NaN count:
        nan_pct = (df["close"].isna().sum() / len(df)) * 100.0
        if nan_pct > max_missing_pct:
            raise DataQualityError(
                f"Data quality check failed: {nan_pct:.2f}% of close prices are NaN "
                f"(maximum allowed: {max_missing_pct}%)."
            )

    # Forward-fill small gaps only, drop any remaining NaNs at the very start
    cleaned = df.copy()
    cleaned = cleaned.ffill()
    cleaned = cleaned.dropna(subset=["close"])

    if len(cleaned) < min_bars:
        raise DataQualityError(
            f"After cleaning NaNs, only {len(cleaned)} bars remain (minimum: {min_bars})."
        )

    cleaned.attrs["metadata"] = {
        "source": "cache",
        "ticker": df.attrs.get("metadata", {}).get("ticker", ""),
        "start_date": str(cleaned.index[0].date()),
        "end_date": str(cleaned.index[-1].date()),
        "bar_count": len(cleaned),
    }

    return cleaned
