"""
TrustTest – Orchestrator Agent (stub)
======================================
The ASI:One-facing entry-point agent.

Responsibilities (Phase 1+):
  - Implement Agent Chat Protocol (ACP) 0.3.0
  - Hold per-session state (session_id → StrategySpec)
  - Drive the pipeline: Parser → Data → Backtest → Skeptic
  - Return formatted result cards to the user via ChatMessage

TODO Phase 1: replace stubs with real ACP handlers and pipeline calls.
"""

import logging
import os

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent initialisation (seed from .env, mailbox for Agentverse connectivity)
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_orchestrator",
    seed=os.getenv("ORCHESTRATOR_SEED", "REPLACE_ME"),
    mailbox=True,
)

# ---------------------------------------------------------------------------
# Agent Chat Protocol handler
# ---------------------------------------------------------------------------
chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(model=ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    """Receive a chat message from ASI:One and start the pipeline."""
    # TODO Phase 1: extract text, parse session, dispatch to Parser Agent
    ctx.logger.info("Received ChatMessage from %s", sender)

    # Acknowledge receipt immediately
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=msg.timestamp, acknowledged=True),
    )

    # TODO Phase 1: run pipeline and send result
    # For now just echo so the agent is visible in ASI:One
    reply = ChatMessage(
        timestamp=msg.timestamp,
        msg_id=ctx.session_id,  # type: ignore[attr-defined]
        content=[
            TextContent(
                type="text",
                text=(
                    "🚧 TrustTest is being set up. "
                    "Phase 1 will wire the full pipeline. Stay tuned!"
                ),
            )
        ],
    )
    await ctx.send(sender, reply)


@chat_proto.on_message(model=StartSessionContent)
async def handle_start(ctx: Context, sender: str, msg: StartSessionContent) -> None:
    """Greet user when a new ASI:One session opens."""
    ctx.logger.info("New session from %s", sender)
    # TODO Phase 1: initialise session state


@chat_proto.on_message(model=EndSessionContent)
async def handle_end(ctx: Context, sender: str, msg: EndSessionContent) -> None:
    """Clean up session state when the user closes the chat."""
    ctx.logger.info("Session ended from %s", sender)
    # TODO Phase 1: clear session state


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
