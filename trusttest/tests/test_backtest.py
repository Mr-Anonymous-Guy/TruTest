"""
tests/test_backtest.py – Placeholder tests for core/backtest.py

TODO Phase 2: implement tests once run_backtest() is live.
"""

import pytest


@pytest.mark.skip(reason="Phase 2 – run_backtest() not yet implemented")
def test_sma_crossover_returns_positive_sharpe():
    """SMA 50/200 on a trending synthetic series should yield Sharpe > 0."""
    pass


@pytest.mark.skip(reason="Phase 2 – run_backtest() not yet implemented")
def test_signal_shift_prevents_lookahead():
    """Signals must be shifted by 1 bar; same-bar entries should not exist."""
    pass


@pytest.mark.skip(reason="Phase 2 – run_backtest() not yet implemented")
def test_fees_reduce_return():
    """Higher fees_bps should produce strictly lower total_return_pct."""
    pass


@pytest.mark.skip(reason="Phase 2 – run_backtest() not yet implemented")
def test_zero_trades_when_flat_signal():
    """A constant-zero signal should produce zero trades and zero return."""
    pass
