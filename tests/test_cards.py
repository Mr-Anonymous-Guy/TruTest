"""
tests/test_cards.py – Phase 5 ASI:One Interactive Cards Protocol Tests
======================================================================
Tests:
  1. Card 1 (Strategy Picker CarouselCardPayload) structure & CTAs
  2. Card 2 (Headline Results DetailCardPayload) summary rows & badges
  3. Card 3 (Audit Details DetailCardPayload) breakdown
  4. Card 4 (Parameter FormCardPayload) input fields & validation error title
  5. CardResultCache: LRU capacity, TTL expiration, and retrieval
  6. extract_selection_from_message: MetadataContent response vs Text fallback
  7. are_cards_enabled toggle via TRUSTTEST_CARDS environment variable
"""

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
    extract_card,
)

from agents.cards import (
    CardResultCache,
    are_cards_enabled,
    create_audit_details_card,
    create_parameter_form_card,
    create_results_card,
    create_strategy_picker_card,
    extract_selection_from_message,
)


def test_strategy_picker_card_structure():
    """Picker card has title, subtitle, and 3 actionable carousel items."""
    card_content = create_strategy_picker_card()
    assert isinstance(card_content, MetadataContent)
    assert card_content.metadata["card_kind"] == "carousel"

    payload_dict = json.loads(card_content.metadata["card_payload"])
    assert payload_dict["title"] == "TrustTest Strategy Showcase"
    items = payload_dict["items"]
    assert len(items) == 3

    item_ids = [it["id"] for it in items]
    assert item_ids == ["demo_a", "demo_b", "custom_form"]

    # Verify primary CTA actions
    assert items[0]["primary_cta"]["selection"]["action"] == "run_demo_a"
    assert items[1]["primary_cta"]["selection"]["action"] == "run_demo_b"
    assert items[2]["primary_cta"]["selection"]["action"] == "open_form"


def test_results_card_structure():
    """Results card details key metrics, verdict badge, and CTAs."""
    spec = {"ticker": "RELIANCE.NS", "strategy": "ma_crossover", "params": {"fast": 50, "slow": 200}}
    backtest = {"total_return": 0.725, "sharpe": 1.15, "max_drawdown": -0.165, "trade_count": 14, "win_rate": 0.643}
    audit = {"verdict": "Trustworthy", "tests": []}

    card_content = create_results_card("res-123", spec, backtest, audit)
    assert isinstance(card_content, MetadataContent)
    assert card_content.metadata["card_kind"] == "detail"

    payload_dict = json.loads(card_content.metadata["card_payload"])
    assert "RELIANCE.NS" in payload_dict["title"]

    rows = {r["label"]: r["value"] for r in payload_dict["summary_rows"]}
    assert rows["Sharpe Ratio"] == "1.15"
    assert "+72.50%" in rows["Total Return"]
    assert "TRUSTWORTHY" in rows["Skeptic Verdict"]

    ctas = payload_dict["ctas"]
    assert len(ctas) == 2
    assert ctas[0]["label"] == "See Audit Details"
    assert ctas[0]["selection"]["action"] == "view_audit_details"
    assert ctas[0]["selection"]["result_id"] == "res-123"
    assert ctas[1]["label"] == "Full Text Report"


def test_audit_details_card_structure():
    """Audit detail card lists all 4 test explanations and has Back to Results CTA."""
    spec = {"ticker": "RELIANCE.NS", "strategy": "ma_crossover", "params": {"fast": 10, "slow": 30}}
    audit = {
        "verdict": "Likely Overfit",
        "tests": [
            {"name": "oos_split", "passed": False, "explanation": "Sharpe drops to -0.42"},
            {"name": "cost_sensitivity", "passed": False, "explanation": "Negative returns at 2x friction"},
        ],
    }

    card_content = create_audit_details_card("res-456", spec, audit)
    assert isinstance(card_content, MetadataContent)
    payload_dict = json.loads(card_content.metadata["card_payload"])

    rows = {r["label"]: r["value"] for r in payload_dict["summary_rows"]}
    assert "[FAIL] Oos Split" in rows
    assert "LIKELY OVERFIT" in rows["Final Verdict"]

    ctas = payload_dict["ctas"]
    assert ctas[0]["label"] == "Back to Results"
    assert ctas[0]["selection"]["action"] == "view_results_card"
    assert ctas[0]["selection"]["result_id"] == "res-456"


def test_parameter_form_card_structure():
    """Form card includes ticker select, number fields, and duration."""
    card_content = create_parameter_form_card()
    payload_dict = json.loads(card_content.metadata["card_payload"])
    fields = payload_dict["fields"]
    field_names = [f["name"] for f in fields]
    assert "ticker" in field_names
    assert "fast" in field_names
    assert "slow" in field_names
    assert "duration_years" in field_names

    # Form with validation error
    err_card = create_parameter_form_card(error_msg="Fast must be less than slow")
    err_dict = json.loads(err_card.metadata["card_payload"])
    assert "Fast must be less than slow" in err_dict["title"]


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

    # Capacity overflow evicts oldest
    cache.store("res-3", spec, bt, audit, "full text 3", timestamp=t0 + 30.0)
    # res-2 was least recently accessed, so it was evicted
    assert cache.get("res-2", current_time=t0 + 40.0) is None
    assert cache.get("res-1", current_time=t0 + 40.0) is not None

    # Expiration past TTL
    expired_item = cache.get("res-1", current_time=t0 + 3000.0)
    assert expired_item is None


def test_extract_selection_from_metadata():
    """extract_selection_from_message parses MetadataContent card responses."""
    card_id = uuid.uuid4()
    resp_block = create_card_response_content(card_id=card_id, selection={"action": "run_demo_a"})
    msg = ChatMessage(content=[resp_block])

    selection = extract_selection_from_message(msg)
    assert selection == {"action": "run_demo_a"}


def test_extract_selection_from_text_fallback():
    """extract_selection_from_message parses legacy JSON inside TextContent."""
    msg = ChatMessage(content=[TextContent(type="text", text='{"action": "run_demo_b"}')])
    selection = extract_selection_from_message(msg)
    assert selection == {"action": "run_demo_b"}


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
