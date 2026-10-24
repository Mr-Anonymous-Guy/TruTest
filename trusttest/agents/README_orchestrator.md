![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# TrustTest – Multi-Agent Strategy Backtester & Adversarial Auditor

TrustTest backtests a trading strategy you describe in plain English, then runs an adversarial audit (out-of-sample, parameter perturbation, cost sensitivity, random baseline) and returns a verdict: **Trustworthy**, **Fragile**, or **Likely Overfit**.

---

## 🎯 What TrustTest Does

1. **Natural Language Understanding**: Understands strategy rules, moving average windows, RSI thresholds, tickers, and dates directly from plain English chat.
2. **Lookahead-Free Backtesting**: Simulates trading performance with shifted 1-bar execution and real-world friction (brokerage fees and market slippage).
3. **Adversarial Quant Audit (The "Skeptic")**:
   - Out-of-sample data stress test (last 30% of history).
   - Friction sensitivity test (2x fees & slippage).
   - Parameter stability perturbation (+/-10% and +/-20% window shifts).
   - 1,000-run Monte Carlo random baseline test.
4. **Actionable Verdict**: Issues an honest, unbiased audit verdict (`✅ Trustworthy`, `⚠️ Fragile`, or `❌ Likely Overfit`).

---

## 💬 Example Prompts to Try in ASI:One

1. *"Backtest a 50/200 day moving average crossover on RELIANCE.NS for the last 5 years with 0.1% fees"*
2. *"Is an RSI 14 strategy on TCS.NS robust or overfit?"*
3. *"Audit my Nifty 50 momentum strategy"*

---

## ⚠️ Disclaimer

TrustTest is developed strictly for **educational and research purposes**. It does **NOT** constitute financial, investment, or trading advice. Historical backtest performance does not guarantee future results.
