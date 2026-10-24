"""
TrustTest – Skeptic Agent (stub)
==================================
Runs the adversarial audit suite (core/skeptic.py) against the
BacktestResult and returns an AuditReport with a verdict.

TODO Phase 3:
  - Implement handle_audit() using core.skeptic.run_audit()
  - Register with Agentverse and update .env with the agent address
"""

import logging
import os

from dotenv import load_dotenv
from uagents import Agent, Context, Model

from trusttest.core.models import AuditReport, BacktestResult, PriceData

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request message
# ---------------------------------------------------------------------------

class AuditRequest(Model):
    """Orchestrator sends backtest result + raw price data for OOS analysis."""
    session_id: str
    result: BacktestResult
    price_data: PriceData   # full history (not just backtest window)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_skeptic",
    seed=os.getenv("SKEPTIC_SEED", "REPLACE_ME"),
    mailbox=True,
)


@agent.on_message(model=AuditRequest)
async def handle_audit(ctx: Context, sender: str, msg: AuditRequest) -> None:
    """
    Run the adversarial audit and return an AuditReport.
    TODO Phase 3: implement using core.skeptic.run_audit().
    """
    ctx.logger.info(
        "AuditRequest for %s (session %s) from %s",
        msg.result.ticker, msg.session_id, sender,
    )
    # TODO Phase 3: deserialise PriceData → df, call run_audit(), send AuditReport
    ctx.logger.warning("SkepticAgent not yet implemented – Phase 3 work")


if __name__ == "__main__":
    agent.run()
