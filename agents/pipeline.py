"""
agents/pipeline.py – TrustTest Pipeline Execution & Formatting Helpers

Contains testable pipeline logic, session state handling, and report formatting
for the TrustTest multi-agent pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("trusttest.pipeline")


def format_final_reply(
    spec: Dict[str, Any],
    assumptions: List[str],
    prices: Dict[str, Any],
    backtest: Dict[str, Any],
    audit: Dict[str, Any],
) -> str:
    """
    Format the complete TrustTest analysis into a clear, readable plain-text report
    suitable for ASI:One chat UI.
    """
    ticker = spec.get("ticker", "N/A")
    strategy = spec.get("strategy", "N/A")
    params = spec.get("params", {})

    lines = []
    lines.append(f"=== TrustTest Strategy & Audit Report ===")
    lines.append(f"Strategy: {strategy} ({', '.join(f'{k}={v}' for k, v in params.items())}) on {ticker}")

    # Assumptions
    if assumptions:
        lines.append("\nAssumptions:")
        for a in assumptions:
            lines.append(f"  • {a}")

    # Data info
    bars = prices.get("bars", 0)
    source = prices.get("source", "cache")
    start = prices.get("start", "")
    end = prices.get("end", "")
    note = prices.get("note", "")
    lines.append(f"\nMarket Data:")
    lines.append(f"  • Source: {source} ({note or 'historical adjusted prices'})")
    lines.append(f"  • Range: {start} to {end} ({bars:,} bars, auto_adjust=True)")

    # Backtest Metrics
    tot_ret = backtest.get("total_return", 0.0) * 100
    cagr = backtest.get("cagr", 0.0) * 100
    sharpe = backtest.get("sharpe", 0.0)
    max_dd = backtest.get("max_drawdown", 0.0) * 100
    trades = backtest.get("trade_count", 0)
    exposure = backtest.get("exposure", 0.0) * 100
    win_rate = backtest.get("win_rate", 0.0) * 100

    lines.append(f"\nHeadline Backtest Performance:")
    lines.append(f"  • Total Return: {tot_ret:+.2f}% (CAGR: {cagr:+.2f}%)")
    lines.append(f"  • Sharpe Ratio: {sharpe:.2f} (annualized 252 days, 0.0% risk-free rate)")
    lines.append(f"  • Max Drawdown: {max_dd:.2f}%")
    lines.append(f"  • Trade Count: {trades} trades | Win Rate: {win_rate:.1f}% | Exposure: {exposure:.1f}%")

    # Skeptic Adversarial Findings
    tests = audit.get("tests", [])
    lines.append(f"\nAdversarial Skeptic Audit:")
    for t in tests:
        name = t.get("name", "").replace("_", " ").title()
        passed = "PASS" if t.get("passed") else "FAIL"
        explanation = t.get("explanation", "")
        lines.append(f"  • {name}: [{passed}] {explanation}")

    # Warnings
    warnings = audit.get("warnings", [])
    if warnings:
        lines.append("\nWarnings:")
        for w in warnings:
            lines.append(f"  ⚠️ {w}")

    # Final Verdict & Disclaimers
    verdict = audit.get("verdict", "Fragile").upper()
    lines.append(f"\nFINAL VERDICT: {verdict}")
    lines.append("\nNote: Past performance is subject to survivorship and selection bias.")
    lines.append("'Trustworthy' means survived these tests, not that it will make money.")
    lines.append("Educational only, not investment advice.")

    return "\n".join(lines)


class SessionManager:
    """Manages conversational state, partial specs, and turns per user."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_or_create(self, sender: str) -> Dict[str, Any]:
        if sender not in self._sessions:
            self._sessions[sender] = {
                "stage": "idle",
                "partial_spec": None,
                "history": [],
            }
        return self._sessions[sender]

    def update_partial_spec(self, sender: str, partial_spec: Optional[Dict[str, Any]]) -> None:
        sess = self.get_or_create(sender)
        sess["partial_spec"] = partial_spec
        sess["stage"] = "awaiting_clarification" if partial_spec else "idle"

    def clear(self, sender: str) -> None:
        self._sessions.pop(sender, None)
