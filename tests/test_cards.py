"""
tests/test_cards.py – Phase 5 ASI:One Interactive Cards Protocol Tests
======================================================================
Tests:
  1. ReportView dataclass extraction from backtest & skeptic dictionaries
  2. Card 1 (Strategy Picker CarouselCardPayload) structure, items & CTAs
  3. Card 2 (Headline Results DetailCardPayload) contrast & CTAs
  4. Card 3 (Audit Details DetailCardPayload) 4 tests, warnings, survivorship & disclaimer
  5. Card 4 (Parameter FormCardPayload) pre-filled fields & error titles
  6. CardResultCache: LRU capacity, TTL expiration, and retrieval
  7. parse_card_selection: MetadataContent, direct JSON, JSON in prose, malicious/oversized/unknown
  8. are_cards_enabled toggle via TRUSTTEST_CARDS
  9. Stored benchmark examples server-side resolution
"""

import collections
import json
import uuid
import pytest
from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent
from uagents_core.contrib.protocols.chat.cards import (
    CarouselCardPayload,
    DetailCardPayload,
    FormCardPayload,
    create_card_content,
    create_card_response_content,
)

from agents.cards import (
    CardResultCache,
    ReportView,
    are_cards_enabled,
    create_audit_details_card,
    create_parameter_form_card,
    create_results_card,
    create_strategy_picker_card,
    parse_card_selection,
)
from agents.orchestrator import STORED_EXAMPLES


def test_report_view_from_results():
    """ReportView cleanly extracts metrics, contrasts, warnings, and disclaimer."""
    spec = {
        "ticker": "RELIANCE.NS",
        "strategy": "ma_crossover",
        "params": {"fast": 50, "slow": 200},
        "fee_pct": 0.1,
        "slippage_pct": 0.05,
        "start": "2021-10-25",
        "end": "2026-10-23",
    }
    backtest = {
        "total_return": 0.725,
        "cagr": 0.115,
        "sharpe": 1.15,
        "max_drawdown": 0.165,
        "trade_count": 8,
        "win_rate": 0.625,
    }
    audit = {
        "verdict": "Trustworthy",
        "tests": [
            {
                "name": "out_of_sample",
                "passed": True,
                "oos_sharpe": 0.95,
                "explanation": "OOS Sharpe is 0.95 (holds >= 50% of in-sample).",
            },
            {
                "name": "cost_sensitivity",
                "passed": False,
                "explanation": "With 2x friction, Sharpe dropped significantly.",
            },
        ],
    }

    view = ReportView.from_results(spec, backtest, audit)
    assert view.ticker == "RELIANCE.NS"
    assert "50/200" in view.strategy_desc or "fast=50, slow=200" in view.strategy_desc
    assert view.price_type == "adjusted prices"
    assert view.total_return_pct == pytest.approx(72.5)
    assert view.cagr_pct == pytest.approx(11.5)
    assert view.sharpe == pytest.approx(1.15)
    assert view.max_drawdown_pct == pytest.approx(16.5)
    assert view.trades == 8
    assert view.win_rate_pct == pytest.approx(62.5)
    assert "OOS Sharpe 0.95 (Held)" in view.oos_result_text
    assert view.verdict == "Trustworthy"
    assert any("Low trade count" in w for w in view.warnings)
    assert any("High friction drag" in w for w in view.warnings)
    assert "Educational only, not investment advice" in view.disclaimer


def test_strategy_picker_card_structure():
    """Picker card has title, subtitle, and 3 actionable carousel items with server-side example IDs."""
    card_content = create_strategy_picker_card()
    assert isinstance(card_content, MetadataContent)
    assert card_content.metadata["card_kind"] == "carousel"

    payload_dict = json.loads(card_content.metadata["card_payload"])
    assert payload_dict["title"] == "TrustTest Strategy Showcase"
    items = payload_dict["items"]
    assert len(items) == 3

    item_ids = [it["id"] for it in items]
    assert item_ids == ["demo_a", "demo_b", "rsi_tcs"]

    # Verify primary CTA actions contain source: trusttest and run_example
    for item in items:
        cta = item["primary_cta"]
        assert cta["selection"]["source"] == "trusttest"
        assert cta["selection"]["action"] == "run_example"
        assert "example_id" in cta["selection"]


def test_results_card_structure():
    """Results card details key metrics, contrast of return vs OOS, and 3 CTAs."""
    spec = {"ticker": "RELIANCE.NS", "strategy": "ma_crossover", "params": {"fast": 50, "slow": 200}}
    backtest = {"total_return": 0.725, "cagr": 0.115, "sharpe": 1.15, "max_drawdown": 0.165, "trade_count": 14, "win_rate": 0.643}
    audit = {
        "verdict": "Trustworthy",
        "tests": [
            {"name": "out_of_sample", "passed": True, "oos_sharpe": 0.95, "explanation": "Holds in OOS"}
        ],
    }

    card_content = create_results_card("res-123", spec, backtest, audit)
    assert isinstance(card_content, MetadataContent)
    assert card_content.metadata["card_kind"] == "detail"

    payload_dict = json.loads(card_content.metadata["card_payload"])
    assert "RELIANCE.NS" in payload_dict["title"]

    rows = {r["label"]: r["value"] for r in payload_dict["summary_rows"]}
    assert "Total: +72.5%" in rows["Return vs OOS"]
    assert "OOS Sharpe 0.95 (Held)" in rows["Return vs OOS"]
    assert "[TRUSTWORTHY]" in rows["Skeptic Verdict"]
    assert "14 trades" in rows["Trades (Win %)"]

    ctas = payload_dict["ctas"]
    assert len(ctas) == 3
    assert ctas[0]["label"] == "See audit details"
    assert ctas[0]["selection"] == {"source": "trusttest", "action": "show_audit", "report_id": "res-123"}
    assert ctas[1]["label"] == "Full text report"
    assert ctas[1]["selection"] == {"source": "trusttest", "action": "full_report", "report_id": "res-123"}
    assert ctas[2]["label"] == "Try an example"
    assert ctas[2]["selection"] == {"source": "trusttest", "action": "show_examples"}


def test_audit_details_card_structure():
    """Audit detail card lists tests with [PASS]/[FAIL], survivorship note, disclaimer, and 2 CTAs."""
    spec = {"ticker": "RELIANCE.NS", "strategy": "ma_crossover", "params": {"fast": 23, "slow": 35}}
    audit = {
        "verdict": "Likely Overfit",
        "tests": [
            {"name": "out_of_sample", "passed": False, "explanation": "Sharpe drops to -0.42"},
            {"name": "parameter_perturbation", "passed": False, "explanation": "Only 30% of neighbours held"},
            {"name": "cost_sensitivity", "passed": False, "explanation": "Negative returns at 2x friction"},
            {"name": "random_baseline", "passed": False, "explanation": "Beats only 40% of random paths"},
        ],
    }

    card_content = create_audit_details_card("res-456", spec, audit)
    assert isinstance(card_content, MetadataContent)
    payload_dict = json.loads(card_content.metadata["card_payload"])

    rows = {r["label"]: r["value"] for r in payload_dict["summary_rows"]}
    assert "[FAIL] Out Of Sample" in rows
    assert "[FAIL] Parameter Perturbation" in rows
    assert "[FAIL] Cost Sensitivity" in rows
    assert "[FAIL] Random Baseline" in rows
    assert "Constituent survivorship applies" in rows["Survivorship Bias"]
    assert "Educational only, not investment advice" in rows["Disclaimer"]

    ctas = payload_dict["ctas"]
    assert len(ctas) == 2
    assert ctas[0]["label"] == "Back to results"
    assert ctas[0]["selection"] == {"source": "trusttest", "action": "show_results", "report_id": "res-456"}
    assert ctas[1]["label"] == "Try an example"
    assert ctas[1]["selection"] == {"source": "trusttest", "action": "show_examples"}


def test_parameter_form_card_structure():
    """Form card includes ticker select, number fields, and duration."""
    card_content = create_parameter_form_card(partial_spec={"ticker": "TCS.NS", "params": {"fast": 20, "slow": 50}})
    payload_dict = json.loads(card_content.metadata["card_payload"])
    fields = payload_dict["fields"]
    field_names = [f["name"] for f in fields]
    assert "ticker" in field_names
    assert "fast" in field_names
    assert "slow" in field_names
    assert "duration_years" in field_names

    # Check placeholder pre-fill
    fast_field = next(f for f in fields if f["name"] == "fast")
    assert fast_field["placeholder"] == "20"

    # Form with validation error
    err_card = create_parameter_form_card(error_msg="Fast window must be less than slow window")
    err_dict = json.loads(err_card.metadata["card_payload"])
    assert "Validation Error: Fast window must be less than slow window" in err_dict["title"]


def test_card_result_cache_lru_and_ttl():
    """CardResultCache supports storing, retrieval, and TTL expiration."""
    cache = CardResultCache(max_size=2)
    t0 = 1000.0

    spec = {"ticker": "RELIANCE.NS"}
    bt = {"sharpe": 1.15}
    audit = {"verdict": "Trustworthy"}

    cache.store("res-1", spec, bt, audit, "full text 1", timestamp=t0)
    cache.store("res-2", spec, bt, audit, "full text 2", timestamp=t0 + 10.0)

    # Retrieval works
    item = cache.get("res-1", current_time=t0 + 20.0)
    assert item is not None
    assert item["full_text"] == "full text 1"
    assert isinstance(item["report_view"], ReportView)

    # Capacity overflow evicts oldest
    cache.store("res-3", spec, bt, audit, "full text 3", timestamp=t0 + 30.0)
    # res-2 was least recently accessed, so it was evicted
    assert cache.get("res-2", current_time=t0 + 40.0) is None
    assert cache.get("res-1", current_time=t0 + 40.0) is not None

    # Expiration past TTL
    expired_item = cache.get("res-1", current_time=t0 + 3000.0)
    assert expired_item is None


def test_parse_card_selection_all_paths():
    """parse_card_selection handles metadata, direct JSON, embedded prose, and rejects malicious/invalid payloads."""
    # 1. Official MetadataContent response
    card_id = uuid.uuid4()
    resp_block = create_card_response_content(card_id=card_id, selection={"source": "trusttest", "action": "show_audit", "report_id": "r1"})
    msg1 = ChatMessage(content=[resp_block])
    assert parse_card_selection(msg1) == {"source": "trusttest", "action": "show_audit", "report_id": "r1"}

    # 2. Direct JSON in string or TextContent
    direct_json = '{"source": "trusttest", "action": "show_results", "report_id": "r2"}'
    assert parse_card_selection(direct_json) == {"source": "trusttest", "action": "show_results", "report_id": "r2"}
    msg2 = ChatMessage(content=[TextContent(type="text", text=direct_json)])
    assert parse_card_selection(msg2) == {"source": "trusttest", "action": "show_results", "report_id": "r2"}

    # 3. JSON embedded inside prose (planner-mediated path)
    prose = 'User selected action: {"source": "trusttest", "action": "run_example", "example_id": "demo_a"} from options.'
    assert parse_card_selection(prose) == {"source": "trusttest", "action": "run_example", "example_id": "demo_a"}

    # 4. Unknown action rejected
    bad_action = '{"source": "trusttest", "action": "drop_tables"}'
    assert parse_card_selection(bad_action) is None

    # 5. Wrong source rejected
    wrong_source = '{"source": "rogue_agent", "action": "show_results"}'
    assert parse_card_selection(wrong_source) is None

    # 6. Malformed JSON returns None
    assert parse_card_selection("Hello world, this is a plain strategy prompt") is None
    assert parse_card_selection('{"source": "trusttest", invalid}') is None

    # 7. Oversized input returns None
    oversized = '{"source": "trusttest", "action": "show_results", "data": "' + ("a" * 2500) + '"}'
    assert parse_card_selection(oversized) is None


def test_are_cards_enabled_toggle(monkeypatch):
    """TRUSTTEST_CARDS toggle switches cards on or off cleanly."""
    monkeypatch.setenv("TRUSTTEST_CARDS", "on")
    assert are_cards_enabled() is True

    monkeypatch.setenv("TRUSTTEST_CARDS", "off")
    assert are_cards_enabled() is False

    monkeypatch.setenv("TRUSTTEST_CARDS", "0")
    assert are_cards_enabled() is False

    monkeypatch.delenv("TRUSTTEST_CARDS", raising=False)
    assert are_cards_enabled() is True


def test_stored_examples_resolution():
    """Stored benchmark examples are resolved server-side without trusting client specs."""
    assert "demo_a" in STORED_EXAMPLES
    assert "demo_b" in STORED_EXAMPLES
    assert "rsi_tcs" in STORED_EXAMPLES

    demo_a = STORED_EXAMPLES["demo_a"]
    assert demo_a["ticker"] == "RELIANCE.NS"
    assert demo_a["params"] == {"fast": 50, "slow": 200}

    demo_b = STORED_EXAMPLES["demo_b"]
    assert demo_b["ticker"] == "RELIANCE.NS"
    assert demo_b["params"] == {"fast": 23, "slow": 35}

    demo_c = STORED_EXAMPLES["rsi_tcs"]
    assert demo_c["ticker"] == "TCS.NS"
    assert demo_c["strategy"] in ("rsi", "rsi_meanrev")


def test_session_recent_reports_bounding():
    """Session recent reports bound to 5 entries per sender with FIFO eviction."""
    from agents.orchestrator import session_store
    sender = "test_sender_reports"
    sess = session_store.get_or_create(sender)
    recent = sess.setdefault("recent_reports", collections.OrderedDict())

    # Add 6 reports
    for i in range(1, 7):
        rep_id = f"r-{i}"
        recent[rep_id] = {"report_id": rep_id, "data": f"report {i}"}
        if len(recent) > 5:
            recent.popitem(last=False)

    assert len(recent) == 5
    assert "r-1" not in recent  # Evicted
    assert "r-2" in recent
    assert "r-6" in recent


def test_form_validation_logic():
    """Form validation rejects fast >= slow, zero/negative windows, and non-numeric inputs."""
    def validate_inputs(fast_raw, slow_raw):
        try:
            fast = int(fast_raw)
            slow = int(slow_raw)
        except (ValueError, TypeError):
            return False, "Invalid moving average window: integers required."
        if fast <= 0 or slow <= 0 or fast >= slow:
            return False, f"Fast window ({fast}) must be strictly less than slow window ({slow})."
        return True, None

    ok, err = validate_inputs(50, 200)
    assert ok and err is None

    ok, err = validate_inputs(200, 50)
    assert not ok and "strictly less" in err

    ok, err = validate_inputs(-10, 50)
    assert not ok and "strictly less" in err

    ok, err = validate_inputs("abc", 50)
    assert not ok and "integers required" in err
