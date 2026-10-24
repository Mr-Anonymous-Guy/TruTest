"""
TrustTest – Backtest Agent (stub)
===================================
Receives a StrategySpec + PriceData and runs the backtest engine
(core/backtest.py), returning a BacktestResult.

TODO Phase 3:
  - Implement handle_backtest() using core.backtest.run_backtest()
  - Register with Agentverse and update .env with the agent address
"""

import logging
import os

from dotenv import load_dotenv
from uagents import Agent, Context, Model

from trusttest.core.models import BacktestResult, PriceData, StrategySpec

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request message (sent by Orchestrator)
# ---------------------------------------------------------------------------

class BacktestRequest(Model):
    """Orchestrator sends spec + data together for efficiency."""
    session_id: str
    spec: StrategySpec
    price_data: PriceData


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_backtest",
    seed=os.getenv("BACKTEST_SEED", "REPLACE_ME"),
    mailbox=True,
)


@agent.on_message(model=BacktestRequest)
async def handle_backtest(ctx: Context, sender: str, msg: BacktestRequest) -> None:
    """
    Run the backtest and return a BacktestResult.
    TODO Phase 3: implement using core.backtest.run_backtest().
    """
    ctx.logger.info(
        "BacktestRequest for %s / %s (session %s) from %s",
        msg.spec.ticker, msg.spec.strategy_type, msg.session_id, sender,
    )
    # TODO Phase 3: deserialise PriceData → pd.DataFrame, call run_backtest(), send result
    ctx.logger.warning("BacktestAgent not yet implemented – Phase 3 work")


if __name__ == "__main__":
    agent.run()
