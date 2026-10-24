"""
TrustTest – Skeptic Engine
==========================
Adversarial audit logic for backtested trading strategies.
Pure-Python / pandas implementation. No agent code here.

Tests performed:
    1. out_of_sample        – last 30 % of data (no data leakage)
    2. cost_2x              – double fees and slippage
    3. param_perturb_p10    – each numeric param +10 %
    4. param_perturb_m10    – each numeric param -10 %
    5. param_perturb_p20    – each numeric param +20 %
    6. param_perturb_m20    – each numeric param -20 %
    7. monte_carlo          – 1 000 random-entry baselines
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from .backtest import run_backtest

logger = logging.getLogger(__name__)

# Thresholds for the verdict
_MIN_TESTS_PASS_FRAC = 0.75   # >= 75 % of tests must pass -> Trustworthy
_MC_BEAT_THRESHOLD = 60.0     # must beat > 60 % of random baselines


def oos_split(df: pd.DataFrame, train_frac: float = 0.70) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split df into in-sample and out-of-sample by date (no shuffling)."""
    n = len(df)
    split = int(n * train_frac)
    return df.iloc[:split], df.iloc[split:]


def perturb_params(params: Dict[str, Any], delta: float) -> Dict[str, Any]:
    """
    Return a copy of *params* with each numeric value multiplied by (1 + delta).
    delta = 0.10 -> +10 %; delta = -0.20 -> -20 %.
    """
    out = {}
    for k, v in params.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
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
    risk_free_rate: float = 0.05,
    trading_days_per_year: int = 252,
) -> Dict[str, Any]:
    """
    Generate *n_runs* random-entry strategies and return summary stats
    (mean, std, p95 Sharpe, and full sharpes array).
    """
    n = len(df)
    if n < 10:
        return {
            "mean_sharpe": 0.0,
            "std_sharpe": 0.0,
            "p95_sharpe": 0.0,
            "sharpes": np.zeros(n_runs),
        }

    close = df["Close"].values
    asset_returns = np.diff(close) / close[:-1]

    rng = np.random.default_rng(42)
    p_enter = 0.05
    p_exit = 0.05

    signals = np.zeros((n_runs, n), dtype=int)
    for t in range(1, n):
        prev = signals[:, t - 1]
        enter_flip = rng.random(n_runs) < p_enter
        exit_flip = rng.random(n_runs) < p_exit
        signals[:, t] = np.where(prev == 0, enter_flip.astype(int), (~exit_flip).astype(int))

    # Shift signals by 1 bar
    shifted = signals[:, :-1]
    trade_diff = np.diff(signals, axis=1)
    cost_frac = (fees_bps + slippage_bps) / 10000.0
    cost_drag = np.abs(trade_diff) * cost_frac

    strat_rets = (shifted * asset_returns) - cost_drag
    excess_daily = np.mean(strat_rets, axis=1) - (risk_free_rate / trading_days_per_year)
    stds = np.std(strat_rets, axis=1)
    stds[stds < 1e-9] = 1e-9
    sharpes = (excess_daily / stds) * np.sqrt(trading_days_per_year)

    return {
        "mean_sharpe": float(np.mean(sharpes)),
        "std_sharpe": float(np.std(sharpes)),
        "p95_sharpe": float(np.percentile(sharpes, 95)),
        "sharpes": sharpes,
    }


def decide_verdict(
    tests: List[Dict[str, Any]],
    mc_beat_rate_pct: float,
) -> Tuple[str, str]:
    """
    Given test results and MC beat rate, return (verdict, rationale).

    Verdict rules (apply in order):
        - If >= 75 % of tests pass AND mc_beat_rate_pct > 60 -> "Trustworthy"
        - If >= 50 % pass -> "Fragile"
        - Otherwise -> "Likely Overfit"
    """
    total = len(tests)
    passed = sum(1 for t in tests if t.get("passed", False))
    pass_frac = passed / total if total > 0 else 0.0

    if pass_frac >= _MIN_TESTS_PASS_FRAC and mc_beat_rate_pct > _MC_BEAT_THRESHOLD:
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
    """
    baseline = run_backtest(df, strategy_type, params, fees_bps, slippage_bps)
    base_sharpe = baseline["sharpe_ratio"]

    tests: List[Dict[str, Any]] = []

    # 1. Out-of-sample (last 30%)
    _, test_df = oos_split(df, train_frac=0.70)
    oos_res = run_backtest(test_df, strategy_type, params, fees_bps, slippage_bps)
    oos_sharpe = oos_res["sharpe_ratio"]
    oos_passed = oos_sharpe > 0 and (oos_sharpe >= 0.3 * base_sharpe if base_sharpe > 0 else True)
    tests.append({
        "name": "out_of_sample",
        "sharpe_ratio": oos_sharpe,
        "cagr_pct": oos_res["cagr_pct"],
        "max_drawdown_pct": oos_res["max_drawdown_pct"],
        "passed": bool(oos_passed),
        "note": f"OOS Sharpe is {oos_sharpe:.2f} (baseline: {base_sharpe:.2f})",
    })

    # 2. Cost 2x sensitivity
    cost_res = run_backtest(df, strategy_type, params, fees_bps * 2.0, slippage_bps * 2.0)
    cost_sharpe = cost_res["sharpe_ratio"]
    cost_passed = cost_sharpe > 0 and cost_res["total_return_pct"] > 0
    tests.append({
        "name": "cost_2x",
        "sharpe_ratio": cost_sharpe,
        "cagr_pct": cost_res["cagr_pct"],
        "max_drawdown_pct": cost_res["max_drawdown_pct"],
        "passed": bool(cost_passed),
        "note": f"Double costs ({fees_bps * 2:.0f}+{slippage_bps * 2:.0f} bps) Sharpe: {cost_sharpe:.2f}",
    })

    # 3-6. Parameter perturbation (+/-10%, +/-20%)
    perturbations = [
        ("param_perturb_p10", 0.10, "+10% params"),
        ("param_perturb_m10", -0.10, "-10% params"),
        ("param_perturb_p20", 0.20, "+20% params"),
        ("param_perturb_m20", -0.20, "-20% params"),
    ]
    for test_name, delta, label in perturbations:
        pert_params = perturb_params(params, delta)
        pert_res = run_backtest(df, strategy_type, pert_params, fees_bps, slippage_bps)
        pert_sharpe = pert_res["sharpe_ratio"]
        # Passes if not catastrophic drop
        pert_passed = pert_sharpe > 0 and (pert_sharpe >= 0.3 * base_sharpe if base_sharpe > 0 else True)
        tests.append({
            "name": test_name,
            "sharpe_ratio": pert_sharpe,
            "cagr_pct": pert_res["cagr_pct"],
            "max_drawdown_pct": pert_res["max_drawdown_pct"],
            "passed": bool(pert_passed),
            "note": f"{label} yields Sharpe {pert_sharpe:.2f}",
        })

    # 7. Monte Carlo benchmark
    mc_stats = monte_carlo_baseline(df, n_runs=mc_runs, fees_bps=fees_bps, slippage_bps=slippage_bps)
    mc_sharpes = mc_stats["sharpes"]
    mc_beat_rate_pct = float(np.mean(base_sharpe > mc_sharpes) * 100.0)
    p95_sharpe = float(mc_stats["p95_sharpe"])
    mc_passed = mc_beat_rate_pct > _MC_BEAT_THRESHOLD
    tests.append({
        "name": "monte_carlo",
        "sharpe_ratio": base_sharpe,
        "cagr_pct": baseline["cagr_pct"],
        "max_drawdown_pct": baseline["max_drawdown_pct"],
        "passed": bool(mc_passed),
        "note": f"Beats {mc_beat_rate_pct:.1f}% of {mc_runs} random runs (95th %ile Sharpe: {p95_sharpe:.2f})",
    })

    verdict, rationale = decide_verdict(tests, mc_beat_rate_pct)
    tests_passed = sum(1 for t in tests if t["passed"])

    return {
        "ticker": params.get("ticker", ""),
        "strategy_type": strategy_type,
        "tests": tests,
        "mc_p95_sharpe": round(p95_sharpe, 2),
        "mc_beat_rate_pct": round(mc_beat_rate_pct, 1),
        "verdict": verdict,
        "verdict_rationale": rationale,
        "tests_passed": tests_passed,
        "tests_total": len(tests),
    }
