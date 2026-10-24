"""
agents/cards.py – ASI:One Interactive Cards Protocol Generator (Phase 5)
========================================================================
Implements ASI:One Card Protocol v1 schemas via uagents_core:
  1. Strategy Picker (CarouselCardPayload) on greetings/hi/examples
  2. Headline Results Card (DetailCardPayload) with verdict badge & return vs OOS
  3. Audit Details Card (DetailCardPayload) with 4 adversarial tests breakdown
  4. Parameter Form Card (FormCardPayload) for custom/clarification input
  5. In-memory CardResultCache and ReportView dataclass
  6. Robust selection parsing for direct JSON and planner-mediated prose
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
import json
import logging
import os
import re
import time
import uuid
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

# Whitelisted action identifiers
WHITELISTED_ACTIONS = {
    "show_results",
    "show_audit",
    "full_report",
    "show_examples",
    "run_example",
    "submit_form",
    "open_form",
    # Backward compatibility with initial experimental actions
    "view_results_card",
    "view_audit_details",
    "full_text_report",
    "run_demo_a",
    "run_demo_b",
}


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
# ReportView Dataclass (Pure Python, derived from existing results dicts)
# ---------------------------------------------------------------------------

@dataclass
class ReportView:
    ticker: str
    strategy_desc: str
    assumptions: str
    data_source: str
    date_range: str
    price_type: str
    total_return_pct: float
    cagr_pct: float
    sharpe: float
    max_drawdown_pct: float
    trades: int
    win_rate_pct: float
    oos_result_text: str
    tests: List[Dict[str, Any]]
    verdict: str
    warnings: List[str]
    disclaimer: str

    @classmethod
    def from_results(
        cls,
        spec: Dict[str, Any],
        backtest: Dict[str, Any],
        audit: Dict[str, Any],
    ) -> "ReportView":
        ticker = str(spec.get("ticker", "N/A")).strip().upper()
        strat = spec.get("strategy", "ma_crossover")
        params = spec.get("params", {})
        param_desc = ", ".join(f"{k}={v}" for k, v in params.items()) or "standard defaults"
        strategy_desc = f"{strat.replace('_', ' ').title()} ({param_desc})"

        fee = spec.get("fee_pct", 0.1)
        slip = spec.get("slippage_pct", 0.05)
        assumptions = f"Fee: {fee}%, Slippage: {slip}%"

        start_date = spec.get("start", "2021-10-25")
        end_date = spec.get("end", "2026-10-23")
        data_source = "NSE Daily" if ".NS" in ticker else "Daily Close"
        date_range = f"{start_date} to {end_date}"

        tot_ret = float(backtest.get("total_return", 0.0)) * 100.0
        cagr = float(backtest.get("cagr", 0.0)) * 100.0
        sharpe = float(backtest.get("sharpe", 0.0))
        max_dd = abs(float(backtest.get("max_drawdown", 0.0))) * 100.0
        trades = int(backtest.get("trade_count", 0))
        win_rate = float(backtest.get("win_rate", 0.0)) * 100.0

        tests = audit.get("tests", [])
        oos_test = next((t for t in tests if t.get("name") in ("out_of_sample", "oos_split")), None)
        if oos_test:
            oos_sharpe = oos_test.get("oos_sharpe")
            oos_passed = oos_test.get("passed", False)
            status_word = "Held" if oos_passed else "Collapsed"
            if oos_sharpe is not None:
                oos_result_text = f"OOS Sharpe {oos_sharpe:.2f} ({status_word})"
            else:
                oos_result_text = f"OOS Split {status_word}"
        else:
            oos_result_text = "OOS Split: N/A"

        verdict = audit.get("verdict", "UNVALIDATED").strip().title()
        warnings = []
        if trades < 10:
            warnings.append(f"Low trade count ({trades} trades): limited statistical significance")
        for t in tests:
            if not t.get("passed") and t.get("name") == "cost_sensitivity":
                warnings.append("High friction drag: alpha collapses under realistic brokerage")

        disclaimer = "Trustworthy means survived these tests, not that it will make money. Educational only, not investment advice."

        return cls(
            ticker=ticker,
            strategy_desc=strategy_desc,
            assumptions=assumptions,
            data_source=data_source,
            date_range=date_range,
            price_type="adjusted prices",
            total_return_pct=tot_ret,
            cagr_pct=cagr,
            sharpe=sharpe,
            max_drawdown_pct=max_dd,
            trades=trades,
            win_rate_pct=win_rate,
            oos_result_text=oos_result_text,
            tests=tests,
            verdict=verdict,
            warnings=warnings,
            disclaimer=disclaimer,
        )


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
            "report_view": ReportView.from_results(spec, backtest, audit),
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
# Card Builders
# ---------------------------------------------------------------------------

def create_strategy_picker_card() -> MetadataContent:
    """
    Card 1: Strategy Picker Carousel sent on greetings, help, or show_examples.
    Provides one-tap execution for Demo A, Demo B, or RSI 14 TCS.
    """
    payload = CarouselCardPayload(
        title="TrustTest Strategy Showcase",
        subtitle="Select a verified benchmark or configure your own strategy below:",
        items=[
            CarouselItem(
                id="demo_a",
                title="Demo A: 50/200 MA Cross",
                subtitle="RELIANCE.NS (2021–2026)",
                badges=[CarouselBadge(label="Trustworthy Benchmark", variant="success")],
                secondary_text="Sensible 50/200 MA. Survives 70/30 OOS split and 2x friction drag.",
                primary_cta=CtaAction(
                    label="Run Demo A",
                    selection={"source": "trusttest", "action": "run_example", "example_id": "demo_a"},
                    primary=True,
                ),
            ),
            CarouselItem(
                id="demo_b",
                title="Demo B: 23/35 MA Cross",
                subtitle="RELIANCE.NS (Over-tuned)",
                badges=[CarouselBadge(label="Likely Overfit", variant="warning")],
                secondary_text="Over-tuned 23/35 MA. High backtest returns that collapse under audit.",
                primary_cta=CtaAction(
                    label="Run Demo B",
                    selection={"source": "trusttest", "action": "run_example", "example_id": "demo_b"},
                    primary=True,
                ),
            ),
            CarouselItem(
                id="rsi_tcs",
                title="Demo C: RSI 14 Mean-Rev",
                subtitle="TCS.NS (Oscillator)",
                badges=[CarouselBadge(label="RSI Mean-Reversion", variant="info")],
                secondary_text="14-period RSI (30/70 thresholds). Rigorous cost and perturbation check.",
                primary_cta=CtaAction(
                    label="Run RSI TCS",
                    selection={"source": "trusttest", "action": "run_example", "example_id": "rsi_tcs"},
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
    Card 2: Headline Results Card with key metrics, verdict badge, and the contrast
    that sells the demo: headline return next to out-of-sample result.
    """
    view = ReportView.from_results(spec, backtest, audit)
    verdict_upper = view.verdict.upper()

    summary_rows = [
        DetailSummaryRow(label="Strategy & Ticker", value=f"{view.strategy_desc} on {view.ticker}"),
        DetailSummaryRow(label="Date Range", value=f"{view.date_range} ({view.price_type})"),
        DetailSummaryRow(label="Skeptic Verdict", value=f"🛡️ [{verdict_upper}]"),
        DetailSummaryRow(label="Return vs OOS", value=f"Total: {view.total_return_pct:+.1f}% | {view.oos_result_text}"),
        DetailSummaryRow(label="Total Return / CAGR", value=f"{view.total_return_pct:+.1f}% (CAGR: {view.cagr_pct:+.1f}%)"),
        DetailSummaryRow(label="Sharpe / Max DD", value=f"Sharpe {view.sharpe:.2f} | Max DD -{view.max_drawdown_pct:.1f}%"),
        DetailSummaryRow(label="Trades (Win %)", value=f"{view.trades} trades ({view.win_rate_pct:.1f}% win)"),
    ]

    payload = DetailCardPayload(
        title=f"TrustTest: {view.ticker} [{verdict_upper}]",
        summary_rows=summary_rows,
        ctas=[
            CtaAction(
                label="See audit details",
                selection={"source": "trusttest", "action": "show_audit", "report_id": result_id},
                primary=True,
            ),
            CtaAction(
                label="Full text report",
                selection={"source": "trusttest", "action": "full_report", "report_id": result_id},
                primary=False,
            ),
            CtaAction(
                label="Try an example",
                selection={"source": "trusttest", "action": "show_examples"},
                primary=False,
            ),
        ],
    )
    return create_card_content(payload, card_id=uuid.uuid4())


def create_audit_details_card(
    result_id: str,
    spec: Dict[str, Any],
    audit: Dict[str, Any],
    backtest: Optional[Dict[str, Any]] = None,
) -> MetadataContent:
    """
    Card 3: Audit Detail Card detailing the 4 adversarial tests, warnings,
    survivorship note, and educational disclaimer.
    """
    view = ReportView.from_results(spec, backtest or {}, audit)
    verdict_upper = view.verdict.upper()

    summary_rows: List[DetailSummaryRow] = []

    # 4 adversarial tests
    for t in view.tests:
        name = t.get("name", "").replace("_", " ").title()
        status_tag = "PASS" if t.get("passed") else "FAIL"
        summary_rows.append(
            DetailSummaryRow(label=f"[{status_tag}] {name}", value=t.get("explanation", ""))
        )

    if not summary_rows:
        summary_rows.append(
            DetailSummaryRow(label="Audit Status", value=audit.get("note", "No test metrics available."))
        )

    # Warnings
    if view.warnings:
        summary_rows.append(
            DetailSummaryRow(label="⚠️ Warnings", value="; ".join(view.warnings))
        )

    # Survivorship bias note
    summary_rows.append(
        DetailSummaryRow(label="Survivorship Bias", value="Constituent survivorship applies. Delisted tickers excluded.")
    )

    # Educational disclaimer
    summary_rows.append(
        DetailSummaryRow(label="Disclaimer", value=view.disclaimer)
    )

    payload = DetailCardPayload(
        title=f"Adversarial Audit: {view.ticker} [{verdict_upper}]",
        summary_rows=summary_rows,
        ctas=[
            CtaAction(
                label="Back to results",
                selection={"source": "trusttest", "action": "show_results", "report_id": result_id},
                primary=True,
            ),
            CtaAction(
                label="Try an example",
                selection={"source": "trusttest", "action": "show_examples"},
                primary=False,
            ),
        ],
    )
    return create_card_content(payload, card_id=uuid.uuid4())


def create_parameter_form_card(
    partial_spec: Optional[Dict[str, Any]] = None,
    error_msg: Optional[str] = None,
) -> MetadataContent:
    """
    Card 4: Interactive Parameter Form Card pre-filled with what is already known.
    """
    partial = partial_spec or {}
    params = partial.get("params", {})
    ticker_val = str(partial.get("ticker", "RELIANCE.NS")).upper()
    fast_val = str(params.get("fast", 50))
    slow_val = str(params.get("slow", 200))

    title = "Configure Strategy Parameters"
    if error_msg:
        title = f"Validation Error: {error_msg}"

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
                label="Fast Moving Average Window (days)",
                required=True,
                placeholder=fast_val,
            ),
            FormField(
                name="slow",
                kind="number",
                label="Slow Moving Average Window (days)",
                required=True,
                placeholder=slow_val,
            ),
            FormField(
                name="duration_years",
                kind="select",
                label="Historical Backtest Window",
                required=True,
                options=[
                    FormFieldOption(label="5 Years (Institutional Standard)", value="5"),
                    FormFieldOption(label="3 Years", value="3"),
                    FormFieldOption(label="2 Years", value="2"),
                ],
            ),
        ],
        submit_cta=CtaAction(
            label="Run Backtest & Audit",
            selection={"source": "trusttest", "action": "submit_form"},
            primary=True,
        ),
    )
    return create_card_content(payload, card_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# Card Selection Parsing & Routing Helpers
# ---------------------------------------------------------------------------

_JSON_EXTRACT_RE = re.compile(r"\{[^{}]*\}")


def parse_card_selection(text_or_msg: Any) -> Optional[Dict[str, Any]]:
    """
    Robust extraction and validation of card CTA selection payload:
      1. Inspects MetadataContent blocks via uagents_core extract_card_response
      2. Accepts direct JSON payload in text
      3. Accepts JSON object embedded inside prose (planner-mediated path)
      4. Whitelists source ('trusttest') and valid actions
      5. Enforces input length bounds (<= 2000 chars)

    Returns validated selection dict, or None to fall back to normal text path.
    """
    if text_or_msg is None:
        return None

    # Path 1: Check MetadataContent if a ChatMessage-like object is provided
    content_list = getattr(text_or_msg, "content", None)
    if isinstance(content_list, list):
        for item in content_list:
            if isinstance(item, MetadataContent):
                resp = extract_card_response(item)
                if resp and resp.selection and isinstance(resp.selection, dict):
                    sel = resp.selection
                    action = sel.get("action")
                    if action in WHITELISTED_ACTIONS:
                        return sel

        # If no MetadataContent hit, combine any text blocks for text inspection
        text_parts = [
            getattr(it, "text", "")
            for it in content_list
            if getattr(it, "text", "")
        ]
        text_candidate = " ".join(text_parts).strip()
    elif isinstance(text_or_msg, str):
        text_candidate = text_or_msg.strip()
    else:
        text_candidate = str(text_or_msg).strip()

    if not text_candidate or len(text_candidate) > 2000:
        return None

    # Path 2: Direct JSON payload
    if text_candidate.startswith("{") and text_candidate.endswith("}"):
        try:
            data = json.loads(text_candidate)
            if isinstance(data, dict):
                src = data.get("source")
                act = data.get("action")
                if (src == "trusttest" or not src) and act in WHITELISTED_ACTIONS:
                    return data
        except Exception:
            pass

    # Path 3: JSON embedded inside prose (planner-mediated path)
    matches = _JSON_EXTRACT_RE.findall(text_candidate)
    for m in matches:
        try:
            data = json.loads(m)
            if isinstance(data, dict):
                src = data.get("source")
                act = data.get("action")
                if (src == "trusttest" or not src) and act in WHITELISTED_ACTIONS:
                    return data
        except Exception:
            continue

    return None


# Backward-compatible alias
extract_selection_from_message = parse_card_selection
