"""
agents/orchestrator.py – TrustTest Orchestrator Agent (Port 8001)
================================================================
ASI:One-facing gateway implementing Agent Chat Protocol (ACP) 0.3.0 & Cards Protocol v1.
Coordinates the multi-agent pipeline:
User -> Orchestrator -> Parser -> Data -> Backtest -> Skeptic -> Final Report.

Phase 4 Reliability:
  - Error taxonomy & one-shot transient retries (call_with_retry)
  - Per-request deadline countdown (RequestBudget: 120s)
  - Duplicate message deduplication (MessageDeduplicator)
  - Concurrency guard (single pipeline per sender)
  - Sliding-window rate limiting (6 req/min per sender)
  - Bounded session store with 30-min idle TTL eviction
  - Centralized user copy (agents/messages.py)
  - Status command with multi-agent health check
  - Step-by-step trace logging (logs/trace.jsonl, logs/latest_trace.json)
  - Partial results when Skeptic is unavailable (no verdict, unvalidated notice)
  - Timing footer on full results

Phase 5 Interactive Cards:
  - Strategy Picker CarouselCardPayload on greeting / hi
  - Headline Results DetailCardPayload with Skeptic verdict badge
  - Audit Breakdown DetailCardPayload with 4 adversarial tests
  - Parameter FormCardPayload with validation for custom strategy submissions
  - In-memory CardResultCache for fast card tab toggling
  - Pure text fallback when TRUSTTEST_CARDS=off
"""

from __future__ import annotations

import collections
import datetime
import json
import logging
import os
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(str(Path(__file__).resolve().parent.parent)))

from dotenv import load_dotenv
from uagents import Agent, Context, Model, Protocol
from uagents.crypto import Identity
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agents import messages
from agents.cards import (
    ReportView,
    are_cards_enabled,
    card_cache,
    create_audit_details_card,
    create_parameter_form_card,
    create_results_card,
    create_strategy_picker_card,
    parse_card_selection,
)
from agents.faults import check_and_log_faults_startup
from agents.models import (
    AuditRequest,
    AuditResponse,
    BacktestRequest,
    BacktestResponse,
    DataRequest,
    HealthRequest,
    HealthResponse,
    ParseRequest,
    ParseResponse,
    PriceData,
    df_to_price_data,
)
from agents.pipeline import format_final_reply
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
from agents.trace import record_hop_event, save_full_pipeline_trace

# ---------------------------------------------------------------------------
# Configuration & Environment
# ---------------------------------------------------------------------------
load_dotenv()

ORCHESTRATOR_SEED = os.getenv("ORCHESTRATOR_SEED")
if not ORCHESTRATOR_SEED or ORCHESTRATOR_SEED.strip() in ("", "REPLACE_WITH_RANDOM_SEED", "REPLACE_ME"):
    raise RuntimeError(
        "ORCHESTRATOR_SEED is missing or unconfigured in .env. "
        "Please provide a valid seed string in your .env file."
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("trusttest_orchestrator")


def _get_addr(env_var: str, default_seed: str) -> str:
    addr = os.getenv(env_var)
    if addr and addr.strip():
        return addr.strip()
    return Identity.from_seed(default_seed, 0).address


PARSER_AGENT_ADDRESS = _get_addr("PARSER_AGENT_ADDRESS", os.getenv("PARSER_SEED", "trusttest_parser_agent_seed_fetchathon3_2026"))
DATA_AGENT_ADDRESS = _get_addr("DATA_AGENT_ADDRESS", os.getenv("DATA_SEED", "trusttest_data_agent_seed_fetchathon3_2026"))
BACKTEST_AGENT_ADDRESS = _get_addr("BACKTEST_AGENT_ADDRESS", os.getenv("BACKTEST_SEED", "trusttest_backtest_agent_seed_fetchathon3_2026"))
SKEPTIC_AGENT_ADDRESS = _get_addr("SKEPTIC_AGENT_ADDRESS", os.getenv("SKEPTIC_SEED", "trusttest_skeptic_agent_seed_fetchathon3_2026"))

# Reliability & Card State Primitives
session_store = BoundedSessionStore(max_sessions=1000, ttl_seconds=1800.0)
concurrency_guard = ConcurrencyGuard()
rate_limiter = RateLimiter(max_requests=6, window_seconds=60.0)
dedup = MessageDeduplicator(max_size=2000)

_orchestrator_start_time = time.time()
check_and_log_faults_startup("trusttest_orchestrator")

# ---------------------------------------------------------------------------
# Stored Benchmark Examples (Server-Side Resolution)
# ---------------------------------------------------------------------------
STORED_EXAMPLES: Dict[str, Dict[str, Any]] = {
    "demo_a": {
        "ticker": "RELIANCE.NS",
        "strategy": "ma_crossover",
        "params": {"fast": 50, "slow": 200},
        "fee_pct": 0.1,
        "slippage_pct": 0.05,
        "start": "2021-10-25",
        "end": "2026-10-23",
        "label": "Demo A (Sensible 50/200 MA on RELIANCE.NS)",
    },
    "demo_b": {
        "ticker": "RELIANCE.NS",
        "strategy": "ma_crossover",
        "params": {"fast": 23, "slow": 35},
        "fee_pct": 0.1,
        "slippage_pct": 0.05,
        "start": "2021-10-25",
        "end": "2026-10-23",
        "label": "Demo B (Over-tuned 23/35 MA on RELIANCE.NS)",
    },
    "rsi_tcs": {
        "ticker": "TCS.NS",
        "strategy": "rsi_meanrev",
        "params": {"period": 14, "oversold": 30, "overbought": 70},
        "fee_pct": 0.1,
        "slippage_pct": 0.05,
        "start": "2021-10-25",
        "end": "2026-10-23",
        "label": "Demo C (14-period RSI on TCS.NS)",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def create_text_chat(text: str) -> ChatMessage:
    """Helper to construct a ChatMessage containing TextContent."""
    return ChatMessage(content=[TextContent(type="text", text=text)])


def check_agent_health() -> str:
    """Check health and ping latency across all 5 agents (Phase 4)."""
    agents = [
        ("Orchestrator", 8001),
        ("Strategy Parser", 8005),
        ("Market Data Agent", 8002),
        ("Backtest Engine", 8003),
        ("Skeptic Auditor", 8004),
    ]
    lines = [
        "🛡️ TrustTest Multi-Agent Health Status:\n",
        "| Agent | Port | Status | Latency |",
        "|---|:---:|:---:|:---:|",
    ]
    all_healthy = True
    for name, port in agents:
        t0 = time.perf_counter()
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.8):
                elapsed_ms = (time.perf_counter() - t0) * 1000
                lines.append(f"| **{name}** | {port} | 🟢 Healthy | {elapsed_ms:.0f}ms |")
        except Exception:
            all_healthy = False
            lines.append(f"| **{name}** | {port} | 🔴 Offline | - |")

    if all_healthy:
        lines.append("\n✅ All 5 agents are online, healthy, and operational.")
    else:
        lines.append("\n⚠️ Some agents are offline. Start offline agents with their respective launch commands.")
    return "\n".join(lines)


def save_trace(req_id: str, sender: str, user_text: str, steps: list, start_time: float) -> None:
    """Save execution trace for scripts/show_trace.py (Phase 4)."""
    total_ms = (time.perf_counter() - start_time) * 1000
    save_full_pipeline_trace(req_id, sender, user_text, steps, total_ms)


# ---------------------------------------------------------------------------
# Agent Construction
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_orchestrator",
    seed=ORCHESTRATOR_SEED,
    port=8001,
    mailbox=True,
    publish_agent_details=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    """Handle and log chat acknowledgements."""
    ctx.logger.info("ChatAcknowledgement received from %s for msg_id: %s", sender, msg.acknowledged_msg_id)


async def send_worker_request(
    ctx: Context,
    destination: str,
    message: Model,
    response_type: type[Model],
    timeout: float = 30.0,
) -> Optional[Model]:
    """
    Send typed request to a worker agent via send_and_receive.
    Falls back to direct execution if worker agent is not yet reachable over mailbox relay.
    """
    t0 = time.perf_counter()
    ctx.logger.info("Sending %s to %s (timeout: %.1fs)", type(message).__name__, destination, timeout)
    try:
        resp, status = await ctx.send_and_receive(destination, message, response_type=response_type, timeout=int(max(1, timeout)))
        elapsed = time.perf_counter() - t0
        ctx.logger.info("send_and_receive to %s finished in %.2fs (status: %s)", destination, elapsed, status)
        if resp is not None:
            return resp
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        ctx.logger.warning("send_and_receive to %s failed in %.2fs: %s. Using direct fallback execution.", destination, elapsed, exc)

    # Resilient local fallback execution so offline tests & demo never hang
    try:
        if isinstance(message, ParseRequest):
            from agents.parser_agent import parse_strategy_text
            res = parse_strategy_text(message.text, context=message.context)
            res.request_id = message.request_id
            return res
        elif isinstance(message, DataRequest):
            from agents.data_source import fetch_prices
            df, src, note = fetch_prices(message.ticker, start=message.start, end=message.end)
            return df_to_price_data(message.request_id, df, message.ticker, src, note=note, ok=True)
        elif isinstance(message, BacktestRequest):
            from agents.backtest_agent import execute_backtest
            b_dict = execute_backtest(message.spec, message.prices)
            return BacktestResponse(request_id=message.request_id, ok=True, result=b_dict)
        elif isinstance(message, AuditRequest):
            from agents.skeptic_agent import execute_audit
            a_dict = execute_audit(message.spec, message.prices)
            return AuditResponse(request_id=message.request_id, ok=True, report=a_dict)
    except Exception as fb_exc:
        ctx.logger.error("Direct fallback execution for %s failed: %s", type(message).__name__, fb_exc)
        if response_type == ParseResponse:
            return ParseResponse(request_id=message.request_id, ok=False, error=str(fb_exc))
        elif response_type == PriceData:
            return PriceData(request_id=message.request_id, ok=False, ticker="", source="error", start="", end="", bars=0, dates=[], closes=[], error=str(fb_exc))
        elif response_type == BacktestResponse:
            return BacktestResponse(request_id=message.request_id, ok=False, error=str(fb_exc))
        elif response_type == AuditResponse:
            return AuditResponse(request_id=message.request_id, ok=False, error=str(fb_exc))

    return None


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    """Receive and process incoming chat messages from ASI:One."""
    # 1. ALWAYS acknowledge receipt first
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

    # 2. Deduplicate message IDs (ASI:One at-least-once delivery protection)
    if dedup.is_duplicate(msg.msg_id):
        ctx.logger.info("Ignoring duplicate msg_id %s from %s", msg.msg_id, sender)
        return

    content_types = [type(item).__name__ for item in msg.content]
    ctx.logger.info("Message received from %s with content types: %s", sender, content_types)

    try:
        sess = session_store.get_or_create(sender)
        raw_user_text = ""
        has_start_session = False
        has_end_session = False

        for item in msg.content:
            if isinstance(item, StartSessionContent):
                has_start_session = True
            elif isinstance(item, TextContent):
                raw_user_text += item.text
            elif isinstance(item, EndSessionContent):
                has_end_session = True

        if raw_user_text:
            # Strip ASI:One agent address or name mention prefixes (e.g. '@agent1qwlf... Hello')
            raw_user_text = re.sub(r"^@agent1[a-z0-9]+\s*", "", raw_user_text, flags=re.IGNORECASE)
            raw_user_text = re.sub(r"^@\S+\s*", "", raw_user_text).strip()

        if has_end_session:
            session_store.clear(sender)
            ctx.logger.info("Cleaned up session state for %s", sender)
            return

        # -------------------------------------------------------------------
        # Phase 5: Handle Card Tap Selections
        # -------------------------------------------------------------------
        pre_resolved_spec: Optional[Dict[str, Any]] = None
        example_label: Optional[str] = None
        card_action = parse_card_selection(msg)

        if card_action:
            action = card_action.get("action")
            ctx.logger.info("Card action received from %s: '%s'", sender, action)

            # Display actions: bypass concurrency guard, read stored report
            if action in ("show_audit", "view_audit_details"):
                res_id = card_action.get("report_id") or card_action.get("result_id")
                recent = sess.get("recent_reports", {})
                cached = recent.get(res_id) if recent else None
                if not cached and res_id:
                    cached = card_cache.get(res_id)
                if not cached:
                    await ctx.send(sender, create_text_chat("⚠️ That result has expired, please run the strategy again or choose an example from 'hi'."))
                    return
                audit_card = create_audit_details_card(res_id, cached["spec"], cached["audit"], cached.get("backtest"))
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=f"Adversarial Audit Breakdown for {cached['spec']['ticker']}:"), audit_card]))
                return

            elif action in ("show_results", "view_results_card"):
                res_id = card_action.get("report_id") or card_action.get("result_id")
                recent = sess.get("recent_reports", {})
                cached = recent.get(res_id) if recent else None
                if not cached and res_id:
                    cached = card_cache.get(res_id)
                if not cached:
                    await ctx.send(sender, create_text_chat("⚠️ That result has expired, please run the strategy again or choose an example from 'hi'."))
                    return
                res_card = create_results_card(res_id, cached["spec"], cached["backtest"], cached["audit"])
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=f"Backtest Results for {cached['spec']['ticker']}:"), res_card]))
                return

            elif action in ("full_report", "full_text_report"):
                res_id = card_action.get("report_id") or card_action.get("result_id")
                recent = sess.get("recent_reports", {})
                cached = recent.get(res_id) if recent else None
                if not cached and res_id:
                    cached = card_cache.get(res_id)
                if not cached:
                    await ctx.send(sender, create_text_chat("⚠️ That result has expired, please run the strategy again or choose an example from 'hi'."))
                    return
                await ctx.send(sender, create_text_chat(cached["full_text"]))
                return

            elif action == "show_examples":
                if are_cards_enabled():
                    picker_card = create_strategy_picker_card()
                    await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text="Select a verified benchmark example below or type a custom strategy:"), picker_card]))
                else:
                    await ctx.send(sender, create_text_chat(messages.WELCOME_GREETING))
                return

            elif action in ("open_form",):
                form_card = create_parameter_form_card()
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text="Configure your custom strategy parameters below:"), form_card]))
                return

            elif action == "run_example":
                ex_id = str(card_action.get("example_id", "")).strip().lower()
                if ex_id not in STORED_EXAMPLES:
                    await ctx.send(sender, create_text_chat("⚠️ Unknown example ID. Please select Demo A, Demo B, or RSI TCS from the examples picker."))
                    return
                ex = STORED_EXAMPLES[ex_id]
                pre_resolved_spec = dict(ex)
                example_label = ex.get("label", ex_id)
                raw_user_text = f"Running stored example: {example_label}"

            elif action == "run_demo_a":
                ex = STORED_EXAMPLES["demo_a"]
                pre_resolved_spec = dict(ex)
                example_label = ex.get("label")
                raw_user_text = f"Running stored example: {example_label}"

            elif action == "run_demo_b":
                ex = STORED_EXAMPLES["demo_b"]
                pre_resolved_spec = dict(ex)
                example_label = ex.get("label")
                raw_user_text = f"Running stored example: {example_label}"

            elif action == "submit_form":
                ticker = str(card_action.get("ticker", "RELIANCE.NS")).strip().upper()
                try:
                    fast = int(card_action.get("fast", 50))
                    slow = int(card_action.get("slow", 200))
                    duration = int(card_action.get("duration_years", 5))
                except (ValueError, TypeError):
                    err = "Invalid moving average window: integers required."
                    sess["form_attempts"] = sess.get("form_attempts", 0) + 1
                    if are_cards_enabled() and sess["form_attempts"] <= 2:
                        form_card = create_parameter_form_card(error_msg=err)
                        await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=f"⚠️ {err}"), form_card]))
                    else:
                        await ctx.send(sender, create_text_chat(f"⚠️ {err}"))
                    return

                if fast <= 0 or slow <= 0 or fast >= slow:
                    err = f"Fast window ({fast}) must be strictly less than slow window ({slow})."
                    sess["form_attempts"] = sess.get("form_attempts", 0) + 1
                    if are_cards_enabled() and sess["form_attempts"] <= 2:
                        form_card = create_parameter_form_card(
                            partial_spec={"ticker": ticker, "params": {"fast": fast, "slow": slow}},
                            error_msg=err,
                        )
                        await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=f"⚠️ {err}"), form_card]))
                    else:
                        await ctx.send(sender, create_text_chat(f"⚠️ {err}"))
                    return

                sess["form_attempts"] = 0
                pre_resolved_spec = {
                    "ticker": ticker,
                    "strategy": "ma_crossover",
                    "params": {"fast": fast, "slow": slow},
                    "fee_pct": 0.1,
                    "slippage_pct": 0.05,
                    "start": "2021-10-25",
                    "end": "2026-10-23",
                }
                raw_user_text = f"Form submitted: {fast}/{slow} MA crossover on {ticker}"

        # -------------------------------------------------------------------
        # Plain Text Commands (Status, Full Report, Custom Form, Greeting)
        # -------------------------------------------------------------------
        cleaned_text = raw_user_text.strip().lower()

        # Status command (Task 4: Fast Health Ping, No LLM)
        if cleaned_text in ("status", "/status", "health"):
            health_report = check_agent_health()
            await ctx.send(sender, create_text_chat(health_report))
            return

        # Full text report request by plain text (works even with cards off)
        if cleaned_text in ("full report", "/report", "full text report", "details"):
            recent = sess.get("recent_reports", {})
            last_id = sess.get("last_result_id")
            cached = recent.get(last_id) if (recent and last_id) else None
            if not cached and last_id:
                cached = card_cache.get(last_id)
            if cached and "full_text" in cached:
                await ctx.send(sender, create_text_chat(cached["full_text"]))
                return
            await ctx.send(sender, create_text_chat("No recent backtest report found in this session. Send a strategy or type 'hi' for benchmark examples."))
            return

        # Form opener command
        if cleaned_text in (
            "form", "open form", "configure", "configure strategy", "custom", "custom strategy",
            "backtest a moving average strategy", "create strategy", "parameters", "/form"
        ):
            if are_cards_enabled():
                form_card = create_parameter_form_card()
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text="Configure your custom strategy parameters below:"), form_card]))
                return

        # Greeting / Start Session
        is_greeting = cleaned_text in ("hi", "hello", "hey", "start", "/start", "help") or (has_start_session and not raw_user_text.strip())
        if is_greeting:
            if are_cards_enabled():
                picker_card = create_strategy_picker_card()
                await ctx.send(sender, ChatMessage(content=[TextContent(type="text", text=messages.WELCOME_GREETING), picker_card]))
            else:
                await ctx.send(sender, create_text_chat(messages.WELCOME_GREETING))
            return

        # 3. Input Sanitization & Bounds Checking (Task 2)
        is_valid_input, user_text, input_error = sanitize_input(raw_user_text, max_chars=1000)
        if not is_valid_input:
            if input_error == "too_long":
                await ctx.send(sender, create_text_chat(messages.MSG_TOO_LONG))
            elif input_error == "empty" and not has_start_session:
                await ctx.send(sender, create_text_chat(messages.MSG_EMPTY))
            return

        # 4. Sliding-Window Rate Limiter (Task 2: 6 req/min per sender)
        if not rate_limiter.allow(sender):
            ctx.logger.warning("Sender %s exceeded rate limit", sender)
            await ctx.send(sender, create_text_chat(messages.RATE_LIMITED))
            return

        # 5. Concurrency Guard (Task 2: Single pipeline per sender)
        if not concurrency_guard.acquire(sender):
            ctx.logger.info("Sender %s submitted request while another is active", sender)
            await ctx.send(sender, create_text_chat(messages.STILL_WORKING))
            return

        budget = RequestBudget(total_seconds=120.0)
        t_start = time.perf_counter()
        trace_steps: List[Dict[str, Any]] = []
        req_id = f"tt-{int(datetime.datetime.now().timestamp() * 1000)}"
        ctx.logger.info("Processing pipeline request [%s] for %s: '%.200s'", req_id, sender, user_text)

        try:
            # --- HOP 1: PARSER AGENT (Skipped for pre-resolved stored examples & forms) ---
            t1_ms: float = 0.0
            if pre_resolved_spec:
                spec = pre_resolved_spec
                assumptions = "Pre-configured verified benchmark parameters" if example_label else "Submitted form parameters"
                trace_steps.append({
                    "hop": 1,
                    "agent": "Strategy Parser",
                    "status": "SUCCESS",
                    "latency_ms": 0.0,
                    "details": f"Server-side resolved: {spec.get('strategy')} on {spec.get('ticker')}",
                })
                ctx.logger.info("Hop 1 bypassed [%s]: Pre-resolved spec %s on %s", req_id, spec.get("strategy"), spec.get("ticker"))
            else:
                t1_start = time.perf_counter()
                parse_req = ParseRequest(request_id=req_id, text=user_text, context=sess.get("partial_spec"))
                step1_timeout = budget.clamp_timeout(30.0)

                async def _call_parser():
                    res = await send_worker_request(
                        ctx, PARSER_AGENT_ADDRESS, parse_req, ParseResponse, timeout=step1_timeout
                    )
                    if res is None:
                        raise TransientError("Parser agent did not respond within timeout.")
                    return res

                parse_res: Optional[ParseResponse] = None
                try:
                    parse_res = await _call_parser()
                except TransientError:
                    ctx.logger.warning("Parser timed out on attempt 1 [%s]; retrying...", req_id)
                    record_hop_event(req_id, sender, "Strategy Parser", "timeout", (time.perf_counter() - t1_start) * 1000, attempt=1)
                    try:
                        parse_res = await _call_parser()
                    except Exception as p_exc:
                        ctx.logger.error("Parser failed on retry [%s]: %s", req_id, p_exc)

                t1_ms = (time.perf_counter() - t1_start) * 1000

                if not parse_res:
                    record_hop_event(req_id, sender, "Strategy Parser", "timeout", t1_ms, attempt=2)
                    trace_steps.append({"hop": 1, "agent": "Strategy Parser", "status": "FAILED", "latency_ms": t1_ms, "details": "Parser Agent timed out after retry"})
                    save_full_pipeline_trace(req_id, sender, user_text, trace_steps, (time.perf_counter() - t_start) * 1000)
                    await ctx.send(sender, create_text_chat(messages.PARSER_FAILED))
                    return

                if not parse_res.ok:
                    if parse_res.question:
                        session_store.update_partial_spec(sender, parse_res.spec)
                        record_hop_event(req_id, sender, "Strategy Parser", "clarification", t1_ms, note=parse_res.question)
                        trace_steps.append({"hop": 1, "agent": "Strategy Parser", "status": "CLARIFICATION", "latency_ms": t1_ms, "details": parse_res.question})
                        save_full_pipeline_trace(req_id, sender, user_text, trace_steps, (time.perf_counter() - t_start) * 1000)

                        attempts = sess.get("form_attempts", 0)
                        if are_cards_enabled() and attempts < 2:
                            sess["form_attempts"] = attempts + 1
                            form_card = create_parameter_form_card(partial_spec=parse_res.spec)
                            await ctx.send(
                                sender,
                                ChatMessage(content=[TextContent(type="text", text=parse_res.question), form_card]),
                            )
                        else:
                            await ctx.send(sender, create_text_chat(parse_res.question))
                        return
                    else:
                        err_msg = parse_res.error or "Could not parse strategy."
                        record_hop_event(req_id, sender, "Strategy Parser", "user_error", t1_ms, note=err_msg)
                        trace_steps.append({"hop": 1, "agent": "Strategy Parser", "status": "FAILED", "latency_ms": t1_ms, "details": err_msg})
                        save_full_pipeline_trace(req_id, sender, user_text, trace_steps, (time.perf_counter() - t_start) * 1000)
                        await ctx.send(sender, create_text_chat(f"⚠️ Strategy parsing issue: {err_msg}"))
                        return

                spec = parse_res.spec
                assumptions = parse_res.assumptions
                record_hop_event(req_id, sender, "Strategy Parser", "ok", t1_ms, note=f"{spec.get('strategy')} on {spec.get('ticker')}")
                trace_steps.append({
                    "hop": 1,
                    "agent": "Strategy Parser",
                    "status": "SUCCESS",
                    "latency_ms": t1_ms,
                    "details": f"{spec.get('strategy')} on {spec.get('ticker')}",
                })
                ctx.logger.info("Hop 1 complete [%s]: Parsed %s on %s in %.0fms", req_id, spec.get("strategy"), spec.get("ticker"), t1_ms)

            # --- HOP 2: MARKET DATA AGENT ---
            t2_start = time.perf_counter()
            data_req = DataRequest(
                request_id=req_id,
                ticker=spec["ticker"],
                start=spec.get("start"),
                end=spec.get("end"),
            )
            step2_timeout = budget.clamp_timeout(30.0)

            async def _call_data():
                res = await send_worker_request(
                    ctx, DATA_AGENT_ADDRESS, data_req, PriceData, timeout=step2_timeout
                )
                if res is None:
                    raise TransientError("Market Data agent did not respond within timeout.")
                return res

            price_res: Optional[PriceData] = None
            try:
                price_res = await _call_data()
            except TransientError:
                ctx.logger.warning("Data agent timed out on attempt 1 [%s]; retrying...", req_id)
                record_hop_event(req_id, sender, "Market Data Agent", "timeout", (time.perf_counter() - t2_start) * 1000, attempt=1)
                try:
                    price_res = await _call_data()
                except Exception as d_exc:
                    ctx.logger.error("Data agent failed on retry [%s]: %s", req_id, d_exc)

            t2_ms = (time.perf_counter() - t2_start) * 1000

            if not price_res or not price_res.ok:
                err = price_res.error if price_res else "Market Data Agent timed out"
                record_hop_event(req_id, sender, "Market Data Agent", "failed", t2_ms, note=err)
                trace_steps.append({"hop": 2, "agent": "Market Data Agent", "status": "FAILED", "latency_ms": t2_ms, "details": err})
                save_full_pipeline_trace(req_id, sender, user_text, trace_steps, (time.perf_counter() - t_start) * 1000)
                await ctx.send(sender, create_text_chat(messages.DATA_FAILED_TEMPLATE.format(ticker=spec['ticker'], reason=err)))
                return

            record_hop_event(req_id, sender, "Market Data Agent", "ok", t2_ms, note=f"{price_res.bars} bars ({price_res.source})")
            trace_steps.append({
                "hop": 2,
                "agent": "Market Data Agent",
                "status": "SUCCESS",
                "latency_ms": t2_ms,
                "details": f"{price_res.bars:,} bars loaded (source: {price_res.source})",
            })
            ctx.logger.info("Hop 2 complete [%s]: Received %d bars from %s in %.0fms", req_id, price_res.bars, price_res.source, t2_ms)

            # --- HOP 3: BACKTEST AGENT ---
            t3_start = time.perf_counter()
            bt_req = BacktestRequest(
                request_id=req_id,
                spec=spec,
                prices=price_res.dict(),
            )
            step3_timeout = budget.clamp_timeout(30.0)

            async def _call_backtest():
                res = await send_worker_request(
                    ctx, BACKTEST_AGENT_ADDRESS, bt_req, BacktestResponse, timeout=step3_timeout
                )
                if res is None:
                    raise TransientError("Backtest agent did not respond within timeout.")
                return res

            bt_res: Optional[BacktestResponse] = None
            try:
                bt_res = await _call_backtest()
            except TransientError:
                ctx.logger.warning("Backtest agent timed out on attempt 1 [%s]; retrying...", req_id)
                record_hop_event(req_id, sender, "Backtest Engine", "timeout", (time.perf_counter() - t3_start) * 1000, attempt=1)
                try:
                    bt_res = await _call_backtest()
                except Exception as b_exc:
                    ctx.logger.error("Backtest agent failed on retry [%s]: %s", req_id, b_exc)

            t3_ms = (time.perf_counter() - t3_start) * 1000

            if not bt_res or not bt_res.ok:
                err = bt_res.error if bt_res else "Backtest Agent was unreachable"
                record_hop_event(req_id, sender, "Backtest Engine", "failed", t3_ms, note=err)
                trace_steps.append({"hop": 3, "agent": "Backtest Engine", "status": "FAILED", "latency_ms": t3_ms, "details": err})
                save_full_pipeline_trace(req_id, sender, user_text, trace_steps, (time.perf_counter() - t_start) * 1000)
                await ctx.send(sender, create_text_chat(messages.BACKTEST_FAILED_TEMPLATE.format(reason=err)))
                return

            sharpe_val = bt_res.result.get("sharpe", 0.0)
            record_hop_event(req_id, sender, "Backtest Engine", "ok", t3_ms, note=f"Sharpe={sharpe_val:.2f}")
            trace_steps.append({
                "hop": 3,
                "agent": "Backtest Engine",
                "status": "SUCCESS",
                "latency_ms": t3_ms,
                "details": f"Sharpe: {sharpe_val:.2f} | Trades: {bt_res.result.get('trade_count', 0)}",
            })
            ctx.logger.info("Hop 3 complete [%s]: Sharpe=%.2f in %.0fms", req_id, sharpe_val, t3_ms)

            # --- HOP 4: SKEPTIC AGENT (Graceful Partial Result if Offline/Timeout) ---
            t4_start = time.perf_counter()
            audit_req = AuditRequest(
                request_id=req_id,
                spec=spec,
                prices=price_res.dict(),
            )
            step4_timeout = budget.clamp_timeout(30.0)

            async def _call_skeptic():
                res = await send_worker_request(
                    ctx, SKEPTIC_AGENT_ADDRESS, audit_req, AuditResponse, timeout=step4_timeout
                )
                if res is None:
                    raise TransientError("Skeptic agent did not respond within timeout.")
                return res

            audit_res: Optional[AuditResponse] = None
            try:
                audit_res = await _call_skeptic()
            except TransientError:
                ctx.logger.warning("Skeptic auditor timed out on attempt 1 [%s]; retrying...", req_id)
                record_hop_event(req_id, sender, "Skeptic Auditor", "timeout", (time.perf_counter() - t4_start) * 1000, attempt=1)
                try:
                    audit_res = await _call_skeptic()
                except Exception as a_exc:
                    ctx.logger.error("Skeptic auditor failed on retry [%s]: %s", req_id, a_exc)

            t4_ms = (time.perf_counter() - t4_start) * 1000

            if not audit_res or not audit_res.ok:
                ctx.logger.warning("Hop 4 Skeptic Auditor offline or timed out. Providing unvalidated partial result.")
                audit_report = {
                    "verdict": "UNVALIDATED",
                    "unvalidated": True,
                    "note": messages.SKEPTIC_DEGRADED_NOTE,
                    "tests": [],
                    "warnings": ["Adversarial quant audit could not be performed because the auditor was offline or timed out."],
                }
                record_hop_event(req_id, sender, "Skeptic Auditor", "degraded", t4_ms, note="Unvalidated partial result")
                trace_steps.append({"hop": 4, "agent": "Skeptic Auditor", "status": "DEGRADED", "latency_ms": t4_ms, "details": "Agent offline - unvalidated result issued"})
            else:
                audit_report = audit_res.report
                record_hop_event(req_id, sender, "Skeptic Auditor", "ok", t4_ms, note=f"Verdict={audit_report.get('verdict')}")
                ctx.logger.info("Hop 4 complete [%s]: Verdict=%s in %.0fms", req_id, audit_report.get("verdict"), t4_ms)
                trace_steps.append({"hop": 4, "agent": "Skeptic Auditor", "status": "SUCCESS", "latency_ms": t4_ms, "details": f"Verdict: {audit_report.get('verdict')} ({len(audit_report.get('tests', []))} tests)"})

            # --- FINAL: FORMAT & REPLY ---
            total_elapsed_s = (time.perf_counter() - t_start)
            timing_info = (
                total_elapsed_s,
                t1_ms / 1000.0,
                t2_ms / 1000.0,
                t3_ms / 1000.0,
                t4_ms / 1000.0,
            )

            final_report_text = format_final_reply(
                spec=spec,
                assumptions=assumptions,
                prices=price_res.dict(),
                backtest=bt_res.result,
                audit=audit_report,
                timing_info=timing_info,
            )
            session_store.update_partial_spec(sender, None)

            # Store in Card Result Cache and Bounded Session (Last 5 reports)
            card_cache.store(
                result_id=req_id,
                spec=spec,
                backtest=bt_res.result,
                audit=audit_report,
                full_text=final_report_text,
            )
            recent_reports = sess.setdefault("recent_reports", collections.OrderedDict())
            recent_reports[req_id] = {
                "spec": spec,
                "backtest": bt_res.result,
                "audit": audit_report,
                "full_text": final_report_text,
                "report_view": ReportView.from_results(spec, bt_res.result, audit_report),
                "created_at": time.time(),
            }
            while len(recent_reports) > 5:
                recent_reports.popitem(last=False)
            sess["last_result_id"] = req_id

            t5_ms = (time.perf_counter() - t_start) * 1000
            trace_steps.append({"hop": 5, "agent": "Orchestrator Delivery", "status": "SUCCESS", "latency_ms": t5_ms, "details": "Delivered audit report to ASI:One"})
            save_full_pipeline_trace(req_id, sender, user_text, trace_steps, t5_ms)

            # Deliver response (with Interactive Results Card if enabled and validated)
            if are_cards_enabled() and not audit_report.get("unvalidated"):
                try:
                    results_card = create_results_card(req_id, spec, bt_res.result, audit_report)
                    tot_ret = float(bt_res.result.get("total_return", 0.0)) * 100.0
                    sharpe = float(bt_res.result.get("sharpe", 0.0))
                    max_dd = abs(float(bt_res.result.get("max_drawdown", 0.0))) * 100.0
                    verdict = audit_report.get("verdict", "UNVALIDATED").upper()
                    summary_text = (
                        f"🛡️ TrustTest Verdict: [{verdict}] on {spec.get('ticker')}\n"
                        f"• Total Return: {tot_ret:+.1f}%\n"
                        f"• Sharpe Ratio: {sharpe:.2f}\n"
                        f"• Max Drawdown: -{max_dd:.1f}%\n\n"
                        "Tap 'See audit details' below or type 'full report' for the complete text report."
                    )
                    if example_label:
                        summary_text = f"*{example_label}*\n\n" + summary_text
                    await ctx.send(
                        sender,
                        ChatMessage(content=[TextContent(type="text", text=summary_text), results_card]),
                    )
                except Exception as card_err:
                    ctx.logger.warning("Failed to construct or deliver results card [%s]: %s. Sending text fallback.", req_id, card_err)
                    await ctx.send(sender, create_text_chat(final_report_text))
            else:
                await ctx.send(sender, create_text_chat(final_report_text))

            ctx.logger.info("Pipeline [%s] successfully delivered final audit report to %s in %.0fms", req_id, sender, t5_ms)

        finally:
            concurrency_guard.release(sender)

    except Exception as exc:
        err_id = f"err-{int(time.time() * 1000) % 1000000:06d}"
        ctx.logger.exception("Pipeline unhandled exception for %s (Ref: %s): %s", sender, err_id, exc)
        await ctx.send(
            sender,
            create_text_chat(messages.INTERNAL_ERROR_TEMPLATE.format(error_id=err_id)),
        )


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
