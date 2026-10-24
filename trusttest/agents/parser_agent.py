"""
TrustTest – Strategy Parser Agent
=================================
Converts plain-English strategy descriptions into a structured StrategySpec JSON.
Uses ASI:One LLM API (OpenAI-compatible) when available, with a resilient rule-based
fallback for zero-downtime offline execution and hackathon demos.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repo root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
from openai import OpenAI
from uagents import Agent, Context, Model

from trusttest.core.models import StrategySpec

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------

class ParseRequest(Model):
    """Sent by Orchestrator to Parser Agent."""
    session_id: str
    user_text: str


class ParseResponse(Model):
    """Sent back to Orchestrator."""
    session_id: str
    success: bool
    spec: Optional[StrategySpec] = None
    missing_fields: List[str] = []
    error: str = ""


# ---------------------------------------------------------------------------
# Heuristic / Rule-based Parser (Fallback & High-Reliability)
# ---------------------------------------------------------------------------

_TICKER_MAP = {
    "reliance": "RELIANCE.NS",
    "reliance.ns": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "tcs.ns": "TCS.NS",
    "infy": "INFY.NS",
    "infosys": "INFY.NS",
    "infy.ns": "INFY.NS",
    "hdfc": "HDFCBANK.NS",
    "hdfcbank": "HDFCBANK.NS",
    "hdfcbank.ns": "HDFCBANK.NS",
    "aapl": "AAPL",
    "apple": "AAPL",
    "nifty": "^NSEI",
    "nsei": "^NSEI",
    "^nsei": "^NSEI",
}


def _heuristic_parse(text: str) -> StrategySpec:
    """Parse text using regex and heuristics."""
    lowered = text.lower()

    # 1. Detect Ticker
    detected_ticker = "RELIANCE.NS"
    for name, sym in _TICKER_MAP.items():
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            detected_ticker = sym
            break

    # 2. Strategy type and params
    strat_type = "sma_crossover"
    params: Dict[str, Any] = {"short_window": 50, "long_window": 200}

    if "rsi" in lowered:
        strat_type = "rsi_threshold"
        period = 14
        oversold = 30.0
        overbought = 70.0

        period_match = re.search(r"(\d+)[- ]?day\s+rsi", lowered) or re.search(r"rsi\s*\(?(\d+)\)?", lowered)
        if period_match:
            period = int(period_match.group(1))

        # Look for thresholds e.g. "below 30", "above 70"
        thresh_matches = re.findall(r"(?:below|under|<)\s*(\d+)", lowered)
        if thresh_matches:
            oversold = float(thresh_matches[0])
        thresh_matches_up = re.findall(r"(?:above|over|>)\s*(\d+)", lowered)
        if thresh_matches_up:
            overbought = float(thresh_matches_up[0])

        params = {"rsi_period": period, "oversold": oversold, "overbought": overbought}

    elif "momentum" in lowered:
        strat_type = "momentum"
        lookback = 20
        lookback_match = re.search(r"(\d+)[- ]?day\s+momentum", lowered) or re.search(r"momentum\s*\(?(\d+)\)?", lowered)
        if lookback_match:
            lookback = int(lookback_match.group(1))
        params = {"lookback": lookback, "threshold": 0.0}

    elif "mean reversion" in lowered or "bollinger" in lowered:
        strat_type = "mean_reversion"
        window = 20
        window_match = re.search(r"(\d+)[- ]?day", lowered)
        if window_match:
            window = int(window_match.group(1))
        params = {"window": window, "num_std": 2.0}

    else:
        # Default SMA Crossover
        strat_type = "sma_crossover"
        # Search for two numbers like "50 and 200" or "50/200"
        nums = [int(n) for n in re.findall(r"\b\d+\b", lowered) if int(n) in range(5, 501)]
        if len(nums) >= 2:
            short_w = min(nums[0], nums[1])
            long_w = max(nums[0], nums[1])
            params = {"short_window": short_w, "long_window": long_w}
        else:
            params = {"short_window": 50, "long_window": 200}

    # 3. Detect Date Range
    start_date = "2018-01-01"
    end_date = "2024-01-01"

    year_matches = re.findall(r"\b(20\d\d)\b", lowered)
    if len(year_matches) >= 2:
        start_date = f"{year_matches[0]}-01-01"
        end_date = f"{year_matches[1]}-01-01"
    elif len(year_matches) == 1:
        start_date = f"{year_matches[0]}-01-01"

    return StrategySpec(
        ticker=detected_ticker,
        strategy_type=strat_type,
        params=params,
        start=start_date,
        end=end_date,
        fees_bps=10.0,
        slippage_bps=5.0,
        description=text,
    )


# ---------------------------------------------------------------------------
# LLM Parser
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """You are a financial trading strategy extractor for TrustTest.
Your task is to parse a plain-English trading strategy into a structured JSON StrategySpec.

Output MUST be a single valid JSON object with EXACTLY these fields:
{
    "ticker": "RELIANCE.NS",  // standard symbol with .NS for Indian stocks (e.g. RELIANCE.NS, TCS.NS, AAPL)
    "strategy_type": "sma_crossover",  // one of: "sma_crossover", "rsi_threshold", "momentum", "mean_reversion"
    "params": { ... },  // strategy parameters
    "start": "2018-01-01",  // ISO YYYY-MM-DD
    "end": "2024-01-01",    // ISO YYYY-MM-DD
    "fees_bps": 10.0,
    "slippage_bps": 5.0
}

If details are omitted, default to:
ticker: "RELIANCE.NS", start: "2018-01-01", end: "2024-01-01", fees_bps: 10.0, slippage_bps: 5.0.
Output only the JSON. Do not include markdown codeblocks or explanation."""


def parse_strategy(text: str) -> StrategySpec:
    """Parse strategy using ASI:One LLM API with heuristic fallback."""
    api_key = os.getenv("ASI1_API_KEY", "")

    if api_key and not api_key.startswith("YOUR_") and not api_key.startswith("REPLACE"):
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.asi1.ai/v1",
                timeout=15.0,
            )
            response = client.chat.completions.create(
                model="asi1",
                messages=[
                    {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
            )
            content = response.choices[0].message.content or ""
            # Strip backticks if present
            cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
            data = json.loads(cleaned)
            return StrategySpec(
                ticker=data.get("ticker", "RELIANCE.NS"),
                strategy_type=data.get("strategy_type", "sma_crossover"),
                params=data.get("params", {"short_window": 50, "long_window": 200}),
                start=data.get("start", "2018-01-01"),
                end=data.get("end", "2024-01-01"),
                fees_bps=float(data.get("fees_bps", 10.0)),
                slippage_bps=float(data.get("slippage_bps", 5.0)),
                description=text,
            )
        except Exception as exc:
            logger.warning("ASI:One LLM parsing failed or timed out: %s. Using heuristic parser.", exc)

    return _heuristic_parse(text)


# ---------------------------------------------------------------------------
# Agent initialization
# ---------------------------------------------------------------------------
agent = Agent(
    name="trusttest_parser",
    seed=os.getenv("PARSER_SEED", "trusttest_parser_seed_hackathon_fetchathon3"),
    port=8005,
    mailbox=True,
    publish_agent_details=True,
)


@agent.on_message(model=ParseRequest)
async def handle_parse(ctx: Context, sender: str, msg: ParseRequest) -> None:
    """Receive a plain-English strategy description and return a StrategySpec."""
    ctx.logger.info("ParseRequest received from %s (session %s): %s", sender, msg.session_id, msg.user_text)
    try:
        spec = parse_strategy(msg.user_text)
        ctx.logger.info("Parsed spec: %s on %s", spec.strategy_type, spec.ticker)
        await ctx.send(
            sender,
            ParseResponse(
                session_id=msg.session_id,
                success=True,
                spec=spec,
                missing_fields=[],
            ),
        )
    except Exception as exc:
        ctx.logger.error("Failed to parse strategy: %s", exc)
        await ctx.send(
            sender,
            ParseResponse(
                session_id=msg.session_id,
                success=False,
                spec=None,
                error=str(exc),
            ),
        )


if __name__ == "__main__":
    agent.run()
