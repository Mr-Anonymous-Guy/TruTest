"""
agents/backtest_agent.py – TrustTest Backtest Engine Agent (Port 8003)
======================================================================
Executes lookahead-free quantitative backtests for StrategySpecs received from
the Orchestrator using historical price data.
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
from uagents import Agent, Context, Protocol

from agents.faults import check_and_log_faults_startup, is_fault_active
from agents.models import (
    BacktestRequest,
    BacktestResponse,
    HealthRequest,
    HealthResponse,
    prices_to_df,
)
from core.backtest import StrategySpec, run_backtest

load_dotenv()

BACKTEST_SEED = os.getenv("BACKTEST_SEED")
if not BACKTEST_SEED or BACKTEST_SEED.strip() in ("", "REPLACE_WITH_BACKTEST_SEED", "REPLACE_ME"):
    BACKTEST_SEED = "trusttest_backtest_agent_seed_fetchathon3_2026"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("trusttest_backtest")

agent = Agent(
    name="trusttest_backtest",
    seed=BACKTEST_SEED,
    port=8003,
    mailbox=True,
    publish_agent_details=True,
)

# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------
health_proto = Protocol(name="HealthCheckProtocol", version="1.0")
backtest_proto = Protocol(name="BacktestEngineProtocol", version="1.0")

_start_time = time.time()
check_and_log_faults_startup("trusttest_backtest")


def execute_backtest(spec_dict: dict, prices_dict: dict) -> dict:
    """
    Direct functional execution helper for BacktestRequest logic.
    Used by handler and directly by offline unit tests.
    """
    if is_fault_active("backtest_fail"):
        raise RuntimeError("[FAULT INJECTION ACTIVE] Simulated Backtest Engine computation error.")

    if not isinstance(spec_dict, dict) or not spec_dict:
        raise ValueError("Invalid StrategySpec: must be a non-empty dictionary.")

    df = prices_to_df(prices_dict)
    if df is None or df.empty:
        raise ValueError("Price series is empty; cannot run backtest.")

    spec = StrategySpec.from_dict(spec_dict)
    result = run_backtest(df, spec)
    return result.to_dict()


@health_proto.on_message(model=HealthRequest, replies={HealthResponse})
async def handle_health_check(ctx: Context, sender: str, msg: HealthRequest) -> None:
    """Respond to health ping with uptime and status."""
    uptime = round(time.time() - _start_time, 1)
    await ctx.send(
        sender,
        HealthResponse(
            request_id=msg.request_id,
            agent_name="Backtest Engine",
            ok=True,
            version="1.0.0",
            uptime_s=uptime,
        ),
    )


@backtest_proto.on_message(model=BacktestRequest, replies={BacktestResponse})
async def handle_backtest_request(ctx: Context, sender: str, msg: BacktestRequest) -> None:
    """Handle BacktestRequest and return BacktestResponse without raising."""
    t0 = time.perf_counter()
    ticker = msg.spec.get("ticker", "UNKNOWN") if isinstance(msg.spec, dict) else "UNKNOWN"
    ctx.logger.info("Received BacktestRequest [%s] from %s for %s", msg.request_id, sender, ticker)

    # 1. Payload validation
    if not isinstance(msg.spec, dict) or "strategy" not in msg.spec:
        ctx.logger.warning("BacktestRequest [%s] rejected: invalid spec payload", msg.request_id)
        await ctx.send(
            sender,
            BacktestResponse(
                request_id=msg.request_id,
                ok=False,
                result=None,
                error="Invalid BacktestRequest: spec must be a dictionary with a 'strategy' field.",
            ),
        )
        return

    if not isinstance(msg.prices, dict) or "dates" not in msg.prices:
        ctx.logger.warning("BacktestRequest [%s] rejected: invalid prices payload", msg.request_id)
        await ctx.send(
            sender,
            BacktestResponse(
                request_id=msg.request_id,
                ok=False,
                result=None,
                error="Invalid BacktestRequest: prices must contain 'dates' and 'closes'.",
            ),
        )
        return

    # 2. Execution
    try:
        res_dict = execute_backtest(msg.spec, msg.prices)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        ctx.logger.info(
            "Backtest [%s] completed in %.0fms: Sharpe=%.2f, Return=%.1f%%, Trades=%d",
            msg.request_id,
            elapsed_ms,
            res_dict.get("sharpe", 0.0),
            res_dict.get("total_return", 0.0) * 100,
            res_dict.get("trade_count", 0),
        )
        reply = BacktestResponse(
            request_id=msg.request_id,
            ok=True,
            result=res_dict,
        )
        await ctx.send(sender, reply)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        ctx.logger.error("Failed BacktestRequest [%s] after %.0fms: %s", msg.request_id, elapsed_ms, exc)
        reply = BacktestResponse(
            request_id=msg.request_id,
            ok=False,
            result=None,
            error=str(exc),
        )
        await ctx.send(sender, reply)


# ---------------------------------------------------------------------------
# Include protocols in agent
# ---------------------------------------------------------------------------
agent.include(health_proto, publish_manifest=True)
agent.include(backtest_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
