"""
agents/data_source.py – Market Data Fetching with Resilient Fallback & Edge Cases (Phase 4)
==========================================================================================
Handles:
  1. Live yfinance fetch with cache fallback
  2. Future end date clamping; rejection if start is in future
  3. start >= end validation
  4. Weekend-only or tiny ranges
  5. Empty yfinance frames or recent listings with < 200 bars
  6. Heavy NaN data handling
  7. Lowercase / spaced ticker normalization
  8. Unknown ticker "Did you mean ...?" with difflib against cached tickers
  9. Fault injection (TRUSTTEST_FAULT=data_live_fail / data_fail)
"""

from __future__ import annotations

import datetime
import difflib
import logging
import os
from typing import List, Optional, Tuple
import pandas as pd

from agents.faults import is_fault_active
from core.data import DataQualityError, load_cached, validate_prices

logger = logging.getLogger("trusttest.data_source")

COMMON_TICKERS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "^NSEI",
    "AAPL",
]


def clean_ticker_symbol(raw_ticker: str) -> str:
    """Normalize lowercase, spaced, or punctuated ticker symbols."""
    cleaned = raw_ticker.strip().replace(" ", "").upper()
    return cleaned


def find_similar_tickers(ticker: str, cache_dir: str = "data/cache") -> List[str]:
    """Find close matches using difflib against cached tickers and common NSE symbols."""
    available: List[str] = list(COMMON_TICKERS)
    try:
        from pathlib import Path
        p = Path(cache_dir)
        if p.exists():
            for f in p.glob("*.csv"):
                stem = f.stem.upper()
                if stem not in available:
                    available.append(stem)
    except Exception:
        pass
    matches = difflib.get_close_matches(ticker, available, n=2, cutoff=0.5)
    return matches


def fetch_prices(
    ticker: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    cache_dir: str = "data/cache",
    enable_live: bool = True,
) -> Tuple[pd.DataFrame, str, Optional[str]]:
    """
    Fetch price history for `ticker` between `start` and `end`.
    Returns:
        (cleaned_df, source, note)
    """
    clean_ticker = clean_ticker_symbol(ticker)
    notes: List[str] = []
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 1. Fault injection check
    if is_fault_active("data_fail"):
        logger.warning("🚨 [FAULT INJECTION ACTIVE] Simulating complete Market Data failure.")
        raise DataQualityError("[FAULT INJECTION ACTIVE] Simulated Market Data Agent failure.")

    if is_fault_active("data_live_fail"):
        logger.warning("🚨 [FAULT INJECTION ACTIVE] Forcing live yfinance failure; falling back to cache.")
        enable_live = False
        notes.append("Simulated live data failure (TRUSTTEST_FAULT=data_live_fail); used local cached data.")

    # 2. Date Range Validations
    if start and end and start >= end:
        raise DataQualityError(
            f"Invalid date range: start date ({start}) must be before end date ({end})."
        )

    if start and start > today_str:
        raise DataQualityError(
            f"Start date ({start}) is in the future. Backtesting requires historical data."
        )

    clamped_end = end
    if end and end > today_str:
        clamped_end = today_str
        notes.append(f"End date ({end}) was in the future; clamped to latest available bar ({today_str}).")

    df: Optional[pd.DataFrame] = None
    source = "live"

    # 3. Live fetch via yfinance
    if enable_live:
        for attempt in range(2):
            try:
                import yfinance as yf
                yf_ticker = yf.Ticker(clean_ticker)
                live_df = yf_ticker.history(start=start, end=clamped_end, auto_adjust=True, timeout=10)
                if live_df is not None and not live_df.empty and len(live_df) >= 30:
                    live_df.columns = [str(c).lower() for c in live_df.columns]
                    if hasattr(live_df.index, "tz") and live_df.index.tz is not None:
                        live_df.index = live_df.index.tz_localize(None)
                    df = live_df
                    source = "live"
                    notes.append(f"Fetched live market data from Yahoo Finance ({len(df)} bars).")
                    break
            except Exception as e:
                logger.warning("Live yfinance attempt %d failed for %s: %s", attempt + 1, clean_ticker, e)

    # 4. Fallback to cached CSV
    if df is None or df.empty:
        try:
            cached_df = load_cached(clean_ticker, cache_dir=cache_dir)
            if start:
                cached_df = cached_df[cached_df.index >= pd.to_datetime(start)]
            if clamped_end:
                cached_df = cached_df[cached_df.index <= pd.to_datetime(clamped_end)]

            df = cached_df
            source = "cache"
            notes.append(f"Used cached historical CSV data ({len(df)} bars).")
        except DataQualityError:
            # Check for close matches
            suggestions = find_similar_tickers(clean_ticker, cache_dir=cache_dir)
            if suggestions:
                sug_str = ", ".join(suggestions)
                raise DataQualityError(
                    f"Ticker '{clean_ticker}' could not be loaded. Did you mean: {sug_str}? "
                    f"Available cached tickers: {', '.join(COMMON_TICKERS[:4])}."
                )
            else:
                raise DataQualityError(
                    f"Ticker '{clean_ticker}' could not be found. "
                    f"Available cached tickers: {', '.join(COMMON_TICKERS[:4])}."
                )
        except Exception as e:
            raise DataQualityError(f"Failed to load data for {clean_ticker}: {e}")

    # 5. Length & Quality Validation
    if df is None or df.empty:
        raise DataQualityError(
            f"No price data available for {clean_ticker} in the specified range. "
            "The range may only contain weekends/holidays."
        )

    if len(df) < 5:
        raise DataQualityError(
            f"Date range contains only {len(df)} trading days (e.g. weekend or tiny window). "
            "Please specify a longer date range (minimum 6 months)."
        )

    if len(df) < 200:
        raise DataQualityError(
            f"Insufficient price history: found {len(df)} bars for {clean_ticker}, "
            "but at least 200 bars (~10 months) are required to compute moving averages and evaluate drawdown."
        )

    # Clean & validate NaNs
    df = validate_prices(df, min_bars=200, max_missing_pct=5.0)

    combined_note = " | ".join(notes) if notes else None
    return df, source, combined_note
