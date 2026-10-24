"""
tests/test_skeptic_agent.py – Unit Tests & Runtime Benchmarks for Skeptic Agent
"""

import json
import time
import pytest
from core.data import load_cached
from core.backtest import StrategySpec
from core.skeptic import audit
from agents.models import df_to_price_data
from agents.skeptic_agent import execute_audit


def test_execute_audit_matches_core():
    """Verify that execute_audit yields identical findings to core.skeptic.audit."""
    df = load_cached("RELIANCE.NS")
    spec = StrategySpec(
        ticker="RELIANCE.NS",
        strategy="ma_crossover",
        params={"fast": 50, "slow": 200},
        fee_pct=0.1,
        slippage_pct=0.05,
    )

    core_report = audit(df, spec)
    p_data = df_to_price_data("req-audit-test", df, ticker="RELIANCE.NS", source="cache")

    agent_rep = execute_audit(spec.to_dict(), p_data.dict())

    assert agent_rep["verdict"] == core_report.verdict
    assert len(agent_rep["tests"]) == len(core_report.tests)
    assert agent_rep["base_metrics"]["sharpe"] == pytest.approx(core_report.base_metrics["sharpe"], rel=1e-3)


def test_measure_demo_pair_runtime():
    """
    Measure and log the runtime of the Skeptic audit on Demo A and Demo B inputs.
    Report elapsed time for both to verify execution stays within timeout budgets.
    """
    with open("data/demo_pair.json") as f:
        demo_pair = json.load(f)

    df = load_cached("RELIANCE.NS")
    p_data = df_to_price_data("req-bench", df, ticker="RELIANCE.NS", source="cache")

    # Time Demo A
    t0 = time.perf_counter()
    res_a = execute_audit(demo_pair["demo_a"], p_data.dict())
    time_a = time.perf_counter() - t0

    # Time Demo B
    t0 = time.perf_counter()
    res_b = execute_audit(demo_pair["demo_b"], p_data.dict())
    time_b = time.perf_counter() - t0

    print(f"\n[Skeptic Audit Benchmark]")
    print(f"  Demo A Audit Runtime: {time_a:.2f}s (Verdict: {res_a['verdict']})")
    print(f"  Demo B Audit Runtime: {time_b:.2f}s (Verdict: {res_b['verdict']})")

    # Skeptic timeout budget is 60s; both must execute in well under 10s
    assert time_a < 15.0, f"Demo A took too long: {time_a:.2f}s"
    assert time_b < 15.0, f"Demo B took too long: {time_b:.2f}s"
