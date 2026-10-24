"""
agents/messages.py – Centralized User-Facing Copy for TrustTest
==============================================================
All user-facing strings live here for consistent tone, brand voice,
and easy editing. Educational only, not investment advice.
"""

from __future__ import annotations

# Greetings & Help
WELCOME_GREETING = (
    "🛡️ TrustTest is online!\n\n"
    "• 💬 Chat naturally: Describe any trading strategy in plain English (e.g. 'Backtest 50/200 MA cross on RELIANCE.NS' or 'RSI 14 on TCS.NS').\n"
    "• 🎛️ Custom inputs: Type 'form' or tap 'Open Form' in the carousel below to test your own custom parameters.\n"
    "• 📊 Benchmarks: Select Demo A, B, or C below for instant verified examples.\n\n"
    "I'll fetch real market data, run a lookahead-free backtest, and perform an adversarial Skeptic audit in real time. (Educational only, not investment advice.)"
)

# Concurrency & Rate Limiting
STILL_WORKING = (
    "⏳ I'm still working on your previous request. Please wait a moment for the backtest and audit to complete."
)

RATE_LIMITED = (
    "⚠️ You're sending requests too quickly. To protect service reliability, please wait a minute before submitting another backtest."
)

# Input Validation
MSG_TOO_LONG = (
    "⚠️ Your strategy description is too long (over 1,000 characters). "
    "Please provide a concise description of your strategy (e.g. 'Backtest 50/200 MA cross on RELIANCE.NS from 2018 to 2024')."
)

MSG_EMPTY = (
    "Please describe a trading strategy in plain English to backtest (e.g. 'Buy Reliance when 50 MA crosses above 200 MA')."
)

FUTURE_DATES = (
    "⚠️ Backtesting requires historical data. Future dates cannot be tested. "
    "Please choose a date range in the past (e.g. 2018-01-01 to 2024-01-01)."
)

SHORT_WINDOW = (
    "⚠️ The selected date window is too short (less than 90 days). "
    "A robust backtest requires at least 6 months of historical price data to compute moving averages and evaluate drawdown."
)

UNKNOWN_TICKER_TEMPLATE = (
    "⚠️ Ticker '{ticker}' was not recognized. "
    "Please use a supported ticker such as RELIANCE.NS, TCS.NS, INFY.NS, or AAPL (cached data available for offline testing)."
)

TYPO_TICKER_TEMPLATE = (
    "Did you mean {suggested}? Please reply with your strategy using a valid ticker (e.g. RELIANCE.NS, TCS.NS, AAPL)."
)

# Pipeline Step Failures
PARSER_FAILED = (
    "Sorry, the Strategy Parser was unable to extract your strategy parameters. "
    "Please try rephrasing (e.g. 'Backtest a 50/200 moving average crossover on RELIANCE.NS')."
)

DATA_FAILED_TEMPLATE = (
    "❌ Pipeline Step 2 (Market Data) failed for {ticker}: {reason}. "
    "Please verify the ticker symbol or try one of our cached assets: RELIANCE.NS, TCS.NS, INFY.NS, AAPL."
)

BACKTEST_FAILED_TEMPLATE = (
    "❌ Pipeline Step 3 (Backtest Engine) failed: {reason}. "
    "No simulation metrics could be computed."
)

SKEPTIC_DEGRADED_NOTE = (
    "The adversarial audit step was unavailable, so this result has NOT been validated. No verdict is given."
)

INTERNAL_ERROR_TEMPLATE = (
    "Sorry, an unexpected error occurred while processing your request (Ref: {error_id}). "
    "Our team has logged this issue. Please try again in a few moments."
)
