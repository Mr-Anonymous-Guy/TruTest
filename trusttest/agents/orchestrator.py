"""
TrustTest – Orchestrator Agent
==============================
The ASI:One-facing entry-point agent.
Implements Agent Chat Protocol (ACP) 0.3.0 and orchestrates the
TrustTest pipeline: Parser -> Data -> Backtest -> Skeptic Auditor.
"""

from __future__ import annotations

import datetime
import logging
import os
import uuid

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

from trusttest.core.pipeline import run_pipeline

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent initialization
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_orchestrator",
    seed=os.getenv("ORCHESTRATOR_SEED", "trusttest_orchestrator_seed_hackathon_fetchathon3"),
)

# ---------------------------------------------------------------------------
# Agent Chat Protocol handler
# ---------------------------------------------------------------------------
chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(model=ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage) -> None:
    """Receive a chat message from ASI:One and run the adversarial audit pipeline."""
    ctx.logger.info("Received ChatMessage from %s", sender)

    # 1. Acknowledge receipt immediately
    try:
        ack = ChatAcknowledgement(
            acknowledged_msg_id=msg.msg_id or uuid.uuid4(),
            timestamp=datetime.datetime.now(),
        )
        await ctx.send(sender, ack)
    except Exception as exc:
        ctx.logger.warning("Could not send ChatAcknowledgement: %s", exc)

    # 2. Extract plain-text prompt from msg.content
    user_text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            user_text += item.text
        elif hasattr(item, "text"):
            user_text += getattr(item, "text", "")

    user_text = user_text.strip()
    ctx.logger.info("User prompt: %s", user_text)

    # 3. Handle greetings or empty text
    if not user_text or user_text.lower() in ("hi", "hello", "hey", "help"):
        greeting = (
            "👋 **Welcome to TrustTest!**\n\n"
            "I am your adversarial trading strategy auditor for Fetch-A-Thon 3.0.\n\n"
            "Describe any trading strategy in plain English and I will:\n"
            "1. 📈 Run a fee-adjusted, lookahead-free backtest.\n"
            "2. 🧐 Subject it to the **Skeptic** adversarial stress tests (out-of-sample, cost sensitivity, parameter perturbation, and 1,000 Monte Carlo baselines).\n"
            "3. 🛡️ Return an audit verdict: **Trustworthy**, **Fragile**, or **Likely Overfit**.\n\n"
            "**Example prompts to try:**\n"
            "- *\"Buy Reliance when the 50 SMA crosses above the 200 SMA from 2018 to 2024\"*\n"
            "- *\"RSI below 30 buy, exit above 70 on TCS.NS\"*\n"
            "- *\"20-day momentum on AAPL\"*"
        )
        reply = ChatMessage(
            content=[TextContent(text=greeting)],
            msg_id=uuid.uuid4(),
            timestamp=datetime.datetime.now(),
        )
        await ctx.send(sender, reply)
        return

    # 4. Run full pipeline
    result_card = run_pipeline(user_text)

    # 5. Send result card back to user
    reply = ChatMessage(
        content=[TextContent(text=result_card)],
        msg_id=uuid.uuid4(),
        timestamp=datetime.datetime.now(),
    )
    await ctx.send(sender, reply)
    ctx.logger.info("Sent audit result card to %s", sender)


@chat_proto.on_message(model=StartSessionContent)
async def handle_start(ctx: Context, sender: str, msg: StartSessionContent) -> None:
    """Greet user when a new ASI:One session opens."""
    ctx.logger.info("New session started from %s", sender)
    welcome_msg = (
        "🛡️ **TrustTest Session Started**\n\n"
        "Send your trading strategy description to begin the backtest and adversarial audit."
    )
    reply = ChatMessage(
        content=[TextContent(text=welcome_msg)],
        msg_id=uuid.uuid4(),
        timestamp=datetime.datetime.now(),
    )
    await ctx.send(sender, reply)


@chat_proto.on_message(model=EndSessionContent)
async def handle_end(ctx: Context, sender: str, msg: EndSessionContent) -> None:
    """Clean up session state when the user closes the chat."""
    ctx.logger.info("Session ended from %s", sender)


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
