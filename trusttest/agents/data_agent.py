"""
TrustTest – Market Data Agent (stub)
======================================
Fetches OHLCV price data via core/data_loader.py and returns it
as a PriceData message. Reports whether data came from live yfinance
or a cached CSV.

TODO Phase 3:
  - Implement handle_data_request() to call load_prices() and serialise
  - Register with Agentverse and update .env with the agent address
"""

import logging
import os

from dotenv import load_dotenv
from uagents import Agent, Context

from trusttest.core.data_loader import load_prices
from trusttest.core.models import DataRequest, PriceBar, PriceData

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_data",
    seed=os.getenv("DATA_SEED", "REPLACE_ME"),
    mailbox=True,
)


@agent.on_message(model=DataRequest)
async def handle_data_request(ctx: Context, sender: str, msg: DataRequest) -> None:
    """
    Load price data for the requested ticker and date range.
    TODO Phase 3: implement fully; for now stub responds with an error.
    """
    ctx.logger.info(
        "DataRequest for %s [%s → %s] from %s",
        msg.ticker, msg.start, msg.end, sender,
    )
    # TODO Phase 3: call load_prices(), serialise to PriceData, send back
    # Example (do not run yet):
    #
    # df, source = load_prices(msg.ticker, msg.start, msg.end)
    # bars = [
    #     PriceBar(
    #         date=str(idx.date()),
    #         open=row.Open, high=row.High, low=row.Low,
    #         close=row.Close, volume=row.Volume,
    #     )
    #     for idx, row in df.iterrows()
    # ]
    # await ctx.send(sender, PriceData(
    #     ticker=msg.ticker, bars=bars, source=source,
    #     row_count=len(bars),
    #     start_actual=bars[0].date, end_actual=bars[-1].date,
    # ))
    ctx.logger.warning("DataAgent not yet implemented – Phase 3 work")


if __name__ == "__main__":
    agent.run()
