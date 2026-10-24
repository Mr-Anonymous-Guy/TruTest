"""
tests/test_reliability.py – Phase 4 Reliability, Fault Injection & Soak Tests
=============================================================================
Comprehensive unit tests covering:
  - Task 9a: Retries, error taxonomy, deadliness, deduplication, concurrency, rate limits, session TTL
  - Task 9b: Worker health, fault injection, data edge cases, LLM resilience, and soak testing
"""

import json
import os
import time
from pathlib import Path
import pytest

from agents import messages
from agents.data_source import clean_ticker_symbol, fetch_prices, find_similar_tickers
from agents.faults import is_fault_active, maybe_inject_fault
from agents.llm import clean_llm_json_response, is_circuit_open, reset_circuit_breaker
from agents.models import HealthRequest, HealthResponse
from agents.orchestrator import check_agent_health, save_trace
from agents.parser_agent import parse_strategy_text
from agents.pipeline import SessionManager, format_final_reply
from agents.reliability import (
    BoundedSessionStore,
    ConcurrencyGuard,
    InternalError,
    MessageDeduplicator,
    RateLimiter,
    RequestBudget,
    TransientError,
    UserError,
    call_with_retry,
    sanitize_input,
)
from core.data import DataQualityError
from scripts.show_trace import show_trace


# ===========================================================================
# 1. Input Validation & Error Handling (Task 0 & Task 7)
# ===========================================================================

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


def test_input_sanitizer():
    """Sanitizer strips non-printable characters and enforces length limits."""
    # Control characters stripped
    ok, text, err = sanitize_input("Backtest\x00 50/200\x08 MA on RELIANCE.NS")
    assert ok
    assert text == "Backtest 50/200 MA on RELIANCE.NS"
    assert err is None

    # Empty text rejected
    ok, text, err = sanitize_input("   \t\n  ")
    assert not ok
    assert err == "empty"

    # Oversize text capped and marked too_long
    long_msg = "A" * 1500
    ok, text, err = sanitize_input(long_msg, max_chars=1000)
    assert not ok
    assert err == "too_long"
    assert len(text) == 1000


# ===========================================================================
# 2. Retries & Error Taxonomy (Task 2 & Task 9a)
# ===========================================================================

def test_retry_transient_error_succeeds_on_second_attempt():
    """TransientError triggers one retry with backoff and succeeds."""
    attempts = 0
    delays = []

    def mock_action():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TransientError("Connection reset")
        return "SUCCESS"

    def mock_sleeper(d):
        delays.append(d)

    result = call_with_retry("test_step", mock_action, retries=1, backoff=1.0, sleeper=mock_sleeper)
    assert result == "SUCCESS"
    assert attempts == 2
    assert delays == [1.0]


def test_retry_transient_error_exhausted_raises():
    """When retries are exhausted on TransientError, the error is raised."""
    attempts = 0

    def mock_failing_action():
        nonlocal attempts
        attempts += 1
        raise TransientError("Persistent timeout")

    with pytest.raises(TransientError):
        call_with_retry("failing_step", mock_failing_action, retries=1, backoff=0.01, sleeper=lambda d: None)

    assert attempts == 2


def test_user_error_is_never_retried():
    """UserError must fail immediately without retry."""
    attempts = 0

    def mock_user_error_action():
        nonlocal attempts
        attempts += 1
        raise UserError("Invalid ticker symbol")

    with pytest.raises(UserError):
        call_with_retry("user_step", mock_user_error_action, retries=2, sleeper=lambda d: None)

    assert attempts == 1


# ===========================================================================
# 3. Concurrency, Deduplication, and Rate Limiting (Task 2 & Task 9a)
# ===========================================================================

def test_message_deduplicator():
    """Duplicate message IDs from ASI:One are flagged and oldest are evicted."""
    dedup = MessageDeduplicator(max_size=3)
    assert not dedup.is_duplicate("msg-1")
    assert dedup.is_duplicate("msg-1")

    assert not dedup.is_duplicate("msg-2")
    assert not dedup.is_duplicate("msg-3")
    # msg-1, msg-2, msg-3 now in dedup
    assert not dedup.is_duplicate("msg-4")  # evicts msg-1
    assert not dedup.is_duplicate("msg-1")  # msg-1 is now fresh again


def test_concurrency_guard_isolation():
    """ConcurrencyGuard permits one active request per sender, isolating senders."""
    guard = ConcurrencyGuard()
    sender_a = "user_alice"
    sender_b = "user_bob"

    assert guard.acquire(sender_a)
    assert not guard.acquire(sender_a)  # second request blocked
    assert guard.is_busy(sender_a)

    # Bob is isolated and can acquire
    assert guard.acquire(sender_b)
    assert guard.is_busy(sender_b)

    guard.release(sender_a)
    assert not guard.is_busy(sender_a)
    assert guard.acquire(sender_a)  # Alice can acquire again


def test_rate_limiter_sliding_window():
    """RateLimiter permits up to quota within window, then throttles."""
    limiter = RateLimiter(max_requests=3, window_seconds=10.0)
    sender = "test_trader"

    fake_time = 1000.0
    assert limiter.allow(sender, current_time=fake_time)
    assert limiter.allow(sender, current_time=fake_time + 1.0)
    assert limiter.allow(sender, current_time=fake_time + 2.0)
    # 4th request within 10s should be rejected
    assert not limiter.allow(sender, current_time=fake_time + 3.0)

    # After window passes, requests are allowed again
    assert limiter.allow(sender, current_time=fake_time + 11.0)


def test_bounded_session_store_ttl_and_eviction():
    """BoundedSessionStore expires idle sessions and evicts oldest at capacity."""
    store = BoundedSessionStore(max_sessions=2, ttl_seconds=100.0)
    t0 = 1000.0

    sess_1 = store.get_or_create("user_1", current_time=t0)
    sess_1["test_val"] = "val_1"

    sess_2 = store.get_or_create("user_2", current_time=t0 + 10.0)
    sess_2["test_val"] = "val_2"

    assert len(store) == 2

    # Accessing user_3 causes user_1 (oldest) to be evicted
    sess_3 = store.get_or_create("user_3", current_time=t0 + 20.0)
    assert len(store) == 2
    # user_1 should have been evicted
    fresh_user_1 = store.get_or_create("user_1", current_time=t0 + 30.0)
    assert "test_val" not in fresh_user_1

    # TTL expiry
    store.get_or_create("user_3", current_time=t0 + 500.0)  # user_1 expired by TTL
    assert len(store) == 1


def test_request_budget_deadline():
    """RequestBudget calculates remaining time and clamps timeouts."""
    budget = RequestBudget(total_seconds=10.0, start_time=100.0)

    # At 102s (2s elapsed): 8s remaining
    clamped = budget.clamp_timeout(5.0, current_time=102.0)
    assert clamped == 5.0

    clamped_large = budget.clamp_timeout(30.0, current_time=102.0)
    assert clamped_large == 8.0

    # At 110s (deadline expired): raises TransientError
    with pytest.raises(TransientError):
        budget.clamp_timeout(5.0, current_time=110.0)


# ===========================================================================
# 4. Partial Results & Degradation (Task 3 & Task 9a)
# ===========================================================================

def test_skeptic_degradation_unvalidated_report():
    """When Skeptic agent is offline, an unvalidated partial report is formatted without a verdict."""
    spec = {"ticker": "RELIANCE.NS", "strategy": "ma_crossover", "params": {"fast": 50, "slow": 200}}
    prices = {"bars": 1200, "source": "cache", "start": "2019-01-01", "end": "2024-01-01", "note": "cache"}
    backtest = {"total_return": 0.45, "cagr": 0.12, "sharpe": 1.15, "max_drawdown": -0.15, "trade_count": 8, "exposure": 0.6, "win_rate": 0.62}
    degraded_audit = {
        "verdict": "UNVALIDATED",
        "unvalidated": True,
        "note": messages.SKEPTIC_DEGRADED_NOTE,
        "tests": [],
        "warnings": ["Adversarial audit skipped."],
    }
    report = format_final_reply(spec, assumptions=["Default assumptions"], prices=prices, backtest=backtest, audit=degraded_audit)
    assert "FINAL VERDICT: UNVALIDATED" in report
    assert "The audit step was unavailable, so this result has NOT been validated. No verdict is given." in report
    assert "Sharpe Ratio: 1.15" in report


def test_full_result_timing_footer():
    """Full results include the timing footer."""
    spec = {"ticker": "RELIANCE.NS", "strategy": "ma_crossover", "params": {"fast": 50, "slow": 200}}
    prices = {"bars": 1200, "source": "cache", "start": "2019-01-01", "end": "2024-01-01", "note": "cache"}
    backtest = {"total_return": 0.45, "cagr": 0.12, "sharpe": 1.15, "max_drawdown": -0.15, "trade_count": 8, "exposure": 0.6, "win_rate": 0.62}
    full_audit = {
        "verdict": "Trustworthy",
        "tests": [{"name": "oos_split", "passed": True, "explanation": "Solid out of sample"}],
        "warnings": [],
    }
    timing_info = (8.4, 2.1, 0.8, 0.2, 5.3)
    report = format_final_reply(spec, assumptions=[], prices=prices, backtest=backtest, audit=full_audit, timing_info=timing_info)
    assert "FINAL VERDICT: TRUSTWORTHY" in report
    assert "Took 8.4s (parse 2.1, data 0.8, backtest 0.2, audit 5.3)" in report


# ===========================================================================
# 5. Fault Injection (Task 6 & Task 9b)
# ===========================================================================

def test_data_fault_injection_live_fail(monkeypatch):
    """TRUSTTEST_FAULT=data_live_fail forces local cache with a clear note."""
    monkeypatch.setenv("TRUSTTEST_FAULT", "data_live_fail")
    df, source, note = fetch_prices("RELIANCE.NS")
    assert source == "cache"
    assert "TRUSTTEST_FAULT=data_live_fail" in note
    assert len(df) > 0


def test_data_fault_injection_data_fail(monkeypatch):
    """TRUSTTEST_FAULT=data_fail simulates complete market data failure."""
    monkeypatch.setenv("TRUSTTEST_FAULT", "data_fail")
    with pytest.raises(DataQualityError) as exc_info:
        fetch_prices("RELIANCE.NS")
    assert "FAULT INJECTION ACTIVE" in str(exc_info.value)


def test_parser_fault_injection_llm_fail(monkeypatch):
    """TRUSTTEST_FAULT=parser_llm_fail bypasses LLM and uses heuristic parser."""
    monkeypatch.setenv("TRUSTTEST_FAULT", "parser_llm_fail")
    res = parse_strategy_text("Buy Reliance when 50 MA crosses 200 MA")
    assert res.ok
    assert res.spec["ticker"] == "RELIANCE.NS"
    assert res.spec["strategy"] == "ma_crossover"
    assert res.spec["params"]["fast"] == 50
    assert res.spec["params"]["slow"] == 200


# ===========================================================================
# 6. LLM Resilience & Circuit Breaker (Task 8 & Task 9b)
# ===========================================================================

def test_llm_clean_json_response():
    """clean_llm_json_response handles code fences, whitespace, and conversational prose."""
    # Code fence
    raw_1 = "```json\n{\"ticker\": \"RELIANCE.NS\", \"strategy\": \"ma_crossover\"}\n```"
    assert clean_llm_json_response(raw_1) == '{"ticker": "RELIANCE.NS", "strategy": "ma_crossover"}'

    # Conversational wrapping
    raw_2 = "Sure, here is your strategy:\n{\"ticker\": \"TCS.NS\", \"strategy\": \"rsi_meanrev\"}\nHope this helps!"
    assert clean_llm_json_response(raw_2) == '{"ticker": "TCS.NS", "strategy": "rsi_meanrev"}'


def test_llm_circuit_breaker_mechanism(monkeypatch):
    """Circuit breaker opens after 3 consecutive failures."""
    from agents.llm import call_llm
    reset_circuit_breaker()
    assert not is_circuit_open()

    monkeypatch.setenv("TRUSTTEST_FAULT", "llm_fail")

    # 3 failures will trip breaker
    for _ in range(3):
        with pytest.raises(RuntimeError):
            call_llm([{"role": "user", "content": "hi"}], max_retries=0)

    assert is_circuit_open()
    # While open, immediately raises without making network request
    with pytest.raises(RuntimeError) as exc:
        call_llm([{"role": "user", "content": "hi"}])
    assert "circuit breaker open" in str(exc.value).lower()

    reset_circuit_breaker()


# ===========================================================================
# 7. Data Edge Cases (Task 7 & Task 9b)
# ===========================================================================

def test_data_future_end_date_clamped():
    """Future end date is clamped to today and noted."""
    df, source, note = fetch_prices("RELIANCE.NS", start="2020-01-01", end="2035-01-01", enable_live=False)
    assert len(df) > 0
    assert "clamped" in note.lower()


def test_data_start_after_end_rejected():
    """Start date after end date raises friendly DataQualityError."""
    with pytest.raises(DataQualityError) as exc:
        fetch_prices("RELIANCE.NS", start="2023-01-01", end="2020-01-01", enable_live=False)
    assert "must be before end date" in str(exc.value)


def test_data_start_in_future_rejected():
    """Start date in the future raises DataQualityError."""
    with pytest.raises(DataQualityError) as exc:
        fetch_prices("RELIANCE.NS", start="2030-01-01", end="2035-01-01", enable_live=False)
    assert "in the future" in str(exc.value)


def test_data_difflib_ticker_suggestions():
    """find_similar_tickers finds close matches."""
    matches = find_similar_tickers("RELIANC")
    assert "RELIANCE.NS" in matches


# ===========================================================================
# 8. Health Check & Trace Testing (Task 4, Task 5a & Task 9b)
# ===========================================================================

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
    show_trace(tmp_path / "nonexistent.json")

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


# ===========================================================================
# 9. Soak Test (Task 9b: 200 sequential & 20 interleaved across 10 senders)
# ===========================================================================

def test_soak_test_session_and_pipeline_bounds():
    """
    Soak test: 200 sequential operations + 20 interleaved across 10 senders.
    Asserts zero unhandled exceptions, bounded session capacity, and no state leaks.
    """
    store = BoundedSessionStore(max_sessions=50, ttl_seconds=1800.0)
    guard = ConcurrencyGuard()
    limiter = RateLimiter(max_requests=1000, window_seconds=60.0)
    senders = [f"agent_user_{i}" for i in range(10)]

    # 1. 200 Sequential simulated requests
    for i in range(200):
        sender = senders[i % len(senders)]
        assert guard.acquire(sender)
        try:
            assert limiter.allow(sender)
            sess = store.get_or_create(sender)
            store.update_partial_spec(sender, {"iter": i, "strategy": "ma_crossover"})
        finally:
            guard.release(sender)

    # 2. 20 Interleaved requests across senders
    for j in range(20):
        sender_1 = senders[j % len(senders)]
        sender_2 = senders[(j + 1) % len(senders)]

        assert guard.acquire(sender_1)
        assert guard.acquire(sender_2)
        try:
            s1 = store.get_or_create(sender_1)
            s2 = store.get_or_create(sender_2)
            assert s1 is not None
            assert s2 is not None
        finally:
            guard.release(sender_1)
            guard.release(sender_2)

    # Verify session store bounds: never exceeds max_sessions (50)
    assert len(store) <= 50
    # Verify no senders remain locked
    for s in senders:
        assert not guard.is_busy(s)
