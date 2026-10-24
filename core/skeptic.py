"""
core/skeptic.py – Adversarial "Skeptic" Auditor
================================================
Pure-Python, offline, lookahead-free adversarial stress tests.
Four attacks:
  1. Out-of-sample (70/30 time split)
  2. Parameter perturbation (+/-10%, +/-20%)
  3. Cost sensitivity (2x friction)
  4. Random baseline (matched trade count and holding duration, 500 runs)
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .backtest import (
    STRATEGIES,
    BacktestResult,
    StrategySpec,
    run_backtest,
    run_backtest_positions,
)

# ---------------------------------------------------------------------------
# Single Source of Truth for Thresholds
# ---------------------------------------------------------------------------

THRESHOLDS: Dict[str, Any] = {
    "oos_split": 0.70,
    "oos_min_sharpe_ratio": 0.5,        # OOS Sharpe must be >= 50% of in-sample Sharpe
    "perturb_pcts": [-0.2, -0.1, 0.1, 0.2],
    "perturb_min_retention": 0.5,       # a neighbour "holds" if its Sharpe >= 50% of base Sharpe
    "perturb_min_pass_fraction": 0.7,   # at least 70% of neighbours must hold
    "cost_multiplier": 2.0,
    "cost_min_sharpe_ratio": 0.5,
    "random_n": 500,
    "random_percentile": 95,
    "random_seed": 42,
    "min_trades_warning": 8,
}


# ---------------------------------------------------------------------------
# Audit Report Dataclass
# ---------------------------------------------------------------------------

@dataclass
class AuditReport:
    verdict: str
    tests: List[Dict[str, Any]]
    base_metrics: Dict[str, Any]
    thresholds: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    disclaimer: str = (
        "Educational only. 'Trustworthy' means the strategy survived these stress tests, "
        "not that it will make money in live trading. Survivorship bias and structural market "
        "regime changes are not fully captured by historical data."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "tests": self.tests,
            "base_metrics": self.base_metrics,
            "thresholds": self.thresholds,
            "warnings": self.warnings,
            "disclaimer": self.disclaimer,
        }

    def summary_text(self) -> str:
        """Render clean plain-text summary report."""
        badge = f"[{self.verdict.upper()}]"
        lines = [
            "=" * 65,
            f"  TRUSTTEST AUDIT REPORT – VERDICT: {badge}",
            "=" * 65,
            f"Base Sharpe:        {self.base_metrics.get('sharpe', 0.0):.2f}",
            f"Base Total Return:  {self.base_metrics.get('total_return', 0.0) * 100.0:.1f}%",
            f"Base CAGR:          {self.base_metrics.get('cagr', 0.0) * 100.0:.1f}%",
            f"Max Drawdown:       {self.base_metrics.get('max_drawdown', 0.0) * 100.0:.1f}%",
            f"Trade Count:        {self.base_metrics.get('trade_count', 0)}",
            "-" * 65,
            "ADVERSARIAL STRESS TESTS:",
        ]
        for t in self.tests:
            status = "PASS" if t["passed"] else "FAIL"
            lines.append(f"  • {t['name']:<25} [{status}] {t['explanation']}")

        if self.warnings:
            lines.append("-" * 65)
            lines.append("WARNINGS:")
            for w in self.warnings:
                lines.append(f"  ! {w}")

        lines.append("-" * 65)
        lines.append(f"NOTE: {self.disclaimer}")
        lines.append("=" * 65)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Verdict Function
# ---------------------------------------------------------------------------

def verdict(tests: List[Dict[str, Any]], base_sharpe: float = 1.0) -> str:
    """
    Determine the audit verdict from attack results:
    - "Likely Overfit": random baseline fails, OR two or more of (out-of-sample, perturbation, cost) fail.
    - "Fragile": exactly one of (out-of-sample, perturbation, cost) fails and the random baseline passes.
    - "Trustworthy": all four pass.
    """
    if base_sharpe <= 0:
        return "Fragile"

    test_map = {t["name"]: t["passed"] for t in tests}
    random_pass = test_map.get("random_baseline", False)

    stress_tests = [
        test_map.get("out_of_sample", False),
        test_map.get("parameter_perturbation", False),
        test_map.get("cost_sensitivity", False),
    ]
    stress_fails = sum(1 for p in stress_tests if not p)

    if not random_pass or stress_fails >= 2:
        return "Likely Overfit"
    elif stress_fails == 1:
        return "Fragile"
    else:
        return "Trustworthy"


# ---------------------------------------------------------------------------
# Individual Attack Implementations
# ---------------------------------------------------------------------------

def attack_out_of_sample(
    df: pd.DataFrame,
    spec: StrategySpec,
    base_result: BacktestResult,
) -> Dict[str, Any]:
    """
    Split time series 70/30.
    Indicators computed on full series (past data only, zero leakage).
    Evaluate separately on in-sample and out-of-sample slices.
    """
    n = len(df)
    split_idx = int(n * THRESHOLDS["oos_split"])

    raw_signals = STRATEGIES[spec.strategy](df, **spec.params)
    shifted_positions = raw_signals.shift(1).fillna(0).astype(int).values

    close_vals = (df["close"] if "close" in df.columns else df["Close"]).values

    close_in = close_vals[:split_idx]
    pos_in = shifted_positions[:split_idx]

    close_out = close_vals[split_idx:]
    pos_out = shifted_positions[split_idx:]

    in_sharpe, in_ret, in_cagr = run_backtest_positions(close_in, pos_in, spec.fee_pct, spec.slippage_pct)
    oos_sharpe, oos_ret, oos_cagr = run_backtest_positions(close_out, pos_out, spec.fee_pct, spec.slippage_pct)

    if in_sharpe <= 0.0:
        passed = False
        explanation = f"In-sample Sharpe ({in_sharpe:.2f}) <= 0; strategy has no positive in-sample edge."
    else:
        required_sharpe = in_sharpe * THRESHOLDS["oos_min_sharpe_ratio"]
        passed = (oos_sharpe >= required_sharpe)
        if passed:
            explanation = f"OOS Sharpe is {oos_sharpe:.2f} (holds >= 50% of in-sample {in_sharpe:.2f})."
        else:
            explanation = f"OOS Sharpe is {oos_sharpe:.2f} (degrades below 50% of in-sample {in_sharpe:.2f})."

    return {
        "name": "out_of_sample",
        "passed": bool(passed),
        "in_sample_sharpe": float(round(in_sharpe, 3)),
        "oos_sharpe": float(round(oos_sharpe, 3)),
        "in_sample_cagr": float(round(in_cagr, 4)),
        "oos_cagr": float(round(oos_cagr, 4)),
        "explanation": explanation,
    }


def attack_parameter_perturbation(
    df: pd.DataFrame,
    spec: StrategySpec,
    base_result: BacktestResult,
) -> Dict[str, Any]:
    """
    Nudge every numeric parameter by +/-10% and +/-20%.
    Check if neighbour Sharpe >= 50% of base Sharpe.
    """
    base_sharpe = base_result.sharpe

    numeric_keys = [k for k, v in spec.params.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not numeric_keys:
        return {
            "name": "parameter_perturbation",
            "passed": True,
            "pass_fraction": 1.0,
            "total_neighbours": 0,
            "worst_sharpe": base_sharpe,
            "median_sharpe": base_sharpe,
            "explanation": "No numeric parameters to perturb.",
        }

    neighbour_specs: List[Dict[str, Any]] = []

    # 1. One parameter at a time
    for key in numeric_keys:
        val = spec.params[key]
        for delta in THRESHOLDS["perturb_pcts"]:
            new_val = val * (1.0 + delta)
            if isinstance(val, int):
                new_val = int(round(new_val))
            p_copy = dict(spec.params)
            p_copy[key] = new_val
            neighbour_specs.append(p_copy)

    # 2. All numeric parameters together
    for delta in THRESHOLDS["perturb_pcts"]:
        p_copy = dict(spec.params)
        for key in numeric_keys:
            val = spec.params[key]
            new_val = val * (1.0 + delta)
            if isinstance(val, int):
                new_val = int(round(new_val))
            p_copy[key] = new_val
        neighbour_specs.append(p_copy)

    # Filter invalid and deduplicate
    valid_neighbours: List[Dict[str, Any]] = []
    seen = set()
    for p in neighbour_specs:
        tup = tuple(sorted(p.items()))
        if tup == tuple(sorted(spec.params.items())) or tup in seen:
            continue

        # Strategy specific validity checks
        if spec.strategy == "ma_crossover":
            fast = p.get("fast", 50)
            slow = p.get("slow", 200)
            if fast <= 0 or slow <= 0 or fast >= slow:
                continue
        elif spec.strategy in ("rsi_meanrev", "rsi"):
            period = p.get("period", 14)
            oversold = p.get("oversold", 30.0)
            overbought = p.get("overbought", 70.0)
            if period <= 1 or oversold <= 0 or overbought >= 100 or oversold >= overbought:
                continue

        seen.add(tup)
        valid_neighbours.append(p)

    if not valid_neighbours:
        return {
            "name": "parameter_perturbation",
            "passed": True,
            "pass_fraction": 1.0,
            "total_neighbours": 0,
            "worst_sharpe": base_sharpe,
            "median_sharpe": base_sharpe,
            "explanation": "No valid perturbed neighbour parameters found.",
        }

    neighbour_sharpes: List[float] = []
    min_required = base_sharpe * THRESHOLDS["perturb_min_retention"] if base_sharpe > 0 else 0.0

    for p in valid_neighbours:
        try:
            sub_spec = StrategySpec(
                ticker=spec.ticker,
                strategy=spec.strategy,
                params=p,
                fee_pct=spec.fee_pct,
                slippage_pct=spec.slippage_pct,
                start=spec.start,
                end=spec.end,
            )
            res = run_backtest(df, sub_spec)
            neighbour_sharpes.append(res.sharpe)
        except Exception:
            continue

    if not neighbour_sharpes:
        return {
            "name": "parameter_perturbation",
            "passed": False,
            "pass_fraction": 0.0,
            "total_neighbours": len(valid_neighbours),
            "worst_sharpe": 0.0,
            "median_sharpe": 0.0,
            "explanation": "All neighbour parameter runs failed.",
        }

    worst_sharpe = float(np.min(neighbour_sharpes))
    median_sharpe = float(np.median(neighbour_sharpes))

    if base_sharpe <= 0:
        return {
            "name": "parameter_perturbation",
            "passed": False,
            "pass_fraction": 0.0,
            "total_neighbours": len(neighbour_sharpes),
            "worst_sharpe": worst_sharpe,
            "median_sharpe": median_sharpe,
            "explanation": f"Base Sharpe is non-positive ({base_sharpe:.2f}); cannot evaluate stability.",
        }

    holding_count = sum(1 for s in neighbour_sharpes if s >= min_required)
    pass_fraction = holding_count / len(neighbour_sharpes)
    passed = (pass_fraction >= THRESHOLDS["perturb_min_pass_fraction"])

    if passed:
        explanation = (
            f"{pass_fraction * 100:.0f}% of neighbours held >= 50% of Sharpe "
            f"(median {median_sharpe:.2f}, worst {worst_sharpe:.2f})."
        )
    else:
        explanation = (
            f"Only {pass_fraction * 100:.0f}% of neighbours held (needed {THRESHOLDS['perturb_min_pass_fraction']*100:.0f}%, "
            f"worst collapsed to {worst_sharpe:.2f})."
        )

    return {
        "name": "parameter_perturbation",
        "passed": bool(passed),
        "pass_fraction": float(round(pass_fraction, 3)),
        "total_neighbours": len(neighbour_sharpes),
        "worst_sharpe": float(round(worst_sharpe, 3)),
        "median_sharpe": float(round(median_sharpe, 3)),
        "explanation": explanation,
    }


def attack_cost_sensitivity(
    df: pd.DataFrame,
    spec: StrategySpec,
    base_result: BacktestResult,
) -> Dict[str, Any]:
    """
    Rerun with fees and slippage multiplied by cost_multiplier (2.0x).
    Pass if CAGR > 0 and Sharpe >= 50% of base Sharpe.
    """
    base_sharpe = base_result.sharpe
    mult = THRESHOLDS["cost_multiplier"]
    cost_spec = StrategySpec(
        ticker=spec.ticker,
        strategy=spec.strategy,
        params=spec.params,
        fee_pct=spec.fee_pct * mult,
        slippage_pct=spec.slippage_pct * mult,
        start=spec.start,
        end=spec.end,
    )
    cost_res = run_backtest(df, cost_spec)

    cost_sharpe = cost_res.sharpe
    cost_cagr = cost_res.cagr

    if base_sharpe <= 0:
        passed = False
        explanation = f"Base Sharpe is non-positive ({base_sharpe:.2f}); cost stress test failed."
    else:
        req_sharpe = base_sharpe * THRESHOLDS["cost_min_sharpe_ratio"]
        passed = (cost_cagr > 0.0) and (cost_sharpe >= req_sharpe)
        if passed:
            explanation = (
                f"With 2x friction ({cost_spec.fee_pct:.2f}% fee, {cost_spec.slippage_pct:.2f}% slip), "
                f"Sharpe is {cost_sharpe:.2f} and CAGR is {cost_cagr * 100:.1f}%."
            )
        else:
            explanation = (
                f"With 2x friction, Sharpe dropped to {cost_sharpe:.2f} and CAGR to {cost_cagr * 100:.1f}%."
            )

    return {
        "name": "cost_sensitivity",
        "passed": bool(passed),
        "cost_sharpe": float(round(cost_sharpe, 3)),
        "cost_cagr": float(round(cost_cagr, 4)),
        "explanation": explanation,
    }


def attack_random_baseline(
    df: pd.DataFrame,
    spec: StrategySpec,
    base_result: BacktestResult,
) -> Dict[str, Any]:
    """
    Generate random_n random long-only strategies with:
    - Same number of trades
    - Same average holding length
    - Random entry dates, same costs
    - Fixed seed for reproducibility.
    Pass if strategy Sharpe exceeds the 95th percentile.
    """
    base_sharpe = base_result.sharpe
    close_vals = (df["close"] if "close" in df.columns else df["Close"]).values
    n = len(close_vals)
    trade_count = base_result.trade_count

    if trade_count == 0 or base_sharpe <= 0 or n < 10:
        return {
            "name": "random_baseline",
            "passed": False,
            "percentile": 0.0,
            "p95_sharpe": 0.0,
            "mean_sharpe": 0.0,
            "explanation": f"Strategy has {trade_count} trades or non-positive Sharpe; fails random benchmark.",
        }

    # Average holding duration
    total_bars_in_position = int(np.sum(base_result.positions))
    avg_holding = max(1, int(round(total_bars_in_position / trade_count)))

    rng = np.random.default_rng(THRESHOLDS["random_seed"])
    n_runs = THRESHOLDS["random_n"]
    random_sharpes: List[float] = []

    # Vectorized / looped generator for random positions matching trade count and holding duration
    for _ in range(n_runs):
        pos = np.zeros(n, dtype=int)
        # Pick trade_count random entry bars
        valid_max_entry = max(1, n - avg_holding - 1)
        entries = rng.choice(valid_max_entry, size=min(trade_count, valid_max_entry), replace=False)
        for e in entries:
            pos[e : min(n, e + avg_holding)] = 1

        sh, tot, cg = run_backtest_positions(close_vals, pos, spec.fee_pct, spec.slippage_pct)
        random_sharpes.append(sh)

    sharpes_arr = np.array(random_sharpes)
    p95 = float(np.percentile(sharpes_arr, THRESHOLDS["random_percentile"]))
    mean_s = float(np.mean(sharpes_arr))

    percentile_rank = float(np.mean(base_sharpe > sharpes_arr) * 100.0)
    passed = (percentile_rank >= float(THRESHOLDS["random_percentile"]))

    if passed:
        explanation = (
            f"Beats {percentile_rank:.1f}% of {n_runs} random baselines "
            f"(exceeds 95th %ile Sharpe: {p95:.2f})."
        )
    else:
        explanation = (
            f"Only beats {percentile_rank:.1f}% of {n_runs} random baselines "
            f"(needs >= 95.0%, 95th %ile was {p95:.2f})."
        )

    return {
        "name": "random_baseline",
        "passed": bool(passed),
        "percentile": float(round(percentile_rank, 1)),
        "p95_sharpe": float(round(p95, 3)),
        "mean_sharpe": float(round(mean_s, 3)),
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Public Audit API
# ---------------------------------------------------------------------------

def audit(df: pd.DataFrame, spec: StrategySpec) -> AuditReport:
    """
    Run the full adversarial quant audit suite against a StrategySpec.
    Returns an AuditReport with individual attack results, warnings, and verdict.
    """
    base_res = run_backtest(df, spec)

    # Run the 4 adversarial attacks
    t1 = attack_out_of_sample(df, spec, base_res)
    t2 = attack_parameter_perturbation(df, spec, base_res)
    t3 = attack_cost_sensitivity(df, spec, base_res)
    t4 = attack_random_baseline(df, spec, base_res)

    tests = [t1, t2, t3, t4]

    # Evaluate verdict
    verd = verdict(tests, base_res.sharpe)

    # Check warnings
    warnings: List[str] = []
    if base_res.trade_count < THRESHOLDS["min_trades_warning"]:
        warnings.append(
            f"Only {base_res.trade_count} trades executed: statistical sample is low "
            f"(recommended minimum: {THRESHOLDS['min_trades_warning']})."
        )

    if base_res.sharpe <= 0:
        warnings.append(f"Base strategy has non-positive Sharpe ({base_res.sharpe:.2f}); no edge found.")

    base_metrics = {
        "total_return": base_res.total_return,
        "cagr": base_res.cagr,
        "sharpe": base_res.sharpe,
        "max_drawdown": base_res.max_drawdown,
        "trade_count": base_res.trade_count,
        "exposure": base_res.exposure,
        "win_rate": base_res.win_rate,
    }

    return AuditReport(
        verdict=verd,
        tests=tests,
        base_metrics=base_metrics,
        thresholds=dict(THRESHOLDS),
        warnings=warnings,
    )
