"""
TrustTest – Backtest Engine (stub)
====================================
Pure-Python / pandas implementation. No agent code here — this module is
imported by backtest_agent.py but can also be tested directly.

TODO (Phase 2):
    - Implement run_backtest() fully
    - Add generate_signals() dispatcher for each strategy_type
    - Add compute_metrics() (Sharpe, maxDD, CAGR, win-rate)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
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
    Fees and slippage are applied on every trade (round-trip = 2x).

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with Date index.
    strategy_type : str
        One of "sma_crossover", "rsi_threshold", "momentum", "mean_reversion".
    params : dict
        Strategy-specific hyperparameters.
    fees_bps : float
        One-way fee in basis points.
    slippage_bps : float
        One-way slippage in basis points.

    Returns
    -------
    dict matching the fields of BacktestResult (minus ticker/strategy_type/params
    which are added by the caller).

    TODO: implement fully in Phase 2.
    """
    # TODO Phase 2: replace stub
    raise NotImplementedError("run_backtest() not yet implemented – Phase 2 work")


def generate_signals(
    df: pd.DataFrame,
    strategy_type: str,
    params: Dict[str, Any],
) -> pd.Series:
    """
    Return a pd.Series of integer signals {-1, 0, 1} aligned to df.index.

    Signals are NOT shifted here – the caller must shift by 1 bar.

    TODO: implement each strategy_type in Phase 2.
    """
    raise NotImplementedError("generate_signals() – Phase 2")


def compute_metrics(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.05,
    trading_days_per_year: int = 252,
) -> Dict[str, float]:
    """
    Given a daily equity curve (starting at 1.0), return:
        sharpe_ratio, max_drawdown_pct, cagr_pct, total_return_pct

    TODO: implement in Phase 2.
    """
    raise NotImplementedError("compute_metrics() – Phase 2")
