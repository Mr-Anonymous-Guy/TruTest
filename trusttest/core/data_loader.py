"""
TrustTest – Data Loader
=======================
Tries live yfinance first (10 s timeout, one retry),
then falls back to a locally cached CSV in data/cache/.
Returns (DataFrame, source_label) where source_label is "live" or "cache".

DataFrame columns: Date (index), Open, High, Low, Close, Volume
"""

import logging
import os
import time
from pathlib import Path
from typing import Tuple

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Absolute path to the cache directory relative to this file
_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"

# Minimum acceptable trading days in a single year
_MIN_ROWS = 200

# Maximum fraction of rows with NaN Close before we raise
_MAX_NAN_FRACTION = 0.03


def _cache_path(ticker: str) -> Path:
    """Return the expected CSV path for a ticker, stripping '^' for index symbols."""
    safe_name = ticker.replace("^", "") + ".csv"
    return _CACHE_DIR / safe_name


def _load_from_csv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Load and slice a cached CSV. Raises FileNotFoundError if absent."""
    path = _cache_path(ticker)
    if not path.exists():
        raise FileNotFoundError(f"No cached data for {ticker} at {path}")

    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    df = df.loc[start:end]  # type: ignore[misc]
    return df


def _download_live(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Download from yfinance with auto_adjust=True.
    Flattens MultiIndex columns (newer yfinance) to standard OHLCV names.
    """
    raw = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        timeout=10,
    )
    if raw.empty:
        raise ValueError(f"yfinance returned empty DataFrame for {ticker}")

    # Flatten MultiIndex if present (yfinance >= 0.2.31)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Normalise column names to Title-case
    raw.columns = [c.title() for c in raw.columns]
    raw.index.name = "Date"
    return raw


def _validate(df: pd.DataFrame, ticker: str) -> None:
    """Raise ValueError if the DataFrame is too short or too holey."""
    if df.empty:
        raise ValueError(f"No data rows for {ticker}")

    if len(df) < _MIN_ROWS:
        raise ValueError(
            f"{ticker}: only {len(df)} rows — need at least {_MIN_ROWS}. "
            "Try a longer date range."
        )

    nan_rate = df["Close"].isna().mean()
    if nan_rate > _MAX_NAN_FRACTION:
        raise ValueError(
            f"{ticker}: {nan_rate:.1%} of Close prices are NaN — "
            "data quality too poor to backtest."
        )


def load_prices(
    ticker: str,
    start: str,
    end: str,
) -> Tuple[pd.DataFrame, str]:
    """
    Load OHLCV price data for *ticker* between *start* and *end* (ISO strings).

    Strategy:
        1. Try live yfinance (up to 2 attempts with 3-s back-off).
        2. On any failure, fall back to data/cache/<TICKER>.csv.
        3. Validate row count and NaN fraction.

    Returns
    -------
    (df, source) where source is "live" or "cache".
    """
    df: pd.DataFrame | None = None
    source = "live"

    # --- Attempt live download (2 tries) ---
    for attempt in range(1, 3):
        try:
            df = _download_live(ticker, start, end)
            logger.info("Loaded %s rows live for %s (attempt %d)", len(df), ticker, attempt)
            source = "live"
            break
        except Exception as exc:
            logger.warning(
                "Live download attempt %d for %s failed: %s", attempt, ticker, exc
            )
            if attempt < 2:
                time.sleep(3)

    # --- Fallback to cache ---
    if df is None or df.empty:
        logger.info("Falling back to cache for %s", ticker)
        try:
            df = _load_from_csv(ticker, start, end)
            source = "cache"
            logger.info("Loaded %s rows from cache for %s", len(df), ticker)
        except FileNotFoundError:
            raise RuntimeError(
                f"No live data and no cache for {ticker}. "
                "Run scripts/build_cache.py first."
            )

    _validate(df, ticker)
    return df, source
