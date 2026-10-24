"""
tests/test_backtest.py – Comprehensive unit tests for core/backtest.py
"""

import numpy as np
import pandas as pd
import pytest

from trusttest.core.backtest import compute_metrics, generate_signals, run_backtest


def _make_trending_df(n: int = 400, seed: int = 42) -> pd.DataFrame:
    """Synthetic upward-trending price series."""
    dates = pd.bdate_range("2020-01-01", periods=n)
    rng = np.random.default_rng(seed)
    # Drift up with slight noise
    returns = rng.normal(0.001, 0.008, n)
    close = 100.0 * np.cumprod(1.0 + returns)
    return pd.DataFrame(
        {
            "Open": close * 0.998,
            "High": close * 1.005,
            "Low": close * 0.995,
            "Close": close,
            "Volume": 500_000,
        },
        index=dates,
    )


def test_sma_crossover_returns_positive_sharpe():
    """SMA 10/30 on a strongly trending synthetic series should yield Sharpe > 0."""
    df = _make_trending_df(n=500)
    result = run_backtest(
        df=df,
        strategy_type="sma_crossover",
        params={"short_window": 10, "long_window": 30},
        fees_bps=5.0,
        slippage_bps=2.0,
    )
    assert result["trade_count"] > 0
    assert result["sharpe_ratio"] > 0
    assert result["total_return_pct"] > 0
    assert len(result["equity_curve"]) == len(df)


def test_signal_shift_prevents_lookahead():
    """Signals must be shifted by 1 bar; same-bar entries should not exist."""
    dates = pd.bdate_range("2020-01-01", periods=5)
    # Flat price, then big jump on day 2
    prices = [100.0, 100.0, 200.0, 200.0, 200.0]
    df = pd.DataFrame(
        {"Open": prices, "High": prices, "Low": prices, "Close": prices, "Volume": 1000},
        index=dates,
    )

    # Momentum strategy: jumps on day 2
    raw = generate_signals(df, "momentum", {"lookback": 1, "threshold": 0.5})
    # Day 2 is the first day close jumps from 100 to 200, so raw signal fires at index 2
    assert raw.iloc[2] == 1
    assert raw.iloc[0] == 0
    assert raw.iloc[1] == 0

    result = run_backtest(df, "momentum", {"lookback": 1, "threshold": 0.5}, fees_bps=0, slippage_bps=0)
    # The jump happens at day 2 close. Lookahead prevention means we only participate in day 3 returns!
    # Day 2 return of asset is 100%, but strategy return on day 2 must be 0 because signal was shifted
    strat_day2_ret = result["daily_returns"][2]
    assert strat_day2_ret == 0.0


def test_fees_reduce_return():
    """Higher fees_bps should produce strictly lower total_return_pct."""
    df = _make_trending_df(n=300)
    res_low_fee = run_backtest(
        df, "sma_crossover", {"short_window": 10, "long_window": 30}, fees_bps=0.0, slippage_bps=0.0
    )
    res_high_fee = run_backtest(
        df, "sma_crossover", {"short_window": 10, "long_window": 30}, fees_bps=50.0, slippage_bps=50.0
    )
    assert res_low_fee["total_return_pct"] > res_high_fee["total_return_pct"]


def test_zero_trades_when_flat_signal():
    """A constant-zero signal should produce zero trades and zero return."""
    df = _make_trending_df(n=100)
    # RSI with impossible oversold condition yields 0 signals
    result = run_backtest(
        df, "rsi_threshold", {"oversold": -10.0, "overbought": 110.0}, fees_bps=10.0, slippage_bps=5.0
    )
    assert result["trade_count"] == 0
    assert result["total_return_pct"] == 0.0
    assert result["max_drawdown_pct"] == 0.0
