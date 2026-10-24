"""
tests/test_pipeline.py – Unit Tests for Orchestrator Pipeline Helpers & Formatting
"""

import pytest
from agents.pipeline import SessionManager, format_final_reply


def test_session_manager_lifecycle():
    """Verify session manager creation, partial spec update, and clearing."""
    sm = SessionManager()
    sess = sm.get_or_create("user-123")
    assert sess["stage"] == "idle"
    assert sess["partial_spec"] is None

    # Update with partial spec
    partial = {"strategy": "ma_crossover", "params": {"fast": 50, "slow": 200}}
    sm.update_partial_spec("user-123", partial)
    assert sess["stage"] == "awaiting_clarification"
    assert sess["partial_spec"]["strategy"] == "ma_crossover"

    # Clear session
    sm.clear("user-123")
    sess_new = sm.get_or_create("user-123")
    assert sess_new["partial_spec"] is None
    assert sess_new["stage"] == "idle"


def test_format_final_reply_complete():
    """Verify that format_final_reply includes all required sections and disclaimers."""
    spec = {
        "ticker": "RELIANCE.NS",
        "strategy": "ma_crossover",
        "params": {"fast": 50, "slow": 200},
    }
    assumptions = [
        "Assumed 0.10% transaction fee per side.",
        "Assumed 0.05% slippage per side.",
        "Default evaluation period: last 5 years.",
    ]
    prices = {
        "bars": 1236,
        "source": "cache",
        "start": "2021-10-25",
        "end": "2026-10-23",
        "note": "Used cached historical CSV data (1,236 bars).",
    }
    backtest = {
        "total_return": -0.0137,
        "cagr": -0.0028,
        "sharpe": 0.05,
        "max_drawdown": 0.2085,
        "trade_count": 4,
        "exposure": 0.493,
        "win_rate": 0.25,
    }
    audit = {
        "verdict": "Likely Overfit",
        "tests": [
            {"name": "out_of_sample", "passed": True, "explanation": "OOS Sharpe is 0.09."},
            {"name": "parameter_perturbation", "passed": False, "explanation": "Only 42% of neighbours held."},
            {"name": "cost_sensitivity", "passed": False, "explanation": "Sharpe dropped to 0.03."},
            {"name": "random_baseline", "passed": False, "explanation": "Only beats 30.4% of baselines."},
        ],
        "warnings": ["Only 4 trades executed: statistical sample is low."],
    }

    report = format_final_reply(spec, assumptions, prices, backtest, audit)

    assert "RELIANCE.NS" in report
    assert "ma_crossover" in report
    assert "Assumptions:" in report
    assert "Market Data:" in report
    assert "Headline Backtest Performance:" in report
    assert "Adversarial Skeptic Audit:" in report
    assert "FINAL VERDICT: LIKELY OVERFIT" in report
    assert "survivorship and selection bias" in report
    assert "Educational only, not investment advice" in report
    assert "Trustworthy" in report
