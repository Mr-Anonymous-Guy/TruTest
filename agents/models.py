"""
agents/models.py – Shared Typed Message Models for TrustTest Worker Agents

All inter-agent messages inherit from uagents.Model and carry `request_id: str`
for deterministic correlation. Payloads use standard JSON-friendly types
(dicts, lists, strings, floats) to ensure clean serialization across relays.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import pandas as pd
from uagents import Model


# ---------------------------------------------------------------------------
# 1. Parser Agent Models
# ---------------------------------------------------------------------------

class ParseRequest(Model):
    request_id: str
    text: str
    context: Optional[Dict[str, Any]] = None


class ParseResponse(Model):
    request_id: str
    ok: bool
    spec: Optional[Dict[str, Any]] = None
    missing: List[str] = []
    question: Optional[str] = None
    assumptions: List[str] = []
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 2. Market Data Agent Models
# ---------------------------------------------------------------------------

class DataRequest(Model):
    request_id: str
    ticker: str
    start: Optional[str] = None
    end: Optional[str] = None


class PriceData(Model):
    request_id: str
    ok: bool
    ticker: str
    source: str
    start: str
    end: str
    bars: int
    dates: List[str]
    closes: List[float]
    note: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. Backtest Agent Models
# ---------------------------------------------------------------------------

class BacktestRequest(Model):
    request_id: str
    spec: Dict[str, Any]
    prices: Dict[str, Any]  # Serialized PriceData or dict representation


class BacktestResponse(Model):
    request_id: str
    ok: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 4. Skeptic Auditor Models
# ---------------------------------------------------------------------------

class AuditRequest(Model):
    request_id: str
    spec: Dict[str, Any]
    prices: Dict[str, Any]  # Serialized PriceData or dict representation


class AuditResponse(Model):
    request_id: str
    ok: bool
    report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Conversion Helpers
# ---------------------------------------------------------------------------

def df_to_price_data(
    request_id: str,
    df: pd.DataFrame,
    ticker: str,
    source: str,
    note: Optional[str] = None,
    ok: bool = True,
    error: Optional[str] = None,
    round_decimals: int = 2,
) -> PriceData:
    """
    Convert a price DataFrame with a DatetimeIndex and close column into a PriceData model.
    Rounds closing prices to round_decimals to optimize JSON envelope size.
    """
    if df is None or df.empty:
        return PriceData(
            request_id=request_id,
            ok=False,
            ticker=ticker,
            source=source,
            start="",
            end="",
            bars=0,
            dates=[],
            closes=[],
            note=note,
            error=error or "Price DataFrame is empty",
        )

    close_series = df["close"] if "close" in df.columns else df["Close"]
    dates = [ts.strftime("%Y-%m-%d") for ts in df.index]
    closes = [round(float(c), round_decimals) for c in close_series.values]

    return PriceData(
        request_id=request_id,
        ok=ok,
        ticker=ticker,
        source=source,
        start=dates[0],
        end=dates[-1],
        bars=len(dates),
        dates=dates,
        closes=closes,
        note=note,
        error=error,
    )


def prices_to_df(prices: Union[PriceData, Dict[str, Any]]) -> pd.DataFrame:
    """
    Reconstruct a pandas DataFrame from a PriceData model or dict representation.
    Returns DataFrame with a monotonic DatetimeIndex and float 'close' column.
    """
    if isinstance(prices, PriceData):
        p_dict = prices.dict()
    else:
        p_dict = dict(prices)

    dates = p_dict.get("dates", [])
    closes = p_dict.get("closes", [])

    if not dates:
        return pd.DataFrame(columns=["close"])

    idx = pd.to_datetime(dates)
    df = pd.DataFrame({"close": [float(c) for c in closes]}, index=idx)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df
