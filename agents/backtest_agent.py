"""
agents/backtest_agent.py – TrustTest Backtest Engine Agent (Port 8003)

Executes lookahead-free quantitative backtests for StrategySpecs received from
the Orchestrator using historical price data.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(str(Path(__file__).resolve().parent.parent)))

from dotenv import load_dotenv
from uagents import Agent, Context

from agents.models import BacktestRequest, BacktestResponse, prices_to_df
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


def execute_backtest(spec_dict: dict, prices_dict: dict) -> dict:
    """
    Direct functional execution helper for BacktestRequest logic.
    Used by handler and directly by offline unit tests.
    """
    df = prices_to_df(prices_dict)
    if df is None or df.empty:
        raise ValueError("Price series is empty; cannot run backtest.")
    spec = StrategySpec.from_dict(spec_dict)
    result = run_backtest(df, spec)
    return result.to_dict()


@agent.on_message(model=BacktestRequest)
async def handle_backtest_request(ctx: Context, sender: str, msg: BacktestRequest) -> None:
    """Handle BacktestRequest and return BacktestResponse with performance metrics."""
    ctx.logger.info("Received BacktestRequest [%s] from %s for %s", msg.request_id, sender, msg.spec.get("ticker"))
    try:
        res_dict = execute_backtest(msg.spec, msg.prices)
        ctx.logger.info(
            "Backtest [%s] completed: Sharpe=%.2f, Return=%.1f%%, Trades=%d",
            msg.request_id,
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
        ctx.logger.error("Failed BacktestRequest [%s]: %s", msg.request_id, exc)
        reply = BacktestResponse(
            request_id=msg.request_id,
            ok=False,
            result=None,
            error=str(exc),
        )
        await ctx.send(sender, reply)


if __name__ == "__main__":
    agent.run()
