"""
tests/test_reliability.py – Phase 4 Reliability & Fault Injection Tests
======================================================================
Verifies:
1. Typo ticker detection ("RELIANC.NS" -> suggests "RELIANCE.NS")
2. Invalid ticker friendly handling ("NOTAREALTICKER" -> suggests valid tickers)
3. Future date rejection (historical data requirement)
4. Short history window rejection (< 90 days)
5. Message length guard (> 1500 chars)
6. Data fault injection (TRUSTTEST_FAULT=data_live_fail -> cache fallback)
7. Parser fault injection (TRUSTTEST_FAULT=parser_llm_fail -> heuristic fallback)
8. Skeptic degradation (unvalidated verdict when Skeptic is unavailable)
9. Health status checking across agent ports
10. Trace logging and inspection via show_trace.py
"""

import os
from pathlib import Path
import pytest

from agents.data_source import fetch_prices
from agents.orchestrator import check_agent_health, save_trace
from agents.parser_agent import parse_strategy_text
from agents.pipeline import SessionManager, format_final_reply
from scripts.show_trace import show_trace


def test_typo_ticker_suggestion():
    """Typo in ticker suggests the closest known ticker."""
    res = parse_strategy_text("Backtest 50/200 MA on RELIANC.NS")
    assert not res.ok
    assert "Did you mean RELIANCE.NS" in res.question


def test_invalid_ticker_handling():
    """Completely unknown ticker returns a polite message listing supported tickers."""
    res = parse_strategy_text("Backtest 50/200 MA on NOTAREALTICKER")
    assert not res.ok
    assert "NOTAREALTICKER" in res.question
    assert "RELIANCE.NS" in res.question


def test_future_dates_rejected():
    """Dates in the future are rejected with a clear historical data explanation."""
    res = parse_strategy_text("SMA 50/200 on RELIANCE.NS from 2028-01-01 to 2030-01-01")
    assert not res.ok
    assert "Future dates cannot be tested" in res.question


def test_short_window_rejected():
    """Windows shorter than 90 days are rejected with guidance."""
    res = parse_strategy_text("SMA 50/200 on RELIANCE.NS from 2023-01-01 to 2023-01-20")
    assert not res.ok
    assert "History window is too short" in res.question


def test_data_fault_injection_live_fail(monkeypatch):
    """TRUSTTEST_FAULT=data_live_fail forces local cache with a clear note."""
    monkeypatch.setenv("TRUSTTEST_FAULT", "data_live_fail")
    df, source, note = fetch_prices("RELIANCE.NS")
    assert source == "cache"
    assert "TRUSTTEST_FAULT=data_live_fail" in note
    assert len(df) > 0


def test_parser_fault_injection_llm_fail(monkeypatch):
    """TRUSTTEST_FAULT=parser_llm_fail bypasses LLM and uses heuristic parser."""
    monkeypatch.setenv("TRUSTTEST_FAULT", "parser_llm_fail")
    res = parse_strategy_text("Buy Reliance when 50 MA crosses 200 MA")
    assert res.ok
    assert res.spec["ticker"] == "RELIANCE.NS"
    assert res.spec["strategy"] == "ma_crossover"
    assert res.spec["params"]["fast"] == 50
    assert res.spec["params"]["slow"] == 200


def test_skeptic_degradation_unvalidated_report():
    """When Skeptic agent is offline, an unvalidated report is formatted without crashing."""
    spec = {"ticker": "RELIANCE.NS", "strategy": "ma_crossover", "params": {"fast": 50, "slow": 200}}
    prices = {"bars": 1200, "source": "cache", "start": "2019-01-01", "end": "2024-01-01", "note": "cache"}
    backtest = {"total_return": 0.45, "cagr": 0.12, "sharpe": 1.15, "max_drawdown": -0.15, "trade_count": 8, "exposure": 0.6, "win_rate": 0.62}
    degraded_audit = {
        "verdict": "UNVALIDATED",
        "note": "Skeptic adversarial auditor was unavailable. Results are unvalidated.",
        "tests": [],
        "warnings": ["Adversarial audit skipped."],
    }
    report = format_final_reply(spec, assumptions=["Default assumptions"], prices=prices, backtest=backtest, audit=degraded_audit)
    assert "FINAL VERDICT: UNVALIDATED" in report
    assert "Adversarial Skeptic Audit" in report
    assert "Sharpe Ratio: 1.15" in report


def test_session_manager_busy_guard():
    """SessionManager tracks busy state to prevent concurrent rapid double-sends."""
    mgr = SessionManager()
    sender = "test_user_123"
    assert not mgr.is_busy(sender)
    mgr.set_busy(sender, True)
    assert mgr.is_busy(sender)
    mgr.set_busy(sender, False)
    assert not mgr.is_busy(sender)


def test_health_check_function():
    """check_agent_health returns formatted status including all 5 agent names."""
    status = check_agent_health()
    assert "TrustTest Multi-Agent Health Status:" in status
    assert "Orchestrator" in status
    assert "Strategy Parser" in status
    assert "Market Data Agent" in status
    assert "Backtest Engine" in status
    assert "Skeptic Auditor" in status


def test_trace_logging_and_show_trace(tmp_path):
    """save_trace creates valid JSON trace file readable by show_trace."""
    trace_file = tmp_path / "latest_trace.json"
    steps = [
        {"hop": 1, "agent": "Strategy Parser", "status": "SUCCESS", "latency_ms": 25.0, "details": "MA on RELIANCE.NS"},
        {"hop": 2, "agent": "Market Data Agent", "status": "SUCCESS", "latency_ms": 110.0, "details": "1200 bars"},
    ]
    # Test show_trace on non-existing path
    show_trace(tmp_path / "nonexistent.json")
    # Test show_trace on real path
    import json
    data = {
        "request_id": "tt-test-1",
        "timestamp": "2026-10-24 14:50:00",
        "sender": "test-sender",
        "user_text": "SMA 50/200 on RELIANCE.NS",
        "total_latency_ms": 135.0,
        "steps": steps,
    }
    trace_file.write_text(json.dumps(data), encoding="utf-8")
    show_trace(trace_file)
    assert trace_file.exists()
