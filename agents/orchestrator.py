"""
agents/orchestrator.py – TrustTest Orchestrator Agent (Port 8001)

ASI:One-facing entry-point implementing Agent Chat Protocol (ACP) 0.3.0.
Coordinates the multi-agent pipeline:
User -> Orchestrator -> Parser -> Data -> Backtest -> Skeptic -> Final Audit Report.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(str(Path(__file__).resolve().parent.parent)))

from dotenv import load_dotenv
from uagents import Agent, Context, Model, Protocol
from uagents.crypto import Identity
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agents.models import (
    AuditRequest,
    AuditResponse,
    BacktestRequest,
    BacktestResponse,
    DataRequest,
    ParseRequest,
    ParseResponse,
    PriceData,
    df_to_price_data,
)
from agents.pipeline import SessionManager, format_final_reply

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

# Session State Manager
session_mgr = SessionManager()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def create_text_chat(text: str) -> ChatMessage:
    """Helper to construct a ChatMessage containing TextContent."""
    return ChatMessage(content=[TextContent(type="text", text=text)])


def check_agent_health() -> str:
    """Check health and ping latency across all 5 agents (Phase 4)."""
    ports = [
        ("Orchestrator", 8001),
        ("Strategy Parser", 8005),
        ("Market Data Agent", 8002),
        ("Backtest Engine", 8003),
        ("Skeptic Auditor", 8004),
    ]
    lines = ["🛡️ TrustTest Multi-Agent Health Status:"]
    all_healthy = True
    for name, port in ports:
        t0 = time.perf_counter()
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.8):
                elapsed_ms = (time.perf_counter() - t0) * 1000
                lines.append(f"  • {name} (Port {port}): 🟢 HEALTHY ({elapsed_ms:.0f}ms)")
        except Exception:
            all_healthy = False
            lines.append(f"  • {name} (Port {port}): 🔴 OFFLINE")
    if all_healthy:
        lines.append("\nAll 5 agents are online, healthy, and operational.")
    else:
        lines.append("\n⚠️ Some agents are offline. Start offline agents with their respective commands.")
    return "\n".join(lines)


def save_trace(req_id: str, sender: str, user_text: str, steps: list, start_time: float) -> None:
    """Save execution trace for scripts/show_trace.py (Phase 4)."""
    try:
        logs_dir = Path(__file__).resolve().parent.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        total_ms = (time.perf_counter() - start_time) * 1000
        trace_data = {
            "request_id": req_id,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sender": sender,
            "user_text": user_text,
            "total_latency_ms": round(total_ms, 1),
            "steps": steps,
        }
        (logs_dir / "latest_trace.json").write_text(json.dumps(trace_data, indent=2), encoding="utf-8")
        with open(logs_dir / "traces.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_data) + "\n")
    except Exception as e:
        logger.warning("Failed to save trace: %s", e)


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
    timeout: int = 30,
) -> Optional[Model]:
    """
    Send typed request to a worker agent via send_and_receive.
    Falls back to direct execution if worker agent is not yet reachable over mailbox relay.
    """
    t0 = time.perf_counter()
    ctx.logger.info("Sending %s to %s (timeout: %ds)", type(message).__name__, destination, timeout)
    try:
        resp, status = await ctx.send_and_receive(destination, message, response_type=response_type, timeout=timeout)
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

    content_types = [type(item).__name__ for item in msg.content]
    ctx.logger.info("Message received from %s with content types: %s", sender, content_types)

    try:
        sess = session_mgr.get_or_create(sender)
        user_text = ""
        has_start_session = False
        has_end_session = False

        for item in msg.content:
            if isinstance(item, StartSessionContent):
                has_start_session = True
            elif isinstance(item, TextContent):
                user_text += item.text
            elif isinstance(item, EndSessionContent):
                has_end_session = True

        if has_end_session:
            session_mgr.clear(sender)
            ctx.logger.info("Cleaned up session state for %s", sender)
            return

        if has_start_session and not user_text:
            welcome = (
                "TrustTest is online. Tell me a trading strategy in plain English (e.g. 'Backtest 50/200 MA cross on RELIANCE.NS') "
                "and I'll run a lookahead-free backtest and an adversarial Skeptic audit. (Educational only, not investment advice.)"
            )
            await ctx.send(sender, create_text_chat(welcome))
            return

        if not user_text:
            return

        # Phase 4: status command
        if user_text.strip().lower() in ("status", "/status", "health"):
            health_report = check_agent_health()
            await ctx.send(sender, create_text_chat(health_report))
            return

        # Phase 4: Length guard (polite refusal if > 1500 chars)
        if len(user_text) > 1500:
            refusal = (
                "⚠️ Strategy description is too long (over 1,500 characters). "
                "Please provide a concise description of your trading strategy (e.g. 'Backtest 50/200 MA cross on RELIANCE.NS from 2018 to 2024')."
            )
            await ctx.send(sender, create_text_chat(refusal))
            return

        # Phase 4: Rapid double-send guard
        if session_mgr.is_busy(sender):
            busy_msg = "⏳ Still working on your previous request. Please wait a moment for the backtest and audit to complete."
            await ctx.send(sender, create_text_chat(busy_msg))
            return

        session_mgr.set_busy(sender, True)
        t_start = time.perf_counter()
        trace_steps = []
        req_id = f"tt-{int(datetime.datetime.now().timestamp() * 1000)}"
        ctx.logger.info("Processing pipeline request [%s] for %s: '%s'", req_id, sender, user_text)

        try:
            # --- HOP 1: PARSER AGENT ---
            t1_start = time.perf_counter()
            parse_req = ParseRequest(request_id=req_id, text=user_text, context=sess.get("partial_spec"))
            parse_res: Optional[ParseResponse] = await send_worker_request(
                ctx, PARSER_AGENT_ADDRESS, parse_req, ParseResponse, timeout=30
            )
            t1_ms = (time.perf_counter() - t1_start) * 1000

            if not parse_res:
                trace_steps.append({"hop": 1, "agent": "Strategy Parser", "status": "FAILED", "latency_ms": t1_ms, "details": "Parser Agent timed out"})
                save_trace(req_id, sender, user_text, trace_steps, t_start)
                await ctx.send(sender, create_text_chat("Sorry, the Strategy Parser Agent timed out. Please try again."))
                return

            if not parse_res.ok:
                if parse_res.question:
                    session_mgr.update_partial_spec(sender, parse_res.spec)
                    trace_steps.append({"hop": 1, "agent": "Strategy Parser", "status": "CLARIFICATION", "latency_ms": t1_ms, "details": parse_res.question})
                    save_trace(req_id, sender, user_text, trace_steps, t_start)
                    await ctx.send(sender, create_text_chat(parse_res.question))
                    return
                else:
                    err_msg = parse_res.error or "Could not parse strategy."
                    trace_steps.append({"hop": 1, "agent": "Strategy Parser", "status": "FAILED", "latency_ms": t1_ms, "details": err_msg})
                    save_trace(req_id, sender, user_text, trace_steps, t_start)
                    await ctx.send(sender, create_text_chat(f"Strategy parsing issue: {err_msg}"))
                    return

            spec = parse_res.spec
            assumptions = parse_res.assumptions
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
            price_res: Optional[PriceData] = await send_worker_request(
                ctx, DATA_AGENT_ADDRESS, data_req, PriceData, timeout=30
            )
            t2_ms = (time.perf_counter() - t2_start) * 1000

            if not price_res or not price_res.ok:
                err = price_res.error if price_res else "Market Data Agent was unreachable on port 8002"
                trace_steps.append({"hop": 2, "agent": "Market Data Agent", "status": "FAILED", "latency_ms": t2_ms, "details": err})
                save_trace(req_id, sender, user_text, trace_steps, t_start)
                await ctx.send(sender, create_text_chat(f"❌ Pipeline Step 2 (Market Data Agent) failed for {spec['ticker']}: {err}. Please ensure trusttest_data is running on port 8002."))
                return

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
            bt_res: Optional[BacktestResponse] = await send_worker_request(
                ctx, BACKTEST_AGENT_ADDRESS, bt_req, BacktestResponse, timeout=30
            )
            t3_ms = (time.perf_counter() - t3_start) * 1000

            if not bt_res or not bt_res.ok:
                err = bt_res.error if bt_res else "Backtest Agent was unreachable on port 8003"
                trace_steps.append({"hop": 3, "agent": "Backtest Engine", "status": "FAILED", "latency_ms": t3_ms, "details": err})
                save_trace(req_id, sender, user_text, trace_steps, t_start)
                await ctx.send(sender, create_text_chat(f"❌ Pipeline Step 3 (Backtest Agent) error: {err}. Please ensure trusttest_backtest is running on port 8003."))
                return

            sharpe_val = bt_res.result.get("sharpe", 0.0)
            trace_steps.append({
                "hop": 3,
                "agent": "Backtest Engine",
                "status": "SUCCESS",
                "latency_ms": t3_ms,
                "details": f"Sharpe: {sharpe_val:.2f} | Trades: {bt_res.result.get('trade_count', 0)}",
            })
            ctx.logger.info("Hop 3 complete [%s]: Sharpe=%.2f in %.0fms", req_id, sharpe_val, t3_ms)

            # --- HOP 4: SKEPTIC AGENT (with graceful degradation if offline, Test 8) ---
            t4_start = time.perf_counter()
            audit_req = AuditRequest(
                request_id=req_id,
                spec=spec,
                prices=price_res.dict(),
            )
            audit_res: Optional[AuditResponse] = await send_worker_request(
                ctx, SKEPTIC_AGENT_ADDRESS, audit_req, AuditResponse, timeout=30
            )
            t4_ms = (time.perf_counter() - t4_start) * 1000

            if not audit_res or not audit_res.ok:
                ctx.logger.warning("Hop 4 Skeptic Auditor offline or timed out. Providing unvalidated backtest report (Test 8).")
                audit_report = {
                    "verdict": "UNVALIDATED",
                    "note": "Skeptic adversarial auditor was unavailable. Results are unvalidated and no verdict can be issued.",
                    "tests": [],
                    "warnings": ["Adversarial audit was not performed because trusttest_skeptic was offline."],
                }
                trace_steps.append({"hop": 4, "agent": "Skeptic Auditor", "status": "DEGRADED", "latency_ms": t4_ms, "details": "Agent offline - unvalidated result issued"})
            else:
                audit_report = audit_res.report
                ctx.logger.info("Hop 4 complete [%s]: Verdict=%s in %.0fms", req_id, audit_report.get("verdict"), t4_ms)
                trace_steps.append({"hop": 4, "agent": "Skeptic Auditor", "status": "SUCCESS", "latency_ms": t4_ms, "details": f"Verdict: {audit_report.get('verdict')} ({len(audit_report.get('tests', []))} tests)"})

            # --- FINAL: FORMAT & REPLY ---
            final_report_text = format_final_reply(
                spec=spec,
                assumptions=assumptions,
                prices=price_res.dict(),
                backtest=bt_res.result,
                audit=audit_report,
            )
            session_mgr.update_partial_spec(sender, None)

            t5_ms = (time.perf_counter() - t_start) * 1000
            trace_steps.append({"hop": 5, "agent": "Orchestrator Delivery", "status": "SUCCESS", "latency_ms": t5_ms, "details": "Delivered audit report to ASI:One"})
            save_trace(req_id, sender, user_text, trace_steps, t_start)

            await ctx.send(sender, create_text_chat(final_report_text))
            ctx.logger.info("Pipeline [%s] successfully delivered final audit report to %s in %.0fms", req_id, sender, t5_ms)

        finally:
            session_mgr.set_busy(sender, False)

    except Exception as exc:
        ctx.logger.exception("Pipeline unhandled exception for %s: %s", sender, exc)
        await ctx.send(
            sender,
            create_text_chat("Sorry, an unexpected error occurred while processing your request. Please try again."),
        )


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
