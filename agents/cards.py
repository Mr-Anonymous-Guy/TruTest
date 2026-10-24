"""
agents/cards.py – ASI:One Interactive Cards Protocol Generator (Phase 5)
========================================================================
Implements ASI:One Card Protocol v1 schemas via uagents_core:
  1. Strategy Picker (CarouselCardPayload) on greetings/hi
  2. Headline Results Card (DetailCardPayload) with verdict badge
  3. Audit Details Card (DetailCardPayload) with adversarial breakdown
  4. Parameter Form Card (FormCardPayload) for custom strategy submission
  5. In-memory CardResultCache with TTL for instant tab navigation
  6. Pure text fallback when TRUSTTEST_CARDS=off
"""

from __future__ import annotations

import collections
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from uagents_core.contrib.protocols.chat import MetadataContent
from uagents_core.contrib.protocols.chat.cards import (
    CarouselBadge,
    CarouselCardPayload,
    CarouselItem,
    CtaAction,
    DetailCardPayload,
    DetailSummaryRow,
    FormCardPayload,
    FormField,
    FormFieldOption,
    create_card_content,
    extract_card_response,
)

logger = logging.getLogger("trusttest.cards")


def are_cards_enabled() -> bool:
    """Return True if interactive cards are enabled (default ON)."""
    val = os.getenv("TRUSTTEST_CARDS", "on").strip().lower()
    return val not in ("off", "false", "0", "no")


def get_card_ttl_seconds() -> float:
    """Get card result expiration TTL in seconds (default 30 min = 1800s)."""
    try:
        return float(os.getenv("TRUSTTEST_CARD_TTL", "1800"))
    except ValueError:
        return 1800.0


# ---------------------------------------------------------------------------
# Card Result Cache (Bounded LRU with TTL)
# ---------------------------------------------------------------------------

class CardResultCache:
    """
    Caches recent pipeline results by result_id so users can toggle between
    Results Card and Audit Details Card without re-running the pipeline.
    """

    def __init__(self, max_size: int = 500) -> None:
        self.max_size = max_size
        self._cache: collections.OrderedDict[str, Dict[str, Any]] = collections.OrderedDict()

    def store(
        self,
        result_id: str,
        spec: Dict[str, Any],
        backtest: Dict[str, Any],
        audit: Dict[str, Any],
        full_text: str,
        timestamp: Optional[float] = None,
    ) -> None:
        now = timestamp if timestamp is not None else time.time()
        self._purge_expired(now)

        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        self._cache[result_id] = {
            "spec": spec,
            "backtest": backtest,
            "audit": audit,
            "full_text": full_text,
            "created_at": now,
        }

    def get(self, result_id: str, current_time: Optional[float] = None) -> Optional[Dict[str, Any]]:
        now = current_time if current_time is not None else time.time()
        self._purge_expired(now)

        if result_id not in self._cache:
            return None

        item = self._cache[result_id]
        ttl = get_card_ttl_seconds()
        if (now - item["created_at"]) > ttl:
            del self._cache[result_id]
            return None

        self._cache.move_to_end(result_id)
        return item

    def _purge_expired(self, now: float) -> None:
        ttl = get_card_ttl_seconds()
        expired = [k for k, v in self._cache.items() if (now - v["created_at"]) > ttl]
        for k in expired:
            del self._cache[k]


# Global In-Memory Card Result Cache
card_cache = CardResultCache()


# ---------------------------------------------------------------------------
# Card Generators
# ---------------------------------------------------------------------------

def create_strategy_picker_card() -> MetadataContent:
    """
    Card 1: Strategy Picker Carousel sent on 'hi' or greeting.
    Provides one-tap execution for Demo A, Demo B, or Custom Form.
    """
    payload = CarouselCardPayload(
        title="TrustTest Strategy Showcase",
        subtitle="Select a verified benchmark or configure your own strategy below:",
        items=[
            CarouselItem(
                id="demo_a",
                title="Demo A: 50/200 MA Cross",
                subtitle="RELIANCE.NS (2018–2024)",
                badges=[CarouselBadge(label="Trustworthy Benchmark", variant="success")],
                secondary_text="Survives 70/30 OOS split, cost 2x drag, and beats random baseline.",
                primary_cta=CtaAction(
                    label="Run Demo A",
                    selection={"action": "run_demo_a"},
                    primary=True,
                ),
            ),
            CarouselItem(
                id="demo_b",
                title="Demo B: 10/30 MA Cross",
                subtitle="RELIANCE.NS (2021–2023 Overfit)",
                badges=[CarouselBadge(label="Overfit Takedown", variant="warning")],
                secondary_text="Impressive in-sample returns that collapse under adversarial audit.",
                primary_cta=CtaAction(
                    label="Run Demo B",
                    selection={"action": "run_demo_b"},
                    primary=True,
                ),
            ),
            CarouselItem(
                id="custom_form",
                title="Custom Parameter Form",
                subtitle="Tune MA Windows & Dates",
                badges=[CarouselBadge(label="Interactive Form", variant="info")],
                secondary_text="Configure stock symbols, moving average fast/slow days, and duration.",
                primary_cta=CtaAction(
                    label="Open Parameter Form",
                    selection={"action": "open_form"},
                    primary=True,
                ),
            ),
        ],
    )
    return create_card_content(payload, card_id=uuid.uuid4())


def create_results_card(
    result_id: str,
    spec: Dict[str, Any],
    backtest: Dict[str, Any],
    audit: Dict[str, Any],
) -> MetadataContent:
    """
    Card 2: Headline Results Card with performance metrics and Skeptic verdict.
    """
    ticker = spec.get("ticker", "N/A")
    strat_name = spec.get("strategy", "Strategy").replace("_", " ").title()
    params = spec.get("params", {})
    param_str = ", ".join(f"{k}={v}" for k, v in params.items())

    tot_ret = backtest.get("total_return", 0.0) * 100
    sharpe = backtest.get("sharpe", 0.0)
    max_dd = backtest.get("max_drawdown", 0.0) * 100
    trades = backtest.get("trade_count", 0)
    win_rate = backtest.get("win_rate", 0.0) * 100
    verdict = audit.get("verdict", "UNVALIDATED").upper()

    summary_rows = [
        DetailSummaryRow(label="Strategy & Ticker", value=f"{strat_name} on {ticker}"),
        DetailSummaryRow(label="Parameters", value=param_str or "Standard defaults"),
        DetailSummaryRow(label="Total Return", value=f"{tot_ret:+.2f}%"),
        DetailSummaryRow(label="Sharpe Ratio", value=f"{sharpe:.2f}"),
        DetailSummaryRow(label="Max Drawdown", value=f"{max_dd:.2f}%"),
        DetailSummaryRow(label="Trades (Win %)", value=f"{trades} trades ({win_rate:.1f}% win)"),
        DetailSummaryRow(label="Skeptic Verdict", value=f"🛡️ {verdict}"),
    ]

    payload = DetailCardPayload(
        title=f"TrustTest Results: {ticker}",
        summary_rows=summary_rows,
        ctas=[
            CtaAction(
                label="See Audit Details",
                selection={"action": "view_audit_details", "result_id": result_id},
                primary=True,
            ),
            CtaAction(
                label="Full Text Report",
                selection={"action": "full_text_report", "result_id": result_id},
                primary=False,
            ),
        ],
    )
    return create_card_content(payload, card_id=uuid.uuid4())


def create_audit_details_card(
    result_id: str,
    spec: Dict[str, Any],
    audit: Dict[str, Any],
) -> MetadataContent:
    """
    Card 3: Audit Detail Card detailing the 4 adversarial tests and findings.
    """
    ticker = spec.get("ticker", "N/A")
    verdict = audit.get("verdict", "UNVALIDATED").upper()
    tests = audit.get("tests", [])

    summary_rows = []
    for t in tests:
        name = t.get("name", "").replace("_", " ").title()
        status_tag = "PASS" if t.get("passed") else "FAIL"
        summary_rows.append(
            DetailSummaryRow(label=f"[{status_tag}] {name}", value=t.get("explanation", ""))
        )

    if not summary_rows:
        summary_rows.append(
            DetailSummaryRow(label="Audit Status", value=audit.get("note", "No test metrics available."))
        )

    summary_rows.append(DetailSummaryRow(label="Final Verdict", value=f"🛡️ {verdict}"))

    payload = DetailCardPayload(
        title=f"Adversarial Audit Breakdown: {ticker}",
        summary_rows=summary_rows,
        ctas=[
            CtaAction(
                label="Back to Results",
                selection={"action": "view_results_card", "result_id": result_id},
                primary=True,
            ),
            CtaAction(
                label="Full Text Report",
                selection={"action": "full_text_report", "result_id": result_id},
                primary=False,
            ),
        ],
    )
    return create_card_content(payload, card_id=uuid.uuid4())


def create_parameter_form_card(error_msg: Optional[str] = None) -> MetadataContent:
    """
    Card 4: Interactive Parameter Form Card for custom strategy inputs.
    """
    title = "Configure Strategy Parameters"
    if error_msg:
        title = f"Form Error: {error_msg}"

    payload = FormCardPayload(
        title=title,
        fields=[
            FormField(
                name="ticker",
                kind="select",
                label="Select Asset Ticker",
                required=True,
                options=[
                    FormFieldOption(label="RELIANCE.NS (Reliance Industries)", value="RELIANCE.NS"),
                    FormFieldOption(label="TCS.NS (Tata Consultancy Services)", value="TCS.NS"),
                    FormFieldOption(label="INFY.NS (Infosys Limited)", value="INFY.NS"),
                    FormFieldOption(label="HDFCBANK.NS (HDFC Bank)", value="HDFCBANK.NS"),
                    FormFieldOption(label="AAPL (Apple Inc.)", value="AAPL"),
                ],
            ),
            FormField(
                name="fast",
                kind="number",
                label="Fast Moving Average (days)",
                required=True,
                placeholder="50",
            ),
            FormField(
                name="slow",
                kind="number",
                label="Slow Moving Average (days)",
                required=True,
                placeholder="200",
            ),
            FormField(
                name="duration_years",
                kind="select",
                label="Historical Evaluation Window",
                required=True,
                options=[
                    FormFieldOption(label="5 Years (Institutional Standard)", value="5"),
                    FormFieldOption(label="3 Years", value="3"),
                    FormFieldOption(label="2 Years", value="2"),
                ],
            ),
        ],
        submit_cta=CtaAction(
            label="Submit Backtest & Audit",
            selection={"action": "submit_form"},
            primary=True,
        ),
    )
    return create_card_content(payload, card_id=uuid.uuid4())


def extract_selection_from_message(msg: Any) -> Optional[Dict[str, Any]]:
    """
    Robust extraction of card CTA selection payload:
      1. Inspects MetadataContent blocks using official extract_card_response
      2. Falls back to parsing JSON in TextContent for legacy clients
    """
    # 1. Official MetadataContent path
    for item in getattr(msg, "content", []):
        if isinstance(item, MetadataContent):
            resp = extract_card_response(item)
            if resp and resp.selection:
                return resp.selection

    # 2. Backwards-compatible text path
    for item in getattr(msg, "content", []):
        text = getattr(item, "text", "")
        if text and text.strip().startswith("{") and text.strip().endswith("}"):
            try:
                data = json.loads(text.strip())
                if isinstance(data, dict) and "action" in data:
                    return data
            except Exception:
                pass

    return None
