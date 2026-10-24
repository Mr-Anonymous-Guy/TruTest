"""
tests/test_backtest_agent.py – Unit Tests for Backtest Agent Handler Logic
"""

import pytest
from core.data import load_cached
from core.backtest import StrategySpec, run_backtest
from agents.models import df_to_price_data
from agents.backtest_agent import execute_backtest


def test_execute_backtest_matches_core():
    """Verify that calling execute_backtest yields identical metrics to calling core directly."""
    df = load_cached("RELIANCE.NS")
    spec = StrategySpec(
        ticker="RELIANCE.NS",
        strategy="ma_crossover",
        params={"fast": 50, "slow": 200},
        fee_pct=0.1,
        slippage_pct=0.05,
    )

    core_res = run_backtest(df, spec)
    p_data = df_to_price_data("req-bt-test", df, ticker="RELIANCE.NS", source="cache")

    agent_res = execute_backtest(spec.to_dict(), p_data.dict())

    core_dict = core_res.to_dict()
    assert agent_res["total_return"] == core_dict["total_return"]
    assert agent_res["sharpe"] == core_dict["sharpe"]
    assert agent_res["trade_count"] == core_dict["trade_count"]
    assert agent_res["max_drawdown"] == core_dict["max_drawdown"]


def test_execute_backtest_invalid_spec():
    """Invalid parameter (fast >= slow) raises validation error."""
    df = load_cached("RELIANCE.NS")
    bad_spec = {
        "ticker": "RELIANCE.NS",
        "strategy": "ma_crossover",
        "params": {"fast": 200, "slow": 50},  # Invalid
        "fee_pct": 0.1,
        "slippage_pct": 0.05,
    }
    p_data = df_to_price_data("req-bad", df, ticker="RELIANCE.NS", source="cache")

    with pytest.raises(ValueError) as exc_info:
        execute_backtest(bad_spec, p_data.dict())
    assert "fast" in str(exc_info.value).lower()
