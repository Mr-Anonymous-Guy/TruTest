# TrustTest

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

> **Multi-agent strategy backtester with an adversarial "Skeptic" auditor — for Fetch-A-Thon 3.0 (ASI:One Agent Challenge)**

---

## One-line pitch

Describe any trading strategy in plain English inside ASI:One; TrustTest backtests it AND audits it for you, returning a verdict: **Trustworthy**, **Fragile**, or **Likely Overfit** — in seconds.

---

## Problem

Retail investors back-test strategies in Excel or online tools that show past P&L but never ask: _"Is this result real or just curve-fitting?"_ Overfit strategies blow up in live trading. TrustTest gives everyone a senior quant's adversarial second opinion.

---

## Target users

- Retail traders curious about algorithmic strategies
- Finance students learning quantitative analysis
- Hobbyist algo-traders who want a quick sanity check before paper trading

---

## Expected outcome

A user types a strategy in ASI:One chat (e.g. _"Buy RELIANCE.NS when the 50-day SMA crosses above the 200-day SMA"_) and receives:

1. **Backtest card** – Sharpe, max drawdown, CAGR, trade count over the full history
2. **Audit card** – 6–7 robustness tests (out-of-sample, param perturbation, cost sensitivity, Monte Carlo)
3. **Verdict** – ✅ Trustworthy / ⚠️ Fragile / ❌ Likely Overfit with a one-paragraph rationale

> ⚠️ **Educational only. Not investment advice.**

---

## Agents

| Agent | Role | Agentverse Address | Profile |
|---|---|---|---|
| Orchestrator | ASI:One-facing entry point; holds session state; drives pipeline | _TBD_ | _TBD_ |
| Parser Agent | Calls ASI:One LLM to convert plain English → StrategySpec JSON | _TBD_ | _TBD_ |
| Data Agent | Downloads OHLCV data (yfinance / CSV cache); reports data source | _TBD_ | _TBD_ |
| Backtest Agent | pandas engine; signals shifted 1 bar; fees/slippage; Sharpe, maxDD, CAGR | _TBD_ | _TBD_ |
| Skeptic Agent | OOS split, param perturbation, cost 2x, Monte Carlo → verdict | _TBD_ | _TBD_ |

---

## Message flow

```
User (ASI:One) ──ChatMessage──► Orchestrator ──► Parser ──► Data ──► Backtest ──► Skeptic ──► Orchestrator ──► User
```

---

## How to run

> TODO (Phase 1): add detailed instructions after Agentverse registration.

```bash
# 1. Clone and install
git clone https://github.com/<YOUR_USERNAME>/trusttest.git
cd trusttest
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env
# Edit .env – fill in ASI1_API_KEY and agent seeds

# 3. Build the price cache
python trusttest/scripts/build_cache.py

# 4. Run agents (each in its own terminal)
python trusttest/agents/orchestrator.py
python trusttest/agents/parser_agent.py
python trusttest/agents/data_agent.py
python trusttest/agents/backtest_agent.py
python trusttest/agents/skeptic_agent.py

# 5. Open ASI:One and chat with the Orchestrator
```

---

## Running tests

```bash
python -m pytest trusttest/tests/ -v
```

---

## Future work

- Payment protocol gate (FET micro-payment after 3 free backtests)
- More strategy types: RSI, Bollinger Bands, pairs trading
- Live US / global equities via yfinance
- Streaming results (StartStreamContent) for long backtests
- Web dashboard showing equity curve chart

---

## Disclaimer

TrustTest is for **educational purposes only**. It does **not** constitute investment advice. Past backtest performance does not predict future results. Always consult a qualified financial professional before making any investment decisions.

---

## Built at

Fetch-A-Thon 3.0 · ASI:One Agent Challenge · October 2026
