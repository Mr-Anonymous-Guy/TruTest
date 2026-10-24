"""
TrustTest – Backtest Agent
===========================
Receives a StrategySpec + PriceData and runs the backtest engine
(core/backtest.py), returning a BacktestResult.
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
import pandas as pd
from uagents import Agent, Context, Model

from trusttest.core.backtest import run_backtest
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
# Agent initialization
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_backtest",
    seed=os.getenv("BACKTEST_SEED", "trusttest_backtest_seed_hackathon_fetchathon3"),
    port=8003,
    mailbox=True,
    publish_agent_details=True,
)


@agent.on_message(model=BacktestRequest)
async def handle_backtest(ctx: Context, sender: str, msg: BacktestRequest) -> None:
    """Run the backtest and return a BacktestResult."""
    ctx.logger.info(
        "BacktestRequest for %s / %s (session %s) from %s",
        msg.spec.ticker, msg.spec.strategy_type, msg.session_id, sender,
    )

    if not msg.price_data.bars:
        ctx.logger.error("Empty price data received in BacktestRequest")
        empty_result = BacktestResult(
            ticker=msg.spec.ticker,
            strategy_type=msg.spec.strategy_type,
            params=msg.spec.params,
            sharpe_ratio=0.0,
            max_drawdown_pct=0.0,
            cagr_pct=0.0,
            total_return_pct=0.0,
            trade_count=0,
            win_rate_pct=0.0,
            equity_curve=[1.0],
            daily_returns=[0.0],
            signal_dates=[],
        )
        await ctx.send(sender, empty_result)
        return

    # Convert PriceBar list to DataFrame
    records = [
        {
            "Date": pd.to_datetime(b.date),
            "Open": b.open,
            "High": b.high,
            "Low": b.low,
            "Close": b.close,
            "Volume": b.volume,
        }
        for b in msg.price_data.bars
    ]
    df = pd.DataFrame(records).set_index("Date").sort_index()

    # Slice to strategy date range if specified
    if msg.spec.start and msg.spec.end:
        df_sliced = df.loc[msg.spec.start:msg.spec.end]
        if not df_sliced.empty:
            df = df_sliced

    try:
        res = run_backtest(
            df=df,
            strategy_type=msg.spec.strategy_type,
            params=msg.spec.params,
            fees_bps=msg.spec.fees_bps,
            slippage_bps=msg.spec.slippage_bps,
        )

        result = BacktestResult(
            ticker=msg.spec.ticker,
            strategy_type=msg.spec.strategy_type,
            params=msg.spec.params,
            sharpe_ratio=res["sharpe_ratio"],
            max_drawdown_pct=res["max_drawdown_pct"],
            cagr_pct=res["cagr_pct"],
            total_return_pct=res["total_return_pct"],
            trade_count=res["trade_count"],
            win_rate_pct=res["win_rate_pct"],
            equity_curve=res["equity_curve"],
            daily_returns=res["daily_returns"],
            signal_dates=res["signal_dates"],
        )
        ctx.logger.info("Backtest complete for %s. Sharpe: %.2f", msg.spec.ticker, result.sharpe_ratio)
        await ctx.send(sender, result)
    except Exception as exc:
        ctx.logger.error("Failed to run backtest: %s", exc)
        fallback = BacktestResult(
            ticker=msg.spec.ticker,
            strategy_type=msg.spec.strategy_type,
            params=msg.spec.params,
            sharpe_ratio=0.0,
            max_drawdown_pct=0.0,
            cagr_pct=0.0,
            total_return_pct=0.0,
            trade_count=0,
            win_rate_pct=0.0,
            equity_curve=[1.0],
            daily_returns=[0.0],
            signal_dates=[],
        )
        await ctx.send(sender, fallback)


if __name__ == "__main__":
    agent.run()
