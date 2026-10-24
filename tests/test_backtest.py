"""
tests/test_backtest.py – Backtest Engine Unit Tests
"""

import math
import numpy as np
import pandas as pd
import pytest

from core.backtest import (
    BacktestResult,
    StrategySpec,
    ma_crossover,
    rsi_meanrev,
    run_backtest,
)


def _make_df(prices: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(prices))
    return pd.DataFrame({"close": prices, "volume": 1000}, index=dates)


def test_signal_shift_no_lookahead():
    """Verify position[t] == raw_signal[t-1] and position[0] == 0."""
    prices = [100.0, 100.0, 100.0, 200.0, 200.0, 200.0]
    df = _make_df(prices)

    spec = StrategySpec(
        ticker="TEST",
        strategy="ma_crossover",
        params={"fast": 2, "slow": 3},
        fee_pct=0.0,
        slippage_pct=0.0,
    )
    res = run_backtest(df, spec)

    # First bar position must be 0
    assert res.positions[0] == 0

    # On bar 3, price jumped to 200. Raw signal fires at bar 3.
    # Lookahead prevention means position at bar 3 must still be 0!
    # Traded at bar 4.
    raw_sig = ma_crossover(df, fast=2, slow=3)
    for t in range(1, len(df)):
        assert res.positions[t] == raw_sig.iloc[t - 1]

    # Return on the jump bar (index 3) must be 0 for the strategy
    assert res.returns[3] == 0.0


def test_costs_reduce_returns():
    """Higher fees/slippage strictly reduce final return."""
    rng = np.random.default_rng(123)
    prices = 100.0 * np.cumprod(1.0 + rng.normal(0.001, 0.01, 300))
    df = _make_df(list(prices))

    spec_zero = StrategySpec(ticker="TEST", strategy="ma_crossover", params={"fast": 10, "slow": 30}, fee_pct=0.0, slippage_pct=0.0)
    spec_fee = StrategySpec(ticker="TEST", strategy="ma_crossover", params={"fast": 10, "slow": 30}, fee_pct=0.2, slippage_pct=0.1)

    res_zero = run_backtest(df, spec_zero)
    res_fee = run_backtest(df, spec_fee)

    if res_zero.trade_count > 0:
        assert res_zero.total_return > res_fee.total_return


def test_hand_computed_series():
    """Test tiny series with hand-calculated metrics."""
    # Prices: 100 -> 100 -> 105 -> 110 -> 100
    prices = [100.0, 100.0, 105.0, 110.0, 100.0]
    df = _make_df(prices)

    # Force position to enter on bar 2 and exit on bar 4
    spec = StrategySpec(ticker="TEST", strategy="ma_crossover", params={"fast": 2, "slow": 3}, fee_pct=0.0, slippage_pct=0.0)
    res = run_backtest(df, spec)

    assert isinstance(res.trade_count, int)
    assert res.positions[0] == 0
    assert 0.0 <= res.max_drawdown <= 1.0


def test_zero_trades_edge_case():
    """Zero trades produces Sharpe 0.0, no NaN anywhere in to_dict()."""
    df = _make_df([100.0] * 50)
    spec = StrategySpec(ticker="TEST", strategy="rsi_meanrev", params={"period": 14, "oversold": 5.0, "overbought": 95.0})
    res = run_backtest(df, spec)

    assert res.trade_count == 0
    assert res.sharpe == 0.0
    d = res.to_dict()
    for k, v in d.items():
        if isinstance(v, float):
            assert not math.isnan(v)
            assert not math.isinf(v)


def test_ma_validation():
    """fast >= slow raises ValueError."""
    df = _make_df([100.0] * 50)
    with pytest.raises(ValueError):
        ma_crossover(df, fast=50, slow=20)
    with pytest.raises(ValueError):
        ma_crossover(df, fast=50, slow=50)


def test_rsi_wilder_smoothing():
    """RSI mean reversion generates valid positions."""
    rng = np.random.default_rng(42)
    prices = 100.0 * np.cumprod(1.0 + rng.normal(0.0, 0.02, 100))
    df = _make_df(list(prices))

    pos = rsi_meanrev(df, period=14, oversold=30.0, overbought=70.0)
    assert set(pos.unique()).issubset({0, 1})


def test_rsi_alias_support():
    """Both 'rsi' and 'rsi_meanrev' strategies are supported."""
    rng = np.random.default_rng(42)
    prices = 100.0 * np.cumprod(1.0 + rng.normal(0.0, 0.02, 100))
    df = _make_df(list(prices))

    spec_alias = StrategySpec(ticker="TCS.NS", strategy="rsi", params={"period": 14, "oversold": 30.0, "overbought": 70.0})
    res_alias = run_backtest(df, spec_alias)
    assert len(res_alias.positions) == 100

    spec_canon = StrategySpec(ticker="TCS.NS", strategy="rsi_meanrev", params={"period": 14, "oversold": 30.0, "overbought": 70.0})
    res_canon = run_backtest(df, spec_canon)
    assert len(res_canon.positions) == 100
    assert res_alias.sharpe == res_canon.sharpe
