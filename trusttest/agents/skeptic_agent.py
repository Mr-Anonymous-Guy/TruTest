"""
TrustTest – Skeptic Agent
==========================
Runs the adversarial audit suite (core/skeptic.py) against the
BacktestResult and returns an AuditReport with a verdict.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
import pandas as pd
from uagents import Agent, Context, Model

from trusttest.core.models import AuditReport, BacktestResult, PriceData, SkepticTest
from trusttest.core.skeptic import run_audit

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request message
# ---------------------------------------------------------------------------

class AuditRequest(Model):
    """Orchestrator sends backtest result + raw price data for adversarial audit."""
    session_id: str
    result: BacktestResult
    price_data: PriceData


# ---------------------------------------------------------------------------
# Agent initialization
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_skeptic",
    seed=os.getenv("SKEPTIC_SEED", "trusttest_skeptic_seed_hackathon_fetchathon3"),
)


@agent.on_message(model=AuditRequest)
async def handle_audit(ctx: Context, sender: str, msg: AuditRequest) -> None:
    """Run the adversarial audit and return an AuditReport."""
    ctx.logger.info(
        "AuditRequest for %s (session %s) from %s",
        msg.result.ticker, msg.session_id, sender,
    )

    if not msg.price_data.bars:
        ctx.logger.error("Empty price data in AuditRequest")
        empty_report = AuditReport(
            ticker=msg.result.ticker,
            strategy_type=msg.result.strategy_type,
            tests=[],
            mc_p95_sharpe=0.0,
            mc_beat_rate_pct=0.0,
            verdict="Likely Overfit",
            verdict_rationale="No price data available for audit.",
            tests_passed=0,
            tests_total=0,
        )
        await ctx.send(sender, empty_report)
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

    try:
        audit_dict = run_audit(
            df=df,
            strategy_type=msg.result.strategy_type,
            params=msg.result.params,
        )

        tests = [
            SkepticTest(
                name=t["name"],
                sharpe_ratio=t["sharpe_ratio"],
                cagr_pct=t["cagr_pct"],
                max_drawdown_pct=t["max_drawdown_pct"],
                passed=t["passed"],
                note=t["note"],
            )
            for t in audit_dict["tests"]
        ]

        report = AuditReport(
            ticker=msg.result.ticker,
            strategy_type=msg.result.strategy_type,
            tests=tests,
            mc_p95_sharpe=audit_dict["mc_p95_sharpe"],
            mc_beat_rate_pct=audit_dict["mc_beat_rate_pct"],
            verdict=audit_dict["verdict"],
            verdict_rationale=audit_dict["verdict_rationale"],
            tests_passed=audit_dict["tests_passed"],
            tests_total=audit_dict["tests_total"],
        )
        ctx.logger.info("Audit complete for %s. Verdict: %s", msg.result.ticker, report.verdict)
        await ctx.send(sender, report)
    except Exception as exc:
        ctx.logger.error("Failed to run skeptic audit: %s", exc)
        fallback = AuditReport(
            ticker=msg.result.ticker,
            strategy_type=msg.result.strategy_type,
            tests=[],
            mc_p95_sharpe=0.0,
            mc_beat_rate_pct=0.0,
            verdict="Likely Overfit",
            verdict_rationale=f"Audit failed due to error: {exc}",
            tests_passed=0,
            tests_total=0,
        )
        await ctx.send(sender, fallback)


if __name__ == "__main__":
    agent.run()
