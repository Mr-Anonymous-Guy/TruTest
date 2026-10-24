"""
TrustTest - Cache Builder
==========================
Downloads adjusted daily OHLCV data from yfinance (2015-01-01 to today)
for a fixed set of tickers and saves each to data/cache/<TICKER>.csv.

Newer yfinance returns MultiIndex columns, so we flatten them to:
    Date, Open, High, Low, Close, Volume

Run once before starting agents (or when you need a data refresh):
    python trusttest/scripts/build_cache.py

Tickers: RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS, ^NSEI, AAPL
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Force UTF-8 output so [OK]/symbols don't crash on Windows cp1252 terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# File is at: <repo_root>/trusttest/scripts/build_cache.py
# parent       = trusttest/scripts/
# parent.parent = trusttest/
# parent.parent.parent = <repo_root>/
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import yfinance as yf

TICKERS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "^NSEI",
    "AAPL",
]

START = "2015-01-01"
CACHE_DIR = ROOT / "trusttest" / "data" / "cache"


def safe_filename(ticker: str) -> str:
    """Strip '^' so '^NSEI' → 'NSEI.csv'."""
    return ticker.replace("^", "") + ".csv"


def download_and_save(ticker: str) -> tuple[bool, str]:
    """
    Download *ticker* data, flatten columns, save to CSV.
    Returns (success, message).
    """
    path = CACHE_DIR / safe_filename(ticker)
    try:
        raw = yf.download(
            ticker,
            start=START,
            auto_adjust=True,
            progress=False,
            timeout=30,
        )
        if raw.empty:
            return False, f"{ticker}: yfinance returned empty DataFrame"

        # Flatten MultiIndex columns (yfinance >= 0.2.31)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        # Normalise to Title-case
        raw.columns = [c.title() for c in raw.columns]

        # Keep only OHLCV columns (drop 'Dividends', 'Stock Splits', etc.)
        keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
        df = raw[keep].copy()
        df.index.name = "Date"
        df = df.dropna(subset=["Close"])

        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path)

        msg = f"{ticker}: {len(df)} rows saved → {path.name}"
        return True, msg

    except Exception as exc:
        return False, f"{ticker}: FAILED – {exc}"


def verify_csv(ticker: str) -> tuple[bool, str]:
    """Re-load the saved CSV and do a basic sanity check."""
    path = CACHE_DIR / safe_filename(ticker)
    try:
        df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
        if df.empty:
            return False, f"{ticker}: CSV is empty after re-load"
        # Check for big gaps (more than 10 consecutive NaN Close values)
        max_gap = int(df["Close"].isna().astype(int).groupby(
            (df["Close"].notna()).cumsum()
        ).sum().max() or 0)
        status = f"{ticker}: {len(df)} rows, max gap = {max_gap} bars"
        return True, status
    except Exception as exc:
        return False, f"{ticker}: verify failed – {exc}"


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Cache directory: {CACHE_DIR}\n")

    failed: list[str] = []

    for ticker in TICKERS:
        ok, msg = download_and_save(ticker)
        symbol = "[OK]  " if ok else "[FAIL]"
        print(f"  {symbol} {msg}")
        if not ok:
            failed.append(ticker)

    print("\n--- Verification ---")
    for ticker in TICKERS:
        if ticker in failed:
            print(f"  [SKIP] {ticker} (download failed)")
            continue
        ok, msg = verify_csv(ticker)
        symbol = "[OK]  " if ok else "[FAIL]"
        print(f"  {symbol} {msg}")

    print()
    if failed:
        print(f"WARNING: Failed tickers: {', '.join(failed)}")
        print("  Agents will fall back to cache for successful tickers.")
        print("  Re-run this script with a network connection to populate missing caches.")
    else:
        print("SUCCESS: All tickers cached successfully.")


if __name__ == "__main__":
    main()
