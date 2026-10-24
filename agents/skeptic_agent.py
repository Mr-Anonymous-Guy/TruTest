"""
agents/skeptic_agent.py – TrustTest Adversarial Skeptic Agent (Port 8004)

Runs the 4-part adversarial quant audit (Out-of-sample, Parameter perturbation,
Cost sensitivity, and Monte Carlo random baseline) to generate a final verdict.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(str(Path(__file__).resolve().parent.parent)))

from dotenv import load_dotenv
from uagents import Agent, Context

from agents.models import AuditRequest, AuditResponse, prices_to_df
from core.backtest import StrategySpec
from core.skeptic import audit

load_dotenv()

SKEPTIC_SEED = os.getenv("SKEPTIC_SEED")
if not SKEPTIC_SEED or SKEPTIC_SEED.strip() in ("", "REPLACE_WITH_SKEPTIC_SEED", "REPLACE_ME"):
    SKEPTIC_SEED = "trusttest_skeptic_agent_seed_fetchathon3_2026"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("trusttest_skeptic")

agent = Agent(
    name="trusttest_skeptic",
    seed=SKEPTIC_SEED,
    port=8004,
    mailbox=True,
    publish_agent_details=True,
)


def execute_audit(spec_dict: dict, prices_dict: dict) -> dict:
    """
    Direct functional execution helper for AuditRequest logic.
    Used by the message handler and by offline unit tests.
    """
    df = prices_to_df(prices_dict)
    if df is None or df.empty:
        raise ValueError("Price series is empty; cannot run quant audit.")
    spec = StrategySpec.from_dict(spec_dict)
    report = audit(df, spec)
    return report.to_dict()


@agent.on_message(model=AuditRequest)
async def handle_audit_request(ctx: Context, sender: str, msg: AuditRequest) -> None:
    """Handle AuditRequest and return AuditResponse with full adversarial findings."""
    ticker = msg.spec.get("ticker", "UNKNOWN")
    ctx.logger.info("Starting Skeptic Audit [%s] for %s from %s", msg.request_id, ticker, sender)
    t0 = time.perf_counter()
    try:
        report_dict = execute_audit(msg.spec, msg.prices)
        elapsed = time.perf_counter() - t0
        ctx.logger.info(
            "Audit [%s] completed in %.2fs. Verdict: %s",
            msg.request_id,
            elapsed,
            report_dict.get("verdict", "").upper(),
        )
        reply = AuditResponse(
            request_id=msg.request_id,
            ok=True,
            report=report_dict,
        )
        await ctx.send(sender, reply)
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        ctx.logger.error("Audit [%s] failed after %.2fs: %s", msg.request_id, elapsed, exc)
        reply = AuditResponse(
            request_id=msg.request_id,
            ok=False,
            report=None,
            error=str(exc),
        )
        await ctx.send(sender, reply)


if __name__ == "__main__":
    agent.run()
