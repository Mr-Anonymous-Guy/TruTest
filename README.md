# 🛡️ TrustTest

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tests:35 passed](https://img.shields.io/badge/tests-35%20passed-brightgreen)
![uagents:0.26.1](https://img.shields.io/badge/uagents-0.26.1-blue)
![protocol:ACP--0.3.0](https://img.shields.io/badge/protocol-ACP--0.3.0-orange)
![python:3.11+](https://img.shields.io/badge/python-3.11+-blue)

> **Multi-agent strategy backtester with an adversarial "Skeptic" auditor — for Fetch-A-Thon 3.0 (ASI:One Agent Challenge)**

---

## ⚡ One-Line Pitch

Describe any trading strategy in plain English inside ASI:One; **TrustTest** runs an institutional-grade backtest AND unleashes an adversarial **Skeptic** agent that actively tries to break the result — returning a definitive verdict: **✅ Trustworthy**, **⚠️ Fragile**, or **❌ Likely Overfit** in seconds.

---

## 🧐 The Problem: The Backtest Mirage

Retail investors back-test strategies in spreadsheets or basic websites that trumpet impressive past returns. But they never test the critical questions:
- *Is this result real or just curve-fitted overfit?*
- *Does it survive when execution costs double?*
- *Does it collapse out-of-sample or when parameters shift slightly (+/-10%)?*
- *Does it perform any better than 1,000 completely random trades?*

Overfit strategies fail when deployed live. **TrustTest** provides every retail trader with an adversarial quantitative research auditor directly inside ASI:One chat.

---

## 🤖 The 5 Cooperating uAgents

TrustTest is powered by 5 specialized uAgents collaborating over Fetch.ai's Agent Chat Protocol (ACP 0.3.0):

| Agent | Role | Agent Address | Protocol / Technology |
|---|---|---|---|
| **Orchestrator** | ASI:One-facing entry point; session state management; pipeline coordinator | `agent1qwlf7ep22r407eu89xa8rh4qa7h95vsltfxqmk6egfxa3t7h620cksg67ak` | ACP 0.3.0 (`chat_protocol_spec`) |
| **Parser Agent** | Plain English → structured `StrategySpec` JSON | `agent1qddf7rvzcdw466gm2ssx2q7jvwvaw6jfrnjtleq38339lpgpsa6pzywph52` | ASI:One LLM API (`asi1`) + heuristic fallback |
| **Data Agent** | Historical OHLCV market data retrieval | `agent1q2f00yh23d3lhzl28tf64jhsm35gtpumt47xp6fqzp5eglupdxtnx3t72pr` | Live `yfinance` + Local CSV Cache (`data/cache/`) |
| **Backtest Agent** | Lookahead-free quantitative simulation engine | `agent1qvgehk9mr8d0l7hvtj25dutc52jp24yj0sqvt6ctw528h292qxlc76l664z` | pandas / NumPy, 1-bar signal shift, fees & slippage |
| **Skeptic Agent** | Adversarial stress tester & auditor | `agent1q2fx992h9ufw5m3nkgcn42x9hycegsnyt67x2gdxpjp3wlpze0327dxffs3` | OOS (30%), 2x costs, param perturbations, Monte Carlo |

---

## 🔄 Multi-Agent Architecture & Message Flow

```
User (ASI:One Chat)
        │
   ChatMessage (ACP 0.3.0)
        ▼
[ Orchestrator Agent ] ◄── ChatAcknowledgement (instant)
        │
        ├──► [ Parser Agent ] (Extracts ticker, strategy type, windows, dates)
        │         │ StrategySpec
        │         ▼
        ├──► [ Market Data Agent ] (Checks yfinance live; falls back to CSV cache)
        │         │ PriceData (OHLCV bars + source label)
        │         ▼
        ├──► [ Backtest Agent ] (Shifted 1-bar signals, fee drag, Sharpe, maxDD, CAGR)
        │         │ BacktestResult
        │         ▼
        └──► [ Skeptic Agent ] (OOS split, cost 2x, +/-10%/20% perturbations, 1,000 MC runs)
                  │ AuditReport (Verdict: Trustworthy / Fragile / Likely Overfit)
                  ▼
[ Orchestrator Agent ] formats Interactive Markdown Result Card
        │
   ChatMessage (ACP 0.3.0)
        ▼
User (ASI:One Chat)
```

---

## 🔬 Adversarial Tests Performed by the Skeptic

1. **Out-of-Sample (OOS) Split (70/30):** Evaluates performance strictly on unseen data without lookahead or data leakage.
2. **Cost Sensitivity (2x Friction):** Doubles fees and slippage to ensure the strategy does not rely on zero-friction assumptions.
3. **Parameter Perturbation (+10%, -10%, +20%, -20%):** Tests parameter stability. If changing a 50-day SMA to 55 or 45 causes performance to invert, the strategy is overfit to historical noise.
4. **Monte Carlo Random-Entry Benchmark (1,000 runs):** Generates 1,000 randomized entry/exit paths with identical trade frequency to establish the 95th-percentile baseline Sharpe ratio.
5. **Verdict Engine:**
   - **✅ Trustworthy:** $\ge 75\%$ tests pass AND beats $> 60\%$ of Monte Carlo random baselines.
   - **⚠️ Fragile:** $\ge 50\%$ tests pass, but sensitive to realistic market friction or parameter drift.
   - **❌ Likely Overfit:** $< 50\%$ tests pass; performance collapses outside historical parameters.

---

## 📋 Sample Interactive Output

```markdown
## 🛡️ TrustTest Audit Report

### Strategy: **Sma Crossover** on `RELIANCE.NS`
- **Parameters:** `short_window=50, long_window=200`
- **Backtest Window:** `2018-01-01` → `2024-01-01`
- **Assumed Costs:** `10 bps fees` + `5 bps slippage` (per trade)
- **Data Source:** 🔴 Live (yfinance)

---

### 📊 Performance Metrics
| Metric | Result | Benchmark / Notes |
| :--- | :--- | :--- |
| **Sharpe Ratio** | **`0.01`** | Risk-free rate: 5% |
| **CAGR** | **`2.2%`** | Annualized compounded growth |
| **Total Return** | **`13.6%`** | Net of fees & slippage |
| **Max Drawdown** | **`45.6%`** | Peak-to-trough decline |
| **Trade Count** | **`11`** | Shifted 1-bar execution |
| **Win Rate** | **`66.7%`** | Profitable trades |

---

### 🧐 Skeptic Adversarial Audit
#### Verdict: ❌ **Likely Overfit**
> *"Only 2/7 tests passed. Performance collapses outside training conditions — classic overfit."*

**Robustness Stress Tests (2/7 passed):**

| Test | Status | Finding |
| :--- | :---: | :--- |
| **Out Of Sample** | ❌ Fail | OOS Sharpe is -0.32 (baseline: 0.01) |
| **Cost 2X** | ❌ Fail | Double costs (20+10 bps) Sharpe: -0.01 |
| **Param Perturb P10** | ✅ Pass | +10% params yields Sharpe 0.08 |
| **Param Perturb M10** | ❌ Fail | -10% params yields Sharpe -0.08 |
| **Param Perturb P20** | ✅ Pass | +20% params yields Sharpe 0.10 |
| **Param Perturb M20** | ❌ Fail | -20% params yields Sharpe -0.49 |
| **Monte Carlo** | ❌ Fail | Beats 20.4% of 500 random runs (95th %ile Sharpe: 0.72) |

**Monte Carlo Benchmark:**
Strategy beats **20.4%** of 1,000 random-entry baselines (95th percentile Sharpe: `0.72`).

---
⚠️ **Disclaimer:** *TrustTest is strictly an educational tool demonstrating multi-agent adversarial strategy auditing. It does NOT constitute financial or investment advice.*
```

---

## 🚀 Quickstart Guide

### 1. Installation

```bash
git clone https://github.com/Mr-Anonymous-Guy/Fetch-A-Thon_3.0.git
cd Fetch-A-Thon_3.0
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
cp .env.example .env
# Optional: add your ASI1_API_KEY if testing live LLM parsing
```

### 3. Build Offline Market Data Cache

```bash
python trusttest/scripts/build_cache.py
```
*(Caches NSE tickers `RELIANCE.NS`, `TCS.NS`, `INFY.NS`, `HDFCBANK.NS`, `^NSEI`, and US equity `AAPL`)*

### 4. Run the Test Suite (35 Unit & Integration Tests)

```bash
python -m pytest trusttest/tests/ -v
```

### 5. Run the Standalone CLI Demo

```bash
# Run with default prompt:
python trusttest/scripts/demo.py

# Or provide your custom plain-English strategy:
python trusttest/scripts/demo.py "RSI below 30 buy, exit above 70 on TCS.NS from 2019 to 2023"
```

### 6. Run the Multi-Agent Bureau / Orchestrator

```bash
# Launch all 5 agents together in a Bureau:
python trusttest/scripts/run_all.py

# Or run Orchestrator standalone for ASI:One Agentverse chat:
python trusttest/agents/orchestrator.py
```

---

## 🛡️ Reliability & Edge Case Engineering

- **No Lookahead Bias:** All signals are strictly shifted by +1 bar. Entries occur on day $t+1$ returns.
- **Realistic Transaction Costs:** Fees and slippage are deducted on every trade (entries and exits).
- **Zero-Downtime Data Fallback:** If `yfinance` network times out, the Data Agent seamlessly serves verified local CSVs from `data/cache/`.
- **Hybrid Parser Resilience:** When `ASI1_API_KEY` is not present or LLM calls time out, a rule-based parser guarantees uninterrupted demo operation.
- **Windows Console Safe:** Full UTF-8 stdout configuration prevents `cp1252` encoding exceptions on Windows environments.

---

## ⚖️ Educational Disclaimer

TrustTest is developed strictly for educational and research purposes as part of Fetch-A-Thon 3.0. It is **NOT** financial, investment, or trading advice. Historical performance, backtesting, and adversarial simulations do not guarantee future returns.

---

## 🏆 Fetch-A-Thon 3.0

Built for the **ASI:One Agent Challenge** · Fetch-A-Thon 3.0 · October 2026.
