# 🛡️ TrustTest

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tests:60 passed](https://img.shields.io/badge/tests-60%20passed-brightgreen)
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

| Agent | Role | Agent Address | Agentverse Profile | Port |
|---|---|---|---|:---:|
| **Orchestrator** | ASI:One gateway; session state; pipeline coordinator | `agent1qwlf7ep22r407eu89xa8rh4qa7h95vsltfxqmk6egfxa3t7h620cksg67ak` | [Profile (Pending Connect)](https://agentverse.ai) | 8001 |
| **Parser Agent** | Plain English → structured `StrategySpec` JSON | `agent1qddf7rvzcdw466gm2ssx2q7jvwvaw6jfrnjtleq38339lpgpsa6pzywph52` | _Local / Agentverse Mailbox_ | 8005 |
| **Data Agent** | Historical market data retrieval (live + cache fallback) | `agent1q2f00yh23d3lhzl28tf64jhsm35gtpumt47xp6fqzp5eglupdxtnx3t72pr` | _Local / Agentverse Mailbox_ | 8002 |
| **Backtest Agent** | Lookahead-free quantitative simulation engine | `agent1qvgehk9mr8d0l7hvtj25dutc52jp24yj0sqvt6ctw528h292qxlc76l664z` | _Local / Agentverse Mailbox_ | 8003 |
| **Skeptic Agent** | Adversarial stress tester & auditor | `agent1q2fx992h9ufw5m3nkgcn42x9hycegsnyt67x2gdxpjp3wlpze0327dxffs3` | _Local / Agentverse Mailbox_ | 8004 |

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

## 🛡️ Reliability Engineering (Failure Handling Architecture)

TrustTest treats failure as a first-class, designed behavior. The pipeline never crashes, hangs silently, or invents quantitative numbers:

| Failure Scenario | What the User Sees in ASI:One | What is Logged (logs/trace.jsonl & logger) |
|---|---|---|
| **Typo in Ticker** (e.g. `RELIANC.NS`) | Suggests closest valid ticker: *"Did you mean RELIANCE.NS?..."* | `user_error` with difflib candidate matches |
| **Unknown Ticker** (e.g. `FAKETICK`) | Clear explanation with safe cached fallbacks: *"Ticker 'FAKETICK' could not be found. Available cached tickers: RELIANCE.NS, TCS.NS..."* | `user_error` logging unknown symbol |
| **Future or Short Dates** | Explains backtests require historical data (min 200 bars / 6 months) | `user_error` with invalid date range details |
| **Rapid Double Send** | Friendly queue notice: *"⏳ I'm still working on your previous request..."* | ConcurrencyGuard prevents race condition on session state |
| **Excessive Request Rate** (> 6/min) | Throttling notice: *"⚠️ You're sending requests too quickly..."* | RateLimiter records sliding-window throttle event |
| **Oversize Message** (> 1,000 chars) | Polite truncation notice requesting concise description | InputSanitizer flags `too_long` error |
| **Live yfinance Outage** | Seamlessly loads historical CSV; final report notes cached source | WARNING: live fetch failed, fallback to local cache CSV |
| **Language Model Unavailable** | Deterministic heuristic parser automatically extracts parameters | WARNING: LLM unavailable/breaker open, using offline parser |
| **Backtest Engine Failure** | Transparent stop naming the failure step without made-up numbers | ERROR: Backtest step failed; stack trace logged |
| **Skeptic Auditor Timeout / Offline** | **Partial Result**: Backtest metrics shown with clear disclaimer: *"The audit step was unavailable, so this result has NOT been validated. No verdict is given."* | WARNING: Skeptic hop timed out after retry; partial result issued |
| **Duplicate ASI:One Delivery** | Instant acknowledgement; duplicate payload discarded | `MessageDeduplicator` logs repeated `msg_id` |
| **Uncaught Exception Anywhere** | Friendly apology with unique reference ID: `Ref: err-XXXXXX` | Full stack trace logged with error ID; session remains usable |

---

## 🎬 Demonstrating Reliability in the Video (30s Segments)

Use these concrete fault flags and manual actions to record the reliability showcase:

1. **Status Command Health Ping (No LLM):**
   - In ASI:One chat, send `status`.
   - The Orchestrator pings all 5 agents over TCP and returns a live health table with millisecond latencies in < 1 second.
2. **Live Data Fallback Demo (`TRUSTTEST_FAULT=data_live_fail`):**
   - Set `TRUSTTEST_FAULT=data_live_fail` in `.env` and restart Data Agent.
   - Send: `"Backtest 50/200 MA cross on RELIANCE.NS"`.
   - Note in report shows: *"Simulated live data failure (TRUSTTEST_FAULT=data_live_fail); used local cached data."*
3. **Graceful Partial Result Demo (`TRUSTTEST_FAULT=skeptic_timeout` or kill Skeptic):**
   - Terminate `trusttest_skeptic` terminal (or set `TRUSTTEST_FAULT=skeptic_timeout`).
   - Run a backtest request in ASI:One.
   - Orchestrator retries once, then delivers the backtest numbers with the prominent notice: *"The audit step was unavailable, so this result has NOT been validated. No verdict is given."* Zero fabricated numbers.
4. **Offline Parser Fallback Demo (`TRUSTTEST_FAULT=parser_llm_fail`):**
   - Set `TRUSTTEST_FAULT=parser_llm_fail` or unconfigure API key.
   - Send: `"Backtest 50/200 MA crossover on RELIANCE.NS for the last 5 years with 0.1% fees"`.
   - Heuristic parser cleanly extracts parameters with explicit assumption note in report.
5. **Timeline Trace Visualizer:**
   - Run `python scripts/show_trace.py latest` in terminal.
   - Prints a clean, colorized terminal table detailing each hop's attempt count, latency, and status.

---

## ⚠️ Known Limitations

1. **Single-Machine Execution:** Agents run as separate processes on a single host. In production, each uAgent would reside on dedicated containerized cloud infrastructure.
2. **Persistent Mailbox Processes:** As standard Fetch.ai mailbox agents, running local processes are required to poll and process incoming messages from Agentverse relays.
3. **Unofficial Data Source:** Historical data uses `yfinance`, which is community-maintained and subject to rate-limiting; cached CSVs are provided for deterministic operation.
4. **Survivorship & Selection Bias:** Backtesting on current index constituents suffers from survivorship bias.
5. **Educational Scope:** TrustTest is strictly an educational tool demonstrating adversarial AI auditing; it does not execute live trades or constitute financial advice.

---

## ⚖️ Educational Disclaimer

TrustTest is developed strictly for educational and research purposes as part of Fetch-A-Thon 3.0. It is **NOT** financial, investment, or trading advice. Historical performance, backtesting, and adversarial simulations do not guarantee future returns.

---

## 🏆 Fetch-A-Thon 3.0

Built for the **ASI:One Agent Challenge** · Fetch-A-Thon 3.0 · October 2026.
