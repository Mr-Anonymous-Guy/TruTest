"""
TrustTest – Skeptic Engine (stub)
====================================
Adversarial audit logic. No agent code here.

TODO (Phase 2):
    - Implement run_audit() fully
    - OOS split (70/30 by date)
    - Parameter perturbation (+/-10 %, +/-20 %)
    - Cost sensitivity (2x fees+slippage)
    - Random-baseline Monte Carlo (1 000 runs)
    - Verdict logic: Trustworthy / Fragile / Likely Overfit
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .backtest import run_backtest

logger = logging.getLogger(__name__)

# Thresholds for the verdict
_MIN_TESTS_PASS_FRAC = 0.75   # ≥75 % of tests must pass → Trustworthy
_MC_BEAT_THRESHOLD = 0.60     # must beat >60 % of random baselines


def run_audit(
    df: pd.DataFrame,
    strategy_type: str,
    params: Dict[str, Any],
    fees_bps: float = 10.0,
    slippage_bps: float = 5.0,
    mc_runs: int = 1_000,
) -> Dict[str, Any]:
    """
    Run the full adversarial audit suite against the strategy.

    Returns
    -------
    dict matching the fields of AuditReport.

    Tests performed
    ---------------
    1. out_of_sample        – last 30 % of data
    2. cost_2x              – double fees and slippage
    3. param_perturb_p10    – each numeric param +10 %
    4. param_perturb_m10    – each numeric param -10 %
    5. param_perturb_p20    – each numeric param +20 %
    6. param_perturb_m20    – each numeric param -20 %
    7. monte_carlo          – 1 000 random-entry baselines

    TODO: implement fully in Phase 2.
    """
    raise NotImplementedError("run_audit() not yet implemented – Phase 2 work")


def oos_split(df: pd.DataFrame, train_frac: float = 0.70) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split df into in-sample and out-of-sample by date (no shuffling)."""
    n = len(df)
    split = int(n * train_frac)
    return df.iloc[:split], df.iloc[split:]


def perturb_params(params: Dict[str, Any], delta: float) -> Dict[str, Any]:
    """
    Return a copy of *params* with each numeric value multiplied by (1 + delta).
    delta = 0.10 → +10 %; delta = -0.20 → -20 %.
    """
    out = {}
    for k, v in params.items():
        if isinstance(v, (int, float)):
            new_val = v * (1 + delta)
            # Preserve int type if original was int
            out[k] = int(round(new_val)) if isinstance(v, int) else float(new_val)
        else:
            out[k] = v
    return out


def monte_carlo_baseline(
    df: pd.DataFrame,
    n_runs: int = 1_000,
    fees_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> Dict[str, float]:
    """
    Generate *n_runs* random-entry strategies and return summary stats
    (mean, std, p95 Sharpe).

    TODO: implement in Phase 2.
    """
    raise NotImplementedError("monte_carlo_baseline() – Phase 2")


def decide_verdict(
    tests: List[Dict[str, Any]],
    mc_beat_rate_pct: float,
) -> tuple[str, str]:
    """
    Given test results and MC beat rate, return (verdict, rationale).

    Verdict rules (apply in order):
        - If ≥75 % of tests pass AND mc_beat_rate_pct > 60 → "Trustworthy"
        - If ≥50 % pass → "Fragile"
        - Otherwise → "Likely Overfit"
    """
    total = len(tests)
    passed = sum(1 for t in tests if t.get("passed", False))
    pass_frac = passed / total if total > 0 else 0.0

    if pass_frac >= _MIN_TESTS_PASS_FRAC and mc_beat_rate_pct > 60:
        verdict = "Trustworthy"
        rationale = (
            f"{passed}/{total} robustness tests passed and the strategy beat "
            f"{mc_beat_rate_pct:.0f}% of random baselines."
        )
    elif pass_frac >= 0.50:
        verdict = "Fragile"
        rationale = (
            f"Only {passed}/{total} robustness tests passed. "
            "The strategy degrades under realistic stress."
        )
    else:
        verdict = "Likely Overfit"
        rationale = (
            f"Only {passed}/{total} tests passed. "
            "Performance collapses outside training conditions — classic overfit."
        )
    return verdict, rationale
