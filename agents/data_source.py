"""
agents/data_source.py – Market Data Fetching with Resilient Local Cache Fallback

Order of operations:
1. Try live yfinance with auto_adjust=True (10s timeout, 1 retry).
2. If live fetch fails, falls back seamlessly to local cached CSVs in data/cache/.
3. If ticker not found anywhere, returns a friendly DataQualityError listing cached tickers.
4. Validates data with core.data.validate_prices.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple
import pandas as pd

from core.data import DataQualityError, load_cached, validate_prices

logger = logging.getLogger("trusttest.data_source")


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
        where source is 'live' or 'cache', and note contains details if fallback occurred.
    """
    clean_ticker = ticker.strip().upper()
    df: Optional[pd.DataFrame] = None
    source = "live"
    note: Optional[str] = None

    # 1. Attempt live yfinance if enabled
    if enable_live:
        for attempt in range(2):
            try:
                import yfinance as yf
                yf_ticker = yf.Ticker(clean_ticker)
                # auto_adjust=True gives adjusted close as 'Close'
                live_df = yf_ticker.history(start=start, end=end, auto_adjust=True, timeout=10)
                if live_df is not None and not live_df.empty and len(live_df) >= 30:
                    live_df.columns = [str(c).lower() for c in live_df.columns]
                    # Ensure index is datetime without timezone
                    if hasattr(live_df.index, "tz") and live_df.index.tz is not None:
                        live_df.index = live_df.index.tz_localize(None)
                    df = live_df
                    source = "live"
                    note = f"Fetched live data from Yahoo Finance ({len(df)} bars)."
                    break
            except Exception as e:
                logger.warning("Live yfinance attempt %d failed for %s: %s", attempt + 1, clean_ticker, e)

    # 2. Fallback to cached CSV
    if df is None or df.empty:
        try:
            cached_df = load_cached(clean_ticker, cache_dir=cache_dir)
            if start:
                cached_df = cached_df[cached_df.index >= pd.to_datetime(start)]
            if end:
                cached_df = cached_df[cached_df.index <= pd.to_datetime(end)]

            df = cached_df
            source = "cache"
            note = f"Used cached historical CSV data ({len(df)} bars)."
        except DataQualityError:
            raise
        except Exception as e:
            raise DataQualityError(f"Failed to load data for {clean_ticker}: {e}")

    # 3. Validate prices
    df = validate_prices(df, min_bars=200, max_missing_pct=5.0)

    return df, source, note
