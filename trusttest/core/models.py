"""
TrustTest – Shared Pydantic/uagents models.

All messages exchanged between agents are defined here.
Keep fields simple and JSON-serializable so they work as
uagents.Model subclasses and as plain dicts for unit tests.
"""

from typing import Any, Dict, List, Literal, Optional

from uagents import Model


# ---------------------------------------------------------------------------
# Strategy specification (produced by Parser Agent)
# ---------------------------------------------------------------------------

class StrategySpec(Model):
    """Structured representation of a trading strategy extracted from plain English."""

    # e.g. "RELIANCE.NS", "TCS.NS", "AAPL"
    ticker: str

    # e.g. "sma_crossover", "rsi_threshold", "momentum", "mean_reversion"
    strategy_type: str

    # Free-form params: {"short_window": 50, "long_window": 200, "rsi_period": 14, ...}
    params: Dict[str, Any]

    # ISO date strings  e.g. "2018-01-01"
    start: str
    end: str

    # Trading cost in basis points (e.g. 10 = 0.10 %)
    fees_bps: float = 10.0

    # Slippage in basis points
    slippage_bps: float = 5.0

    # Optional: original plain-English description for audit trail
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Data layer messages
# ---------------------------------------------------------------------------

class DataRequest(Model):
    """Sent by Orchestrator/Backtest Agent to Data Agent."""

    ticker: str
    start: str
    end: str


class PriceBar(Model):
    """Single OHLCV bar – date as ISO string for JSON safety."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceData(Model):
    """Response from Data Agent."""

    ticker: str
    bars: List[PriceBar]
    source: Literal["live", "cache"]  # tells orchestrator which path was used
    row_count: int
    start_actual: str
    end_actual: str


# ---------------------------------------------------------------------------
# Backtest result
# ---------------------------------------------------------------------------

class BacktestResult(Model):
    """Output of Backtest Agent – metrics over the FULL date range."""

    ticker: str
    strategy_type: str
    params: Dict[str, Any]

    # Key performance metrics
    sharpe_ratio: float
    max_drawdown_pct: float
    cagr_pct: float
    total_return_pct: float
    trade_count: int
    win_rate_pct: float

    # For downstream use by Skeptic
    equity_curve: List[float]          # daily portfolio value (normalised to 1.0)
    daily_returns: List[float]         # daily log-returns
    signal_dates: List[str]            # dates on which signals fired


# ---------------------------------------------------------------------------
# Skeptic / audit report
# ---------------------------------------------------------------------------

class SkepticTest(Model):
    """Result of a single adversarial test run by the Skeptic."""

    name: str                         # e.g. "out_of_sample", "cost_2x", "param_perturb_short_p10"
    sharpe_ratio: float
    cagr_pct: float
    max_drawdown_pct: float
    passed: bool                      # True if the strategy still looks viable
    note: str                         # Human-readable explanation


class AuditReport(Model):
    """Full audit produced by Skeptic Agent."""

    ticker: str
    strategy_type: str

    # Individual test results
    tests: List[SkepticTest]

    # Monte Carlo benchmark stats
    mc_p95_sharpe: float              # 95th-percentile Sharpe from random baselines
    mc_beat_rate_pct: float           # % of MC runs the strategy beats

    # Overall verdict
    verdict: Literal["Trustworthy", "Fragile", "Likely Overfit"]
    verdict_rationale: str

    # Convenience for formatting
    tests_passed: int
    tests_total: int
