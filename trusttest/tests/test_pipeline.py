"""
tests/test_pipeline.py – End-to-end pipeline integration tests
"""

import pytest
from trusttest.agents.parser_agent import _heuristic_parse, parse_strategy
from trusttest.core.pipeline import format_result_card, run_pipeline


def test_heuristic_parser_sma():
    text = "Buy Reliance when 50 SMA crosses above 200 SMA from 2018 to 2024"
    spec = _heuristic_parse(text)
    assert spec.ticker == "RELIANCE.NS"
    assert spec.strategy_type == "sma_crossover"
    assert spec.params["short_window"] == 50
    assert spec.params["long_window"] == 200
    assert spec.start == "2018-01-01"
    assert spec.end == "2024-01-01"


def test_heuristic_parser_rsi():
    text = "RSI below 25 buy, exit above 75 on TCS.NS"
    spec = _heuristic_parse(text)
    assert spec.ticker == "TCS.NS"
    assert spec.strategy_type == "rsi_threshold"
    assert spec.params["oversold"] == 25.0
    assert spec.params["overbought"] == 75.0


def test_heuristic_parser_momentum():
    text = "20-day momentum on AAPL"
    spec = _heuristic_parse(text)
    assert spec.ticker == "AAPL"
    assert spec.strategy_type == "momentum"
    assert spec.params["lookback"] == 20


def test_end_to_end_pipeline_sma():
    """Run full pipeline on cached/live Reliance data."""
    text = "Buy Reliance when 50 SMA crosses above 200 SMA from 2018 to 2024"
    result = run_pipeline(text)
    assert "## 🛡️ TrustTest Audit Report" in result
    assert "Strategy: **Sma Crossover**" in result
    assert "Sharpe Ratio" in result
    assert "Skeptic Adversarial Audit" in result
    assert "Robustness Stress Tests" in result
    assert "Monte Carlo Benchmark" in result
    assert "Disclaimer:" in result


def test_end_to_end_pipeline_rsi():
    """Run full pipeline on cached/live TCS data."""
    text = "RSI below 30 buy, exit above 70 on TCS.NS from 2019 to 2023"
    result = run_pipeline(text)
    assert "## 🛡️ TrustTest Audit Report" in result
    assert "TCS.NS" in result
    assert "Verdict:" in result


def test_pipeline_error_handling():
    """Test response when a totally unknown ticker with no cache is provided."""
    result = run_pipeline("Buy XYZUNKNOWNSTOCK on 10 SMA from 2020 to 2022")
    # Should produce either a graceful card or error message with advice
    assert "TrustTest" in result
