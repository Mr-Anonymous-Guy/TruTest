"""
TrustTest – Market Data Agent
==============================
Fetches OHLCV price data via core/data_loader.py and returns it
as a PriceData message. Reports whether data came from live yfinance
or a cached CSV.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from uagents import Agent, Context

from trusttest.core.data_loader import load_prices
from trusttest.core.models import DataRequest, PriceBar, PriceData

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent initialization
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_data",
    seed=os.getenv("DATA_SEED", "trusttest_data_seed_hackathon_fetchathon3"),
    port=8002,
    mailbox=True,
    publish_agent_details=True,
)


@agent.on_message(model=DataRequest)
async def handle_data_request(ctx: Context, sender: str, msg: DataRequest) -> None:
    """Load price data for the requested ticker and date range."""
    ctx.logger.info(
        "DataRequest for %s [%s -> %s] from %s",
        msg.ticker, msg.start, msg.end, sender,
    )
    try:
        df, source = load_prices(msg.ticker, msg.start, msg.end)
        bars = [
            PriceBar(
                date=str(idx.date()) if hasattr(idx, "date") else str(idx),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
            for idx, row in df.iterrows()
        ]
        resp = PriceData(
            ticker=msg.ticker,
            bars=bars,
            source=source,  # "live" | "cache"
            row_count=len(bars),
            start_actual=bars[0].date if bars else msg.start,
            end_actual=bars[-1].date if bars else msg.end,
        )
        ctx.logger.info("Sending PriceData (%s bars from %s) to %s", len(bars), source, sender)
        await ctx.send(sender, resp)
    except Exception as exc:
        ctx.logger.error("Error loading prices for %s: %s", msg.ticker, exc)
        empty_resp = PriceData(
            ticker=msg.ticker,
            bars=[],
            source="cache",
            row_count=0,
            start_actual=msg.start,
            end_actual=msg.end,
        )
        await ctx.send(sender, empty_resp)


if __name__ == "__main__":
    agent.run()
