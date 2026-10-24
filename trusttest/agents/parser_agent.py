"""
TrustTest – Strategy Parser Agent (stub)
=========================================
Calls the ASI:One LLM (OpenAI-compatible) to convert plain-English
strategy descriptions into a structured StrategySpec JSON.

TODO Phase 3:
  - Implement parse_strategy() using the OpenAI client pointed at ASI:One
  - Validate required fields; return a list of missing fields if incomplete
  - Register with Agentverse and update .env with the agent address
"""

import logging
import os

from dotenv import load_dotenv
from uagents import Agent, Context, Model

from trusttest.core.models import StrategySpec

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Message types for inter-agent communication
# ---------------------------------------------------------------------------

class ParseRequest(Model):
    """Sent by Orchestrator to Parser Agent."""
    session_id: str
    user_text: str


class ParseResponse(Model):
    """Sent back to Orchestrator."""
    session_id: str
    success: bool
    spec: StrategySpec | None = None
    missing_fields: list[str] = []
    error: str = ""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_parser",
    seed=os.getenv("PARSER_SEED", "REPLACE_ME"),
    mailbox=True,
)

ORCHESTRATOR_ADDRESS = os.getenv("ORCHESTRATOR_ADDRESS", "")


@agent.on_message(model=ParseRequest)
async def handle_parse(ctx: Context, sender: str, msg: ParseRequest) -> None:
    """
    Receive a plain-English strategy description and return a StrategySpec.
    TODO Phase 3: call ASI:One LLM with a structured extraction prompt.
    """
    ctx.logger.info("ParseRequest received from %s (session %s)", sender, msg.session_id)
    # TODO Phase 3: implement LLM call
    await ctx.send(
        sender,
        ParseResponse(
            session_id=msg.session_id,
            success=False,
            error="Parser not yet implemented – Phase 3 work",
        ),
    )


if __name__ == "__main__":
    agent.run()
