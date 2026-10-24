"""
agents/data_agent.py – TrustTest Market Data Agent (Port 8002)
=============================================================
Serves price history requests for the TrustTest pipeline. Fetches live
NSE/global market data via yfinance, falling back to local cached CSVs.
Hardened with input validation, health check handler, and fault injection.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(str(Path(__file__).resolve().parent.parent)))

from dotenv import load_dotenv
from uagents import Agent, Context

from agents.data_source import fetch_prices
from agents.faults import check_and_log_faults_startup, is_fault_active
from agents.models import DataRequest, HealthRequest, HealthResponse, PriceData, df_to_price_data

load_dotenv()

DATA_SEED = os.getenv("DATA_SEED")
if not DATA_SEED or DATA_SEED.strip() in ("", "REPLACE_WITH_DATA_SEED", "REPLACE_ME"):
    DATA_SEED = "trusttest_data_agent_seed_fetchathon3_2026"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("trusttest_data")

agent = Agent(
    name="trusttest_data",
    seed=DATA_SEED,
    port=8002,
    mailbox=True,
    publish_agent_details=True,
)

_start_time = time.time()
check_and_log_faults_startup("trusttest_data")


@agent.on_message(model=HealthRequest)
async def handle_health_check(ctx: Context, sender: str, msg: HealthRequest) -> None:
    """Respond to health ping with uptime and status."""
    uptime = round(time.time() - _start_time, 1)
    await ctx.send(
        sender,
        HealthResponse(
            request_id=msg.request_id,
            agent_name="Market Data Agent",
            ok=True,
            version="1.0.0",
            uptime_s=uptime,
        ),
    )


@agent.on_message(model=DataRequest)
async def handle_data_request(ctx: Context, sender: str, msg: DataRequest) -> None:
    """Handle incoming DataRequest and reply with PriceData without raising."""
    t0 = time.perf_counter()
    ctx.logger.info("Received DataRequest [%s] for ticker '%s' from %s", msg.request_id, msg.ticker, sender)

    # 1. Payload validation
    if not msg.ticker or not isinstance(msg.ticker, str) or len(msg.ticker.strip()) == 0:
        ctx.logger.warning("DataRequest [%s] rejected: empty ticker symbol", msg.request_id)
        await ctx.send(
            sender,
            PriceData(
                request_id=msg.request_id,
                ok=False,
                ticker="",
                source="error",
                start="",
                end="",
                bars=0,
                dates=[],
                closes=[],
                error="Invalid ticker: ticker symbol cannot be empty.",
            ),
        )
        return

    if len(msg.ticker) > 30:
        ctx.logger.warning("DataRequest [%s] rejected: oversize ticker '%s'", msg.request_id, msg.ticker[:30])
        await ctx.send(
            sender,
            PriceData(
                request_id=msg.request_id,
                ok=False,
                ticker=msg.ticker[:30],
                source="error",
                start="",
                end="",
                bars=0,
                dates=[],
                closes=[],
                error="Invalid ticker: ticker symbol exceeds maximum length (30 characters).",
            ),
        )
        return

    # 2. Fault injection check
    if is_fault_active("data_fail"):
        ctx.logger.warning("🚨 [FAULT INJECTION ACTIVE] Simulating complete Market Data failure for %s", msg.ticker)
        await ctx.send(
            sender,
            PriceData(
                request_id=msg.request_id,
                ok=False,
                ticker=msg.ticker,
                source="error",
                start="",
                end="",
                bars=0,
                dates=[],
                closes=[],
                error="[FAULT INJECTION ACTIVE] Simulated Market Data Agent failure.",
            ),
        )
        return

    # 3. Execution
    try:
        df, source, note = fetch_prices(ticker=msg.ticker, start=msg.start, end=msg.end)
        reply = df_to_price_data(
            request_id=msg.request_id,
            df=df,
            ticker=msg.ticker.strip().upper(),
            source=source,
            note=note,
            ok=True,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        ctx.logger.info(
            "Replying [%s] with %d bars from '%s' (%s to %s) in %.0fms",
            msg.request_id,
            reply.bars,
            source,
            reply.start,
            reply.end,
            elapsed_ms,
        )
        await ctx.send(sender, reply)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        ctx.logger.error("Failed to fulfill DataRequest [%s] after %.0fms: %s", msg.request_id, elapsed_ms, exc)
        err_reply = PriceData(
            request_id=msg.request_id,
            ok=False,
            ticker=msg.ticker,
            source="error",
            start="",
            end="",
            bars=0,
            dates=[],
            closes=[],
            note=None,
            error=str(exc),
        )
        await ctx.send(sender, err_reply)


if __name__ == "__main__":
    agent.run()
