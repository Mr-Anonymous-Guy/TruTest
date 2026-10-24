"""
agents/data_agent.py – TrustTest Market Data Agent (Port 8002)

Serves price history requests for the TrustTest pipeline. Fetches live
NSE/global market data via yfinance, falling back to local cached CSVs.
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

from agents.data_source import fetch_prices
from agents.models import DataRequest, PriceData, df_to_price_data

load_dotenv()

DATA_SEED = os.getenv("DATA_SEED")
if not DATA_SEED or DATA_SEED.strip() in ("", "REPLACE_WITH_DATA_SEED", "REPLACE_ME"):
    # Fallback to deterministic default if not set in .env
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


@agent.on_message(model=DataRequest)
async def handle_data_request(ctx: Context, sender: str, msg: DataRequest) -> None:
    """Handle incoming DataRequest and reply with PriceData."""
    ctx.logger.info("Received DataRequest [%s] for %s from %s", msg.request_id, msg.ticker, sender)
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
        ctx.logger.info(
            "Replying [%s] with %d bars from '%s' (%s to %s)",
            msg.request_id,
            reply.bars,
            source,
            reply.start,
            reply.end,
        )
        await ctx.send(sender, reply)
    except Exception as exc:
        ctx.logger.error("Failed to fulfill DataRequest [%s]: %s", msg.request_id, exc)
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
