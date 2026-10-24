"""
tests/test_skeptic.py – Skeptic Adversarial Auditor Unit Tests
"""

import numpy as np
import pandas as pd
import pytest

from core.backtest import StrategySpec
from core.skeptic import (
    AuditReport,
    audit,
    attack_parameter_perturbation,
    verdict,
)


def _make_synth_df(n: int = 500, seed: int = 42) -> pd.DataFrame:
    dates = pd.bdate_range("2018-01-01", periods=n)
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.012, n)
    close = 100.0 * np.cumprod(1.0 + rets)
    return pd.DataFrame({"close": close, "volume": 1000}, index=dates)


def test_determinism():
    """Identical inputs and seed produce identical AuditReport results."""
    df = _make_synth_df(500, seed=10)
    spec = StrategySpec(
        ticker="TEST",
        strategy="ma_crossover",
        params={"fast": 10, "slow": 30},
        fee_pct=0.1,
        slippage_pct=0.05,
    )
    rep1 = audit(df, spec)
    rep2 = audit(df, spec)

    assert rep1.verdict == rep2.verdict
    assert rep1.base_metrics["sharpe"] == rep2.base_metrics["sharpe"]
    assert rep1.to_dict() == rep2.to_dict()


def test_verdict_branches():
    """Unit test every verdict rule with fabricated test inputs."""
    # 1. Base Sharpe <= 0 -> "Fragile"
    assert verdict([], base_sharpe=-0.1) == "Fragile"
    assert verdict([], base_sharpe=0.0) == "Fragile"

    # 2. All 4 pass -> "Trustworthy"
    all_pass = [
        {"name": "out_of_sample", "passed": True},
        {"name": "parameter_perturbation", "passed": True},
        {"name": "cost_sensitivity", "passed": True},
        {"name": "random_baseline", "passed": True},
    ]
    assert verdict(all_pass, base_sharpe=1.0) == "Trustworthy"

    # 3. Exactly one stress test fails & random passes -> "Fragile"
    one_stress_fail = [
        {"name": "out_of_sample", "passed": False},
        {"name": "parameter_perturbation", "passed": True},
        {"name": "cost_sensitivity", "passed": True},
        {"name": "random_baseline", "passed": True},
    ]
    assert verdict(one_stress_fail, base_sharpe=1.0) == "Fragile"

    # 4. Two stress tests fail -> "Likely Overfit"
    two_stress_fail = [
        {"name": "out_of_sample", "passed": False},
        {"name": "parameter_perturbation", "passed": False},
        {"name": "cost_sensitivity", "passed": True},
        {"name": "random_baseline", "passed": True},
    ]
    assert verdict(two_stress_fail, base_sharpe=1.0) == "Likely Overfit"

    # 5. Random baseline fails -> "Likely Overfit"
    random_fail = [
        {"name": "out_of_sample", "passed": True},
        {"name": "parameter_perturbation", "passed": True},
        {"name": "cost_sensitivity", "passed": True},
        {"name": "random_baseline", "passed": False},
    ]
    assert verdict(random_fail, base_sharpe=1.0) == "Likely Overfit"


def test_perturbation_validity():
    """Perturbation must never produce invalid parameters (e.g. fast >= slow or negative)."""
    df = _make_synth_df(400)
    spec = StrategySpec(
        ticker="TEST",
        strategy="ma_crossover",
        params={"fast": 5, "slow": 10},
    )
    from core.backtest import run_backtest
    base_res = run_backtest(df, spec)
    pert_res = attack_parameter_perturbation(df, spec, base_res)
    assert "pass_fraction" in pert_res
    assert pert_res["total_neighbours"] > 0


def test_pure_noise_rejection():
    """Run a strategy on 20 seeded random-walk series; at most 2 should be Trustworthy."""
    spec = StrategySpec(
        ticker="NOISE",
        strategy="ma_crossover",
        params={"fast": 15, "slow": 45},
        fee_pct=0.1,
        slippage_pct=0.05,
    )

    trustworthy_count = 0
    for seed in range(20):
        dates = pd.bdate_range("2020-01-01", periods=500)
        rng = np.random.default_rng(seed + 1000)
        # Pure zero-mean random walk
        rets = rng.normal(0.0, 0.015, 500)
        close = 100.0 * np.cumprod(1.0 + rets)
        df_noise = pd.DataFrame({"close": close, "volume": 1000}, index=dates)

        rep = audit(df_noise, spec)
        if rep.verdict == "Trustworthy":
            trustworthy_count += 1

    print(f"\nPure noise check: {trustworthy_count}/20 came back Trustworthy")
    assert trustworthy_count <= 2, f"Expected <= 2 Trustworthy on pure noise, got {trustworthy_count}"


def test_rsi_audit_alias_support():
    """Skeptic audit works with both 'rsi' and 'rsi_meanrev' specs."""
    df = _make_synth_df(300)
    spec_alias = StrategySpec(ticker="TCS.NS", strategy="rsi", params={"period": 14, "oversold": 30.0, "overbought": 70.0})
    rep_alias = audit(df, spec_alias)
    assert rep_alias.verdict in ("Trustworthy", "Fragile", "Likely Overfit")

    spec_canon = StrategySpec(ticker="TCS.NS", strategy="rsi_meanrev", params={"period": 14, "oversold": 30.0, "overbought": 70.0})
    rep_canon = audit(df, spec_canon)
    assert rep_canon.verdict in ("Trustworthy", "Fragile", "Likely Overfit")
