# Core Quantitative Engine & Adversarial Skeptic

Pure-Python, offline-capable quantitative backtesting and adversarial audit engine for TrustTest. Has zero dependencies on `uagents` or Fetch.ai libraries, enabling fast, isolated testing and clean agent integration in Phase 3.

---

## 1. Data Layer (`core/data.py`)

### `load_cached(ticker: str, cache_dir: str = "data/cache") -> pd.DataFrame`
- **Inputs**: `ticker` (e.g., `"RELIANCE.NS"`, `"TCS.NS"`, `"NSEI"`), optional `cache_dir`.
- **Output**: `pd.DataFrame` with a monotonic `DatetimeIndex` (no duplicates) and float `close` column (auto-adjusted for splits/dividends).
- **Errors**: Raises `DataQualityError` if file is missing, listing all available cached tickers.

### `validate_prices(df: pd.DataFrame, min_bars: int = 500, max_missing_pct: float = 3.0) -> pd.DataFrame`
- **Inputs**: Price DataFrame, minimum required bars (default: 500), max allowed missing business days (default: 3.0%).
- **Output**: Cleaned DataFrame with forward-filled small gaps.
- **Errors**: Raises `DataQualityError` if fewer than `min_bars` or if missing data exceeds `max_missing_pct`.

---

## 2. Backtest Engine (`core/backtest.py`)

### `StrategySpec` (Dataclass)
- Specification matching Parser Agent JSON schema:
  - `ticker: str` (e.g. `"RELIANCE.NS"`)
  - `strategy: str` (`"ma_crossover"` or `"rsi_meanrev"`)
  - `params: dict` (e.g. `{"fast": 50, "slow": 200}` or `{"period": 14, "oversold": 30, "overbought": 70}`)
  - `fee_pct: float` (percentage, e.g. `0.1` for 0.10%)
  - `slippage_pct: float` (percentage, e.g. `0.05` for 0.05%)
  - `start: Optional[str]`, `end: Optional[str]`
- Includes `to_dict()` and `from_dict()` (JSON-safe, handles nulls and numpy types).

### `run_backtest(df: pd.DataFrame, spec: StrategySpec) -> BacktestResult`
- **Engine Rules**:
  - **No look-ahead**: `position[t] = raw_signal[t-1]`. First bar position is 0.
  - **Frictions**: Each position change pays `(fee_pct + slippage_pct)` on entry and exit.
  - **Metrics**: `total_return`, `cagr`, `sharpe` (annualized with 252, risk-free 0.0), `max_drawdown`, `trade_count`, `exposure`, `win_rate`.
  - Edge cases: Zero trades or zero variance returns Sharpe 0.0 without `NaN`.

---

## 3. Adversarial Skeptic Auditor (`core/skeptic.py`)

### `audit(df: pd.DataFrame, spec: StrategySpec) -> AuditReport`
- **Inputs**: Clean price DataFrame and a `StrategySpec`.
- **Attacks Executed**:
  1. `out_of_sample`: 70/30 time-split; verifies OOS Sharpe retains $\ge 50\%$ of in-sample Sharpe.
  2. `parameter_perturbation`: Nudges parameters by $\pm 10\%$ and $\pm 20\%$; checks if $\ge 70\%$ of neighbours retain $\ge 50\%$ Sharpe.
  3. `cost_sensitivity`: 2x fees and slippage; checks if CAGR remains $> 0$ and Sharpe retains $\ge 50\%$.
  4. `random_baseline`: 500 Monte Carlo random entries with identical trades and holding periods; checks if strategy exceeds 95th percentile.
- **Output**: `AuditReport` dataclass with:
  - `verdict`: `"Trustworthy"`, `"Fragile"`, or `"Likely Overfit"`.
  - `tests`: List of attack test results with numbers and one-line plain-English explanations.
  - `base_metrics`: Strategy performance metrics dictionary.
  - `warnings`: Warning strings (e.g. low trade counts $< 8$).
  - `summary_text()`: Formatted plain-text summary for ACP chat messages.
  - `to_dict()`: JSON-serializable representation for inter-agent communication.
