"""
TrustTest – Orchestrator Agent (Phase 1)
========================================
ASI:One-facing entry-point agent implementing Agent Chat Protocol (ACP) 0.3.0.
"""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any, Dict

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

# ---------------------------------------------------------------------------
# Session State (stub for Phase 3 pipeline extension)
# ---------------------------------------------------------------------------
# TODO (Phase 3): store active StrategySpec, intermediate backtest results, and audit progress per session.
sessions: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def create_text_chat(text: str) -> ChatMessage:
    """Helper to construct a ChatMessage containing TextContent."""
    return ChatMessage(
        content=[TextContent(type="text", text=text)]
    )


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

# ---------------------------------------------------------------------------
# Protocol & Handlers (AgentChatProtocol 0.3.0)
# ---------------------------------------------------------------------------
chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    """Handle and log chat acknowledgements."""
    ctx.logger.info("ChatAcknowledgement received from %s for msg_id: %s", sender, msg.acknowledged_msg_id)


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    """Receive and process incoming chat messages from ASI:One or clients."""
    # ALWAYS acknowledge receipt first
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

    content_types = [type(item).__name__ for item in msg.content]
    ctx.logger.info("Message received from %s with content types: %s", sender, content_types)

    try:
        # Initialize or retrieve session state
        if sender not in sessions:
            sessions[sender] = {"created_at": datetime.datetime.now(), "history": []}

        user_text = ""
        has_start_session = False
        has_end_session = False
        has_unknown = False

        for item in msg.content:
            if isinstance(item, StartSessionContent):
                has_start_session = True
                ctx.logger.info("StartSessionContent detected from %s", sender)
            elif isinstance(item, TextContent):
                user_text += item.text
                ctx.logger.info("TextContent received from %s: %s", sender, item.text)
            elif isinstance(item, EndSessionContent):
                has_end_session = True
                ctx.logger.info("EndSessionContent detected from %s", sender)
            else:
                has_unknown = True
                ctx.logger.warning("Unknown content type from %s: %s", sender, type(item).__name__)

        # Handle session termination
        if has_end_session:
            sessions.pop(sender, None)
            ctx.logger.info("Cleaned up session state for %s", sender)
            return

        # Handle new session greeting if no text prompt was attached
        if has_start_session and not user_text:
            welcome_msg = (
                "TrustTest is online. Soon I'll backtest your trading strategy and then try to break the result with an adversarial audit. "
                "(Educational only, not investment advice.)"
            )
            reply = create_text_chat(welcome_msg)
            await ctx.send(sender, reply)
            ctx.logger.info("Sent welcome reply to %s: %s", sender, welcome_msg)
            return

        # Handle text message: reply with placeholder echoing the user's strategy
        if user_text:
            sessions[sender]["history"].append(user_text)
            reply_text = (
                f"TrustTest is online. Soon I'll backtest your trading strategy and then try to break the result with an adversarial audit. "
                f"(Educational only, not investment advice.)\n\n"
                f"Received strategy description:\n\"{user_text}\""
            )
            reply = create_text_chat(reply_text)
            await ctx.send(sender, reply)
            ctx.logger.info("Sent reply to %s: %s", sender, reply_text)
        elif has_unknown:
            fallback_text = (
                "Received unrecognized message content. Please describe your trading strategy in plain English."
            )
            reply = create_text_chat(fallback_text)
            await ctx.send(sender, reply)
            ctx.logger.info("Sent unknown content fallback to %s", sender)

    except Exception as exc:
        ctx.logger.exception("Exception occurred while handling message from %s: %s", sender, exc)
        err_msg = (
            "Sorry, an unexpected error occurred while processing your request. "
            "Please try again."
        )
        await ctx.send(sender, create_text_chat(err_msg))


agent.include(chat_proto, publish_manifest=True)

# ---------------------------------------------------------------------------
# Main Execution Guard
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    agent.run()
