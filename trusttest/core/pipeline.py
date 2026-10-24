"""
TrustTest – Pipeline Runner & Result Formatter
=============================================
Orchestrates:
  1. Plain-English Parsing (Parser)
  2. Market Data Retrieval (Data Loader with Cache Fallback)
  3. Backtesting (Shifted Signals, Fees/Slippage)
  4. Adversarial Audit (Skeptic OOS, Perturb, Cost, Monte Carlo)
  5. Interactive Markdown Result Card Formatting
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from trusttest.agents.parser_agent import parse_strategy
from trusttest.core.backtest import run_backtest
from trusttest.core.data_loader import load_prices
from trusttest.core.models import StrategySpec
from trusttest.core.skeptic import run_audit

logger = logging.getLogger(__name__)


def format_result_card(
    spec: StrategySpec,
    backtest: Dict[str, Any],
    audit: Dict[str, Any],
    data_source: str = "cache",
) -> str:
    """Format backtest result and Skeptic audit as an interactive markdown card."""
    verdict = audit.get("verdict", "Fragile")
    if verdict == "Trustworthy":
        badge = "✅ **Trustworthy**"
    elif verdict == "Fragile":
        badge = "⚠️ **Fragile**"
    else:
        badge = "❌ **Likely Overfit**"

    strat_title = spec.strategy_type.replace("_", " ").title()
    params_str = ", ".join(f"{k}={v}" for k, v in spec.params.items())

    # Build stress test table rows
    tests_rows = []
    for t in audit.get("tests", []):
        name = t.get("name", "").replace("_", " ").title()
        status = "✅ Pass" if t.get("passed", False) else "❌ Fail"
        note = t.get("note", "")
        tests_rows.append(f"| **{name}** | {status} | {note} |")
    tests_table = "\n".join(tests_rows)

    source_tag = "🔴 Live (yfinance)" if data_source == "live" else "🟢 Cached (data/cache)"

    card = f"""## 🛡️ TrustTest Audit Report

### Strategy: **{strat_title}** on `{spec.ticker}`
- **Parameters:** `{params_str}`
- **Backtest Window:** `{spec.start}` → `{spec.end}`
- **Assumed Costs:** `{spec.fees_bps:.0f} bps fees` + `{spec.slippage_bps:.0f} bps slippage` (per trade)
- **Data Source:** {source_tag}

---

### 📊 Performance Metrics
| Metric | Result | Benchmark / Notes |
| :--- | :--- | :--- |
| **Sharpe Ratio** | **`{backtest.get('sharpe_ratio', 0.0):.2f}`** | Risk-free rate: 5% |
| **CAGR** | **`{backtest.get('cagr_pct', 0.0):.1f}%`** | Annualized compounded growth |
| **Total Return** | **`{backtest.get('total_return_pct', 0.0):.1f}%`** | Net of fees & slippage |
| **Max Drawdown** | **`{backtest.get('max_drawdown_pct', 0.0):.1f}%`** | Peak-to-trough decline |
| **Trade Count** | **`{backtest.get('trade_count', 0)}`** | Shifted 1-bar execution |
| **Win Rate** | **`{backtest.get('win_rate_pct', 0.0):.1f}%`** | Profitable trades |

---

### 🧐 Skeptic Adversarial Audit
#### Verdict: {badge}
> *"{audit.get('verdict_rationale', '')}"*

**Robustness Stress Tests ({audit.get('tests_passed', 0)}/{audit.get('tests_total', 0)} passed):**

| Test | Status | Finding |
| :--- | :---: | :--- |
{tests_table}

**Monte Carlo Benchmark:**
Strategy beats **{audit.get('mc_beat_rate_pct', 0.0):.1f}%** of 1,000 random-entry baselines (95th percentile Sharpe: `{audit.get('mc_p95_sharpe', 0.0):.2f}`).

---
⚠️ **Disclaimer:** *TrustTest is strictly an educational tool demonstrating multi-agent adversarial strategy auditing. It does NOT constitute financial or investment advice.*
"""
    return card


def run_pipeline(user_text: str) -> str:
    """
    Execute the entire 5-step pipeline:
    1. Parse plain English -> StrategySpec
    2. Load market data (live/cache)
    3. Run backtest engine
    4. Run Skeptic audit suite
    5. Return formatted markdown card
    """
    try:
        # Step 1: Parse
        spec = parse_strategy(user_text)
        logger.info("Pipeline parsed strategy: %s on %s", spec.strategy_type, spec.ticker)

        # Step 2: Market data
        df, source = load_prices(spec.ticker, spec.start, spec.end)
        logger.info("Pipeline loaded %d rows for %s (%s)", len(df), spec.ticker, source)

        # Step 3: Backtest
        backtest_res = run_backtest(
            df=df,
            strategy_type=spec.strategy_type,
            params=spec.params,
            fees_bps=spec.fees_bps,
            slippage_bps=spec.slippage_bps,
        )

        # Step 4: Skeptic Audit
        audit_res = run_audit(
            df=df,
            strategy_type=spec.strategy_type,
            params=spec.params,
            fees_bps=spec.fees_bps,
            slippage_bps=spec.slippage_bps,
            mc_runs=500,
        )

        # Step 5: Format result card
        return format_result_card(spec, backtest_res, audit_res, data_source=source)

    except Exception as exc:
        logger.error("Pipeline execution failed: %s", exc, exc_info=True)
        return (
            f"❌ **TrustTest Error**\n\n"
            f"Unable to complete audit for strategy: *\"{user_text}\"*\n\n"
            f"**Reason:** `{exc}`\n\n"
            f"*Try testing a strategy on RELIANCE.NS, TCS.NS, or AAPL (e.g., 'SMA 50/200 on Reliance').*"
        )
