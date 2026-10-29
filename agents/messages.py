"""
agents/messages.py – Centralized User-Facing Copy for TrustTest
==============================================================
All user-facing strings live here for consistent tone, brand voice,
and easy editing. Educational only, not investment advice.
"""

from __future__ import annotations

# Greetings & Help
WELCOME_GREETING = (
    "Hey there! 👋 I'm **TrustTest**.\n"
    "I help traders stress-test their trading ideas against real market friction and statistical stress tests "
    "to see if a strategy has true edge or is just overfitted to historical noise.\n\n"
    "To get started, **what stock or index are we analyzing today?**\n"
    "(e.g. HDFC Bank, Reliance, TCS, Infosys, Nifty 50, or Apple)"
)

# Market Context Snapshots for Popular Tickers
TICKER_MARKET_SNAPSHOTS = {
    "HDFCBANK.NS": (
        "**HDFC Bank (HDFCBANK.NS)** — India's largest private lender and the anchor heavyweight of both the Nifty 50 (~11%) and Bank Nifty (~29%). 🏦\n\n"
        "With immense institutional liquidity and tight bid-ask spreads, it's one of the cleanest instruments for quantitative backtesting because slippage is typically minimal. "
        "Post its mega-merger with HDFC Ltd, it has traded in broad multi-month consolidation ranges punctuated by sharp trend legs."
    ),
    "RELIANCE.NS": (
        "**Reliance Industries (RELIANCE.NS)** — India's highest-market-cap enterprise and Nifty 50 bellwether (~9-10% weight). ⚡\n\n"
        "Driven by oil-to-chemicals, retail, and telecom (Jio), it exhibits strong trend persistence during capital expenditure and earnings cycles, making it classic territory for trend-following systems."
    ),
    "TCS.NS": (
        "**Tata Consultancy Services (TCS.NS)** — Global IT services leader and defensive cash-flow compounder. 💻\n\n"
        "Historically less volatile than broad markets, TCS frequently mean-reverts within defined valuation bands, making it an excellent candidate for oscillator and mean-reversion strategies like RSI."
    ),
    "INFY.NS": (
        "**Infosys (INFY.NS)** — Premier Indian tech bellwether with high foreign institutional ownership. 🌐\n\n"
        "More cyclical and higher-beta than TCS, Infosys experiences sharp quarterly reaction gaps and multi-month momentum runs based on global tech demand."
    ),
    "^NSEI": (
        "**Nifty 50 Index (^NSEI)** — The benchmark gauge of the Indian equity market, representing 50 blue-chip companies across 13 sectors. 📈\n\n"
        "With world-class liquidity and lower single-stock idiosyncratic risk, Nifty 50 is ideal for macro moving-average trend systems."
    ),
    "AAPL": (
        "**Apple Inc. (AAPL)** — Global consumer tech titan and dominant component of the S&P 500 and Nasdaq-100. 🍏\n\n"
        "Supported by consistent institutional inflows and aggressive share buyback programs, Apple exhibits long-term upward drift with shallow drawdowns."
    ),
}

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
