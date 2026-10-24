"""
scripts/demo_pair.py – Demo Pair Generator & Auditor for TrustTest

Generates and audits Demo A (50/200 MA crossover) and Demo B (over-tuned
in-sample MA crossover) on the last 5 years of RELIANCE.NS cached data.
Outputs a side-by-side comparison table and writes:
- data/demo_pair.json
- data/demo_pair_results.json
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(str(Path(__file__).resolve().parent.parent)))

import pandas as pd
from core.backtest import (
    STRATEGIES,
    StrategySpec,
    run_backtest,
    run_backtest_positions,
)
from core.data import load_cached
from core.skeptic import THRESHOLDS, audit


def find_overfit_params(df_5y: pd.DataFrame, fee_pct: float = 0.1, slippage_pct: float = 0.05) -> dict:
    """
    Grid-search MA crossover parameters on the first 70% in-sample window
    (fast 3 to 60, slow 20 to 250) to maximize in-sample Sharpe ratio.
    """
    n = len(df_5y)
    split_idx = int(n * THRESHOLDS["oos_split"])
    close_vals = df_5y["close"].values
    close_in = close_vals[:split_idx]

    best_sharpe = -999.0
    best_params = {"fast": 20, "slow": 50}

    for slow in range(20, 251, 5):
        for fast in range(3, min(61, slow)):
            raw_sig = STRATEGIES["ma_crossover"](df_5y, fast=fast, slow=slow)
            shifted_pos = raw_sig.shift(1).fillna(0).astype(int).values
            pos_in = shifted_pos[:split_idx]
            sh, tot, cg = run_backtest_positions(close_in, pos_in, fee_pct=fee_pct, slippage_pct=slippage_pct)
            if sh > best_sharpe:
                best_sharpe = sh
                best_params = {"fast": int(fast), "slow": int(slow)}

    return best_params


def main():
    print("Loading cached RELIANCE.NS data...")
    df = load_cached("RELIANCE.NS")

    # Last 5 years window
    start_dt = df.index[-1] - pd.DateOffset(years=5)
    df_5y = df[df.index >= start_dt].copy()
    start_str = str(df_5y.index[0].date())
    end_str = str(df_5y.index[-1].date())
    print(f"5-Year Window: {start_str} to {end_str} ({len(df_5y)} bars)")

    # 1. Demo A: Standard 50/200 MA crossover
    spec_a = StrategySpec(
        ticker="RELIANCE.NS",
        strategy="ma_crossover",
        params={"fast": 50, "slow": 200},
        fee_pct=0.1,
        slippage_pct=0.05,
        start=start_str,
        end=end_str,
    )

    # 2. Demo B: In-Sample Optimized / Over-Tuned MA crossover
    print("Running in-sample grid search for Demo B...")
    best_params_b = find_overfit_params(df_5y, fee_pct=0.1, slippage_pct=0.05)
    print(f"Found over-tuned parameters for Demo B: {best_params_b}")

    spec_b = StrategySpec(
        ticker="RELIANCE.NS",
        strategy="ma_crossover",
        params=best_params_b,
        fee_pct=0.1,
        slippage_pct=0.05,
        start=start_str,
        end=end_str,
    )

    # Audit both
    print("\nAuditing Demo A through Skeptic Engine...")
    rep_a = audit(df_5y, spec_a)

    print("Auditing Demo B through Skeptic Engine...")
    rep_b = audit(df_5y, spec_b)

    # Helper maps for tests
    t_map_a = {t["name"]: t for t in rep_a.tests}
    t_map_b = {t["name"]: t for t in rep_b.tests}

    # Format side-by-side table
    print("\n" + "=" * 80)
    print("TRUSTTEST DEMO PAIR: QUANT AUDIT COMPARISON")
    print("=" * 80)
    header_fmt = "{:<32} | {:<22} | {:<22}"
    row_fmt    = "{:<32} | {:<22} | {:<22}"

    print(header_fmt.format("Metric / Test", "Demo A (50/200 SMA)", f"Demo B ({spec_b.params['fast']}/{spec_b.params['slow']} Over-tuned)"))
    print("-" * 80)
    print(row_fmt.format("Ticker & Window", "RELIANCE.NS (5 Yrs)", "RELIANCE.NS (5 Yrs)"))
    print(row_fmt.format("Headline Return", f"{rep_a.base_metrics['total_return']*100:+.2f}%", f"{rep_b.base_metrics['total_return']*100:+.2f}%"))
    print(row_fmt.format("Headline CAGR", f"{rep_a.base_metrics['cagr']*100:+.2f}%", f"{rep_b.base_metrics['cagr']*100:+.2f}%"))
    print(row_fmt.format("Headline Sharpe", f"{rep_a.base_metrics['sharpe']:.2f}", f"{rep_b.base_metrics['sharpe']:.2f}"))
    print(row_fmt.format("Trades Count", str(rep_a.base_metrics['trade_count']), str(rep_b.base_metrics['trade_count'])))
    print(row_fmt.format("Exposure", f"{rep_a.base_metrics['exposure']*100:.1f}%", f"{rep_b.base_metrics['exposure']*100:.1f}%"))
    print("-" * 80)

    # Attack 1: Out of Sample
    oos_a = t_map_a.get("out_of_sample", {})
    oos_b = t_map_b.get("out_of_sample", {})
    oos_a_str = f"{'PASS' if oos_a.get('passed') else 'FAIL'} (IS:{oos_a.get('in_sample_sharpe',0):.2f}/OOS:{oos_a.get('oos_sharpe',0):.2f})"
    oos_b_str = f"{'PASS' if oos_b.get('passed') else 'FAIL'} (IS:{oos_b.get('in_sample_sharpe',0):.2f}/OOS:{oos_b.get('oos_sharpe',0):.2f})"
    print(row_fmt.format("1. Out-of-Sample (70/30)", oos_a_str, oos_b_str))

    # Attack 2: Parameter Perturbation
    pert_a = t_map_a.get("parameter_perturbation", {})
    pert_b = t_map_b.get("parameter_perturbation", {})
    pert_a_str = f"{'PASS' if pert_a.get('passed') else 'FAIL'} ({pert_a.get('pass_fraction',0)*100:.0f}% held)"
    pert_b_str = f"{'PASS' if pert_b.get('passed') else 'FAIL'} ({pert_b.get('pass_fraction',0)*100:.0f}% held)"
    print(row_fmt.format("2. Param Perturbation", pert_a_str, pert_b_str))

    # Attack 3: Cost Sensitivity
    cost_a = t_map_a.get("cost_sensitivity", {})
    cost_b = t_map_b.get("cost_sensitivity", {})
    cost_a_str = f"{'PASS' if cost_a.get('passed') else 'FAIL'} (Sh:{cost_a.get('cost_sharpe',0):.2f}, Ret:{cost_a.get('cost_cagr',0)*100:.1f}%)"
    cost_b_str = f"{'PASS' if cost_b.get('passed') else 'FAIL'} (Sh:{cost_b.get('cost_sharpe',0):.2f}, Ret:{cost_b.get('cost_cagr',0)*100:.1f}%)"
    print(row_fmt.format("3. Cost Stress (2x Fees)", cost_a_str, cost_b_str))

    # Attack 4: Random Baseline
    rand_a = t_map_a.get("random_baseline", {})
    rand_b = t_map_b.get("random_baseline", {})
    rand_a_str = f"{'PASS' if rand_a.get('passed') else 'FAIL'} ({rand_a.get('percentile',0):.1f}%ile)"
    rand_b_str = f"{'PASS' if rand_b.get('passed') else 'FAIL'} ({rand_b.get('percentile',0):.1f}%ile)"
    print(row_fmt.format("4. Random Baseline (95th %ile)", rand_a_str, rand_b_str))

    print("-" * 80)
    print(row_fmt.format("FINAL VERDICT", rep_a.verdict.upper(), rep_b.verdict.upper()))
    print("=" * 80)

    # Save to JSON
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)

    pair_specs = {
        "demo_a": spec_a.to_dict(),
        "demo_b": spec_b.to_dict(),
    }
    with open(out_dir / "demo_pair.json", "w", encoding="utf-8") as f:
        json.dump(pair_specs, f, indent=2)
    print(f"\nSaved strategy specifications to {out_dir / 'demo_pair.json'}")

    pair_results = {
        "demo_a": rep_a.to_dict(),
        "demo_b": rep_b.to_dict(),
    }
    with open(out_dir / "demo_pair_results.json", "w", encoding="utf-8") as f:
        json.dump(pair_results, f, indent=2)
    print(f"Saved audit results to {out_dir / 'demo_pair_results.json'}")


if __name__ == "__main__":
    main()
