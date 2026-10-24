# 🧪 TrustTest – Testing & Verification Guide

This guide provides step-by-step instructions for running all unit tests, integration tests, and live multi-agent demonstrations for **TrustTest** (Fetch-A-Thon 3.0).

---

## 📋 Prerequisites

Ensure your virtual environment is activated and dependencies are installed:

```powershell
# Windows PowerShell
.venv\Scripts\activate

# Verify installed packages
python -c "import uagents, pandas, numpy, yfinance; print('All core dependencies loaded successfully!')"
```

---

## 1. Automated Test Suite (pytest)

Run the full automated test suite containing **35 unit and integration tests**:

```powershell
.venv\Scripts\python -m pytest trusttest/tests/ -v
```

### Expected Result
All 35 tests must pass:
```
============================= 35 passed in ~6.5s =============================
```

### Testing Specific Components

- **Backtest Engine Tests:**
  ```powershell
  .venv\Scripts\python -m pytest trusttest/tests/test_backtest.py -v
  ```
  *Verifies:* Lookahead-bias prevention (1-bar signal shift), transaction fee drag, zero-trades handling, and SMA positive Sharpe on trending series.

- **Adversarial Skeptic Tests:**
  ```powershell
  .venv\Scripts\python -m pytest trusttest/tests/test_skeptic.py -v
  ```
  *Verifies:* 70/30 Out-of-Sample split, parameter perturbations (+/-10%, +/-20%), Monte Carlo beat-rate ranges, and verdict logic (`Trustworthy`, `Fragile`, `Likely Overfit`).

- **Market Data Loader Tests (Offline Cache):**
  ```powershell
  .venv\Scripts\python -m pytest trusttest/tests/test_data_loader.py -v
  ```
  *Verifies:* Cache integrity for NSE (`RELIANCE.NS`, `TCS.NS`) and US equities (`AAPL`), row counts, and date slicing.

- **End-to-End Pipeline Integration Tests:**
  ```powershell
  .venv\Scripts\python -m pytest trusttest/tests/test_pipeline.py -v
  ```
  *Verifies:* Plain English parsing, strategy extraction, end-to-end backtest + Skeptic audit execution, and markdown result card generation.

---

## 2. Standalone CLI Demo Runner

Test the end-to-end pipeline directly from the command line without needing external network sessions:

### Test Case A: Default SMA Crossover Strategy (Reliance)
```powershell
.venv\Scripts\python trusttest/scripts/demo.py
```
*Expected Output:*
- Parses: `SMA Crossover` on `RELIANCE.NS`
- Loads: Market data for `RELIANCE.NS`
- Displays: Performance Metrics table (Sharpe, CAGR, Max Drawdown, Win Rate)
- Displays: Skeptic Robustness Stress Tests (OOS, Cost 2x, Param Perturbations, Monte Carlo)
- Verdict: `❌ Likely Overfit` or `⚠️ Fragile`

### Test Case B: RSI Strategy with Date Range (TCS)
```powershell
.venv\Scripts\python trusttest/scripts/demo.py "RSI below 30 buy, exit above 70 on TCS.NS from 2019 to 2023"
```
*Expected Output:*
- Parses: `RSI Threshold` (`period=14, oversold=30, overbought=70`) on `TCS.NS`
- Evaluates: Out-of-sample data and parameter stability
- Verdict: `✅ Trustworthy`

### Test Case C: Momentum Strategy (AAPL)
```powershell
.venv\Scripts\python trusttest/scripts/demo.py "20-day momentum on AAPL"
```

---

## 3. Multi-Agent Bureau Runner

Launch all 5 uAgents together in a single local Bureau to verify multi-agent initialization and address binding:

```powershell
.venv\Scripts\python trusttest/scripts/run_all.py
```

### Expected Output
```
======================================================================
  🛡️  TrustTest Multi-Agent Bureau (Fetch-A-Thon 3.0)
======================================================================
Initializing 5 uAgents:
  • Orchestrator: agent1qwlf7ep22r407eu89xa8rh4qa7h95vsltfxqmk6egfxa3t7h620cksg67ak
  • Parser:       agent1qddf7rvzcdw466gm2ssx2q7jvwvaw6jfrnjtleq38339lpgpsa6pzywph52
  • Data:         agent1q2f00yh23d3lhzl28tf64jhsm35gtpumt47xp6fqzp5eglupdxtnx3t72pr
  • Backtest:     agent1qvgehk9mr8d0l7hvtj25dutc52jp24yj0sqvt6ctw528h292qxlc76l664z
  • Skeptic:      agent1q2fx992h9ufw5m3nkgcn42x9hycegsnyt67x2gdxpjp3wlpze0327dxffs3

Starting Bureau...
```

Press `Ctrl + C` to stop the Bureau when verified.

---

## 4. Cache Rebuilding (Optional Offline Data Test)

To verify the offline data download and CSV cache generator:

```powershell
.venv\Scripts\python trusttest/scripts/build_cache.py
```

---

## 5. Verification Checklist

| Checkpoint | Command | Status |
|---|---|---|
| **All Unit Tests** | `python -m pytest trusttest/tests/ -v` | ✅ 35/35 Passing |
| **Lookahead Prevention** | `pytest trusttest/tests/test_backtest.py -k test_signal_shift` | ✅ Verified |
| **Skeptic Stress Suite** | `pytest trusttest/tests/test_skeptic.py` | ✅ Verified |
| **CLI Demo Run** | `python trusttest/scripts/demo.py` | ✅ Verified |
| **Multi-Agent Bureau** | `python trusttest/scripts/run_all.py` | ✅ Verified |
