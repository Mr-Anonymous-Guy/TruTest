"""
TrustTest – Backtest Engine
===========================
Pure-Python / pandas implementation. No agent code here — this module is
imported by backtest_agent.py but can also be tested directly.

Signals are shifted one bar to prevent look-ahead bias.
Fees and slippage are applied on every trade.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal Generators
# ---------------------------------------------------------------------------

def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate standard RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def generate_signals(
    df: pd.DataFrame,
    strategy_type: str,
    params: Dict[str, Any],
) -> pd.Series:
    """
    Return a pd.Series of integer signals {-1, 0, 1} aligned to df.index.

    Signals are NOT shifted here – the caller must shift by 1 bar to prevent
    lookahead bias.
    """
    if df.empty:
        return pd.Series(dtype=int)

    close = df["Close"]
    signals = pd.Series(0, index=df.index, dtype=int)

    st = strategy_type.lower().strip()

    if st == "sma_crossover":
        short_w = int(params.get("short_window") or params.get("short") or params.get("fast") or 50)
        long_w = int(params.get("long_window") or params.get("long") or params.get("slow") or 200)
        if short_w >= long_w:
            short_w, long_w = min(short_w, long_w), max(short_w, long_w)
            if short_w == long_w:
                short_w = max(1, long_w - 1)

        sma_short = close.rolling(short_w, min_periods=short_w).mean()
        sma_long = close.rolling(long_w, min_periods=long_w).mean()
        signals[sma_short > sma_long] = 1

    elif st == "rsi_threshold":
        period = int(params.get("rsi_period") or params.get("period") or 14)
        oversold = float(params.get("oversold") or params.get("lower_threshold") or 30.0)
        overbought = float(params.get("overbought") or params.get("upper_threshold") or 70.0)

        rsi = _calc_rsi(close, period=period)
        in_pos = 0
        pos_values = []
        for val in rsi:
            if val < oversold:
                in_pos = 1
            elif val > overbought:
                in_pos = 0
            pos_values.append(in_pos)
        signals = pd.Series(pos_values, index=df.index, dtype=int)

    elif st == "momentum":
        lookback = int(params.get("lookback") or params.get("period") or 20)
        threshold = float(params.get("threshold") or 0.0)
        pct = close.pct_change(lookback).fillna(0.0)
        signals[pct > threshold] = 1

    elif st == "mean_reversion":
        window = int(params.get("window") or params.get("period") or 20)
        num_std = float(params.get("num_std") or params.get("std_dev") or 2.0)
        ma = close.rolling(window, min_periods=window).mean()
        std = close.rolling(window, min_periods=window).std().fillna(0.0)
        lower_band = ma - num_std * std

        in_pos = 0
        pos_values = []
        for c, lb, mean_v in zip(close, lower_band, ma):
            if pd.isna(lb) or pd.isna(mean_v):
                pos_values.append(0)
                continue
            if c < lb:
                in_pos = 1
            elif c >= mean_v:
                in_pos = 0
            pos_values.append(in_pos)
        signals = pd.Series(pos_values, index=df.index, dtype=int)

    else:
        logger.warning("Unrecognized strategy_type: %s. Returning zero signals.", strategy_type)

    return signals


# ---------------------------------------------------------------------------
# Metric Calculation
# ---------------------------------------------------------------------------

def compute_metrics(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.05,
    trading_days_per_year: int = 252,
) -> Dict[str, float]:
    """
    Given a daily equity curve (starting at 1.0), return:
        sharpe_ratio, max_drawdown_pct, cagr_pct, total_return_pct
    """
    if len(equity_curve) < 2:
        return {
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "cagr_pct": 0.0,
            "total_return_pct": 0.0,
        }

    initial_val = float(equity_curve.iloc[0])
    final_val = float(equity_curve.iloc[-1])
    total_return_pct = ((final_val / initial_val) - 1.0) * 100.0

    n_days = len(equity_curve)
    years = max(n_days / trading_days_per_year, 1.0 / trading_days_per_year)
    final_ratio = max(final_val / initial_val, 1e-6)
    cagr_pct = ((final_ratio ** (1.0 / years)) - 1.0) * 100.0

    # Max Drawdown
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    max_drawdown_pct = abs(float(drawdown.min())) * 100.0

    # Sharpe Ratio
    daily_returns = equity_curve.pct_change().dropna()
    std = float(daily_returns.std())
    if std > 1e-9:
        excess_daily_mean = float(daily_returns.mean()) - (risk_free_rate / trading_days_per_year)
        sharpe_ratio = float((excess_daily_mean / std) * np.sqrt(trading_days_per_year))
    else:
        sharpe_ratio = 0.0

    return {
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown_pct": max_drawdown_pct,
        "cagr_pct": cagr_pct,
        "total_return_pct": total_return_pct,
    }


# ---------------------------------------------------------------------------
# Backtest Runner
# ---------------------------------------------------------------------------

def run_backtest(
    df: pd.DataFrame,
    strategy_type: str,
    params: Dict[str, Any],
    fees_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> Dict[str, Any]:
    """
    Run a backtest on *df* (OHLCV DataFrame, Date index).

    Signals are shifted one bar to prevent look-ahead bias.
    Fees and slippage are applied on every trade.
    """
    if df.empty:
        return {
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "cagr_pct": 0.0,
            "total_return_pct": 0.0,
            "trade_count": 0,
            "win_rate_pct": 0.0,
            "equity_curve": [1.0],
            "daily_returns": [0.0],
            "signal_dates": [],
        }

    # Generate raw signals and shift by 1 bar
    raw_signals = generate_signals(df, strategy_type, params)
    shifted_signals = raw_signals.shift(1).fillna(0).astype(int)

    # Asset daily return
    close = df["Close"]
    asset_returns = close.pct_change().fillna(0.0)

    # Trade detection & costs
    trade_diff = shifted_signals.diff().fillna(shifted_signals.iloc[0])
    trades_mask = trade_diff != 0
    trade_count = int(trades_mask.sum())

    total_cost_frac = (fees_bps + slippage_bps) / 10000.0
    cost_drag = np.abs(trade_diff).astype(float) * total_cost_frac

    # Daily strategy returns & equity curve
    daily_strategy_returns = (shifted_signals.astype(float) * asset_returns) - cost_drag
    equity_curve = (1.0 + daily_strategy_returns).cumprod()

    # Calculate trade-level win rate
    # Track discrete trades from entry to exit
    win_rate_pct = 0.0
    if trade_count > 0:
        trades_pnl: List[float] = []
        in_trade = False
        entry_price = 0.0
        for i in range(len(df)):
            sig = shifted_signals.iloc[i]
            prev_sig = shifted_signals.iloc[i - 1] if i > 0 else 0
            curr_price = float(close.iloc[i])

            if sig != 0 and prev_sig == 0:
                # Entry
                in_trade = True
                entry_price = curr_price
            elif sig == 0 and prev_sig != 0 and in_trade:
                # Exit
                in_trade = False
                trade_ret = (curr_price / entry_price - 1.0) - (2.0 * total_cost_frac)
                trades_pnl.append(trade_ret)

        if in_trade and entry_price > 0:
            last_price = float(close.iloc[-1])
            trade_ret = (last_price / entry_price - 1.0) - total_cost_frac
            trades_pnl.append(trade_ret)

        if trades_pnl:
            wins = sum(1 for p in trades_pnl if p > 0)
            win_rate_pct = (wins / len(trades_pnl)) * 100.0
        else:
            win_rate_pct = 0.0

    # Signal execution dates
    signal_dates = [str(idx.date()) if hasattr(idx, "date") else str(idx) for idx in df.index[trades_mask]]

    metrics = compute_metrics(equity_curve)

    return {
        "sharpe_ratio": round(metrics["sharpe_ratio"], 2),
        "max_drawdown_pct": round(metrics["max_drawdown_pct"], 2),
        "cagr_pct": round(metrics["cagr_pct"], 2),
        "total_return_pct": round(metrics["total_return_pct"], 2),
        "trade_count": trade_count,
        "win_rate_pct": round(win_rate_pct, 2),
        "equity_curve": [round(float(x), 4) for x in equity_curve.tolist()],
        "daily_returns": [round(float(x), 6) for x in daily_strategy_returns.tolist()],
        "signal_dates": signal_dates,
    }
