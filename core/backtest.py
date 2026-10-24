"""
core/backtest.py – Pure-Python Backtest Engine
==============================================
No uagents, no network calls, plain pandas & numpy.
Strict 1-bar signal shift to prevent look-ahead bias.
Realistic fee and slippage modeling.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Data Classes (Plain Python, JSON-safe)
# ---------------------------------------------------------------------------

@dataclass
class StrategySpec:
    ticker: str
    strategy: str
    params: Dict[str, Any]
    fee_pct: float = 0.1         # 0.1% transaction fee per side
    slippage_pct: float = 0.05    # 0.05% slippage per side
    start: Optional[str] = None
    end: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": str(self.ticker),
            "strategy": str(self.strategy),
            "params": {k: (int(v) if isinstance(v, (int, np.integer)) else float(v) if isinstance(v, (float, np.floating)) else v) for k, v in self.params.items()},
            "fee_pct": float(self.fee_pct),
            "slippage_pct": float(self.slippage_pct),
            "start": str(self.start) if self.start else None,
            "end": str(self.end) if self.end else None,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> StrategySpec:
        return cls(
            ticker=d["ticker"],
            strategy=d["strategy"],
            params=d.get("params", {}),
            fee_pct=float(d.get("fee_pct", 0.1)),
            slippage_pct=float(d.get("slippage_pct", 0.05)),
            start=d.get("start"),
            end=d.get("end"),
        )


@dataclass
class BacktestResult:
    spec: StrategySpec
    total_return: float
    cagr: float
    sharpe: float
    max_drawdown: float
    trade_count: int
    exposure: float
    win_rate: float
    equity_curve: List[float] = field(default_factory=list)
    positions: List[int] = field(default_factory=list)
    returns: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "total_return": float(round(self.total_return, 4)),
            "cagr": float(round(self.cagr, 4)),
            "sharpe": float(round(self.sharpe, 4)),
            "max_drawdown": float(round(self.max_drawdown, 4)),
            "trade_count": int(self.trade_count),
            "exposure": float(round(self.exposure, 4)),
            "win_rate": float(round(self.win_rate, 4)),
            "equity_curve": [float(round(x, 4)) for x in self.equity_curve],
            "positions": [int(x) for x in self.positions],
            "returns": [float(round(x, 6)) for x in self.returns],
            "metadata": {k: (v if isinstance(v, (str, int, float, bool)) else str(v)) for k, v in self.metadata.items()},
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> BacktestResult:
        return cls(
            spec=StrategySpec.from_dict(d["spec"]),
            total_return=float(d["total_return"]),
            cagr=float(d["cagr"]),
            sharpe=float(d["sharpe"]),
            max_drawdown=float(d["max_drawdown"]),
            trade_count=int(d["trade_count"]),
            exposure=float(d["exposure"]),
            win_rate=float(d["win_rate"]),
            equity_curve=[float(x) for x in d.get("equity_curve", [])],
            positions=[int(x) for x in d.get("positions", [])],
            returns=[float(x) for x in d.get("returns", [])],
            metadata=d.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def ma_crossover(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.Series:
    """
    Long when fast SMA > slow SMA, flat otherwise.
    Validates fast < slow.
    """
    fast = int(fast)
    slow = int(slow)
    if fast >= slow:
        raise ValueError(f"fast window ({fast}) must be strictly less than slow window ({slow}).")

    close = df["close"] if "close" in df.columns else df["Close"]
    sma_fast = close.rolling(window=fast, min_periods=fast).mean()
    sma_slow = close.rolling(window=slow, min_periods=slow).mean()

    raw_signal = (sma_fast > sma_slow).astype(int)
    # Warm-up periods have position 0
    raw_signal = raw_signal.fillna(0).astype(int)
    return raw_signal


def rsi_meanrev(
    df: pd.DataFrame,
    period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
) -> pd.Series:
    """
    RSI mean reversion with Wilder's exponential smoothing.
    Enter long when RSI < oversold, exit when RSI > overbought,
    hold position between the two levels.
    """
    period = int(period)
    oversold = float(oversold)
    overbought = float(overbought)

    close = df["close"] if "close" in df.columns else df["Close"]
    delta = close.diff()

    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder smoothing (exponential moving average with alpha = 1 / period)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.fillna(50.0)

    # Position state machine
    positions = []
    in_pos = 0
    for r in rsi:
        if r < oversold:
            in_pos = 1
        elif r > overbought:
            in_pos = 0
        positions.append(in_pos)

    return pd.Series(positions, index=df.index, dtype=int)


STRATEGIES: Dict[str, Callable[..., pd.Series]] = {
    "ma_crossover": ma_crossover,
    "rsi_meanrev": rsi_meanrev,
}


# ---------------------------------------------------------------------------
# Backtest Engine Core
# ---------------------------------------------------------------------------

def run_backtest_positions(
    close_prices: np.ndarray,
    positions: np.ndarray,
    fee_pct: float = 0.1,
    slippage_pct: float = 0.05,
) -> Tuple[float, float, float]:
    """
    Fast vectorized backtest from close prices and shifted positions.
    Returns: (sharpe, total_return, cagr)
    """
    n = len(close_prices)
    if n < 2 or len(positions) != n:
        return 0.0, 0.0, 0.0

    # Asset returns
    asset_returns = np.zeros(n, dtype=float)
    asset_returns[1:] = (close_prices[1:] - close_prices[:-1]) / close_prices[:-1]

    # Position changes (trades)
    pos_diff = np.zeros(n, dtype=float)
    pos_diff[0] = float(positions[0])
    pos_diff[1:] = np.abs(positions[1:] - positions[:-1])

    # Costs per trade side: fee_pct and slippage_pct are percentages (0.1% -> 0.001)
    cost_rate = (fee_pct + slippage_pct) / 100.0
    cost_drag = pos_diff * cost_rate

    strat_returns = (positions * asset_returns) - cost_drag

    # Equity
    equity = np.cumprod(1.0 + strat_returns)
    final_eq = equity[-1]
    total_ret = final_eq - 1.0

    # CAGR
    years = n / 252.0
    cagr = (final_eq ** (1.0 / years) - 1.0) if final_eq > 0 and years > 0 else -1.0

    # Annualised Sharpe (risk-free = 0)
    std_ret = np.std(strat_returns[1:])
    if std_ret > 1e-9:
        sharpe = (np.mean(strat_returns[1:]) / std_ret) * np.sqrt(252.0)
    else:
        sharpe = 0.0

    return float(sharpe), float(total_ret), float(cagr)


def run_backtest(df: pd.DataFrame, spec: StrategySpec) -> BacktestResult:
    """
    Run backtest with:
    1. Lookahead-free execution: position[t] = raw_signal[t-1], position[0] = 0.
    2. Fee and slippage friction deducted per side.
    3. Full performance metrics.
    """
    if spec.strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy '{spec.strategy}'. Supported: {list(STRATEGIES.keys())}")

    # Slice date range if specified
    work_df = df
    if spec.start or spec.end:
        start_date = spec.start or str(df.index[0].date())
        end_date = spec.end or str(df.index[-1].date())
        work_df = df.loc[start_date:end_date]
        if work_df.empty:
            raise ValueError(f"Date slice [{spec.start} : {spec.end}] returned empty DataFrame.")

    close_series = work_df["close"] if "close" in work_df.columns else work_df["Close"]
    n_bars = len(work_df)

    # 1. Compute raw signal on bar t's close
    strat_fn = STRATEGIES[spec.strategy]
    raw_signals = strat_fn(work_df, **spec.params)

    # 2. Shift signal by 1 bar: traded on bar t+1. position[0] = 0.
    shifted_signals = raw_signals.shift(1).fillna(0).astype(int)

    positions = shifted_signals.values
    close_vals = close_series.values

    # Asset daily return
    asset_returns = np.zeros(n_bars, dtype=float)
    if n_bars > 1:
        asset_returns[1:] = (close_vals[1:] - close_vals[:-1]) / close_vals[:-1]

    # Costs: on change in position charge (fee_pct + slippage_pct) of notional per side
    pos_diff = np.zeros(n_bars, dtype=float)
    pos_diff[0] = float(positions[0])
    pos_diff[1:] = np.abs(positions[1:] - positions[:-1])

    cost_pct = (spec.fee_pct + spec.slippage_pct) / 100.0
    cost_drag = pos_diff * cost_pct

    strat_returns = (positions * asset_returns) - cost_drag
    equity_curve = np.cumprod(1.0 + strat_returns)

    # Compute metrics
    final_equity = float(equity_curve[-1]) if n_bars > 0 else 1.0
    total_return = (final_equity - 1.0)

    years = max(n_bars / 252.0, 1.0 / 252.0)
    cagr = (final_equity ** (1.0 / years) - 1.0) if final_equity > 0 else -1.0

    # Max Drawdown
    cummax = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - cummax) / cummax
    max_drawdown = abs(float(np.min(drawdowns)))

    # Trade count & win rate
    entries = np.where((positions[1:] == 1) & (positions[:-1] == 0))[0] + 1
    if positions[0] == 1:
        entries = np.insert(entries, 0, 0)
    trade_count = len(entries)

    # Win rate calculation
    trades_pnl: List[float] = []
    in_t = False
    entry_p = 0.0
    for i in range(n_bars):
        pos = positions[i]
        prev_pos = positions[i - 1] if i > 0 else 0
        curr_p = close_vals[i]

        if pos == 1 and prev_pos == 0:
            in_t = True
            entry_p = curr_p
        elif pos == 0 and prev_pos == 1 and in_t:
            in_t = False
            # Trade return after two-sided friction
            pnl = (curr_p / entry_p - 1.0) - (2.0 * cost_pct)
            trades_pnl.append(pnl)

    if in_t and entry_p > 0:
        pnl = (close_vals[-1] / entry_p - 1.0) - cost_pct
        trades_pnl.append(pnl)

    if trades_pnl:
        wins = sum(1 for p in trades_pnl if p > 0)
        win_rate = (wins / len(trades_pnl))
    else:
        win_rate = 0.0

    # Exposure
    exposure = float(np.mean(positions > 0)) if n_bars > 0 else 0.0

    # Sharpe ratio (annualized, risk-free = 0)
    if trade_count == 0 or n_bars < 2:
        sharpe = 0.0
    else:
        std_ret = float(np.std(strat_returns[1:]))
        if std_ret > 1e-9:
            sharpe = (float(np.mean(strat_returns[1:])) / std_ret) * np.sqrt(252.0)
        else:
            sharpe = 0.0

    if math.isnan(sharpe) or math.isinf(sharpe):
        sharpe = 0.0

    metadata = {
        "source": "cache",
        "ticker": spec.ticker,
        "date_range": f"{work_df.index[0].date()} to {work_df.index[-1].date()}",
        "bar_count": n_bars,
        "price_basis": "adjusted prices (auto_adjust=True)",
        "parameters": spec.params,
        "fees": f"{spec.fee_pct}% fee + {spec.slippage_pct}% slippage per side",
    }

    return BacktestResult(
        spec=spec,
        total_return=float(total_return),
        cagr=float(cagr),
        sharpe=float(sharpe),
        max_drawdown=float(max_drawdown),
        trade_count=int(trade_count),
        exposure=float(exposure),
        win_rate=float(win_rate),
        equity_curve=[float(x) for x in equity_curve.tolist()],
        positions=[int(x) for x in positions.tolist()],
        returns=[float(x) for x in strat_returns.tolist()],
        metadata=metadata,
    )
