"""
tests/test_models.py – Inter-Agent Message Models & Payload Size Benchmarks
"""

import json
import pandas as pd
from core.data import load_cached
from agents.models import df_to_price_data, prices_to_df, PriceData


def test_price_data_roundtrip():
    """Verify DataFrame to PriceData and back produces identical data."""
    dates = pd.bdate_range("2023-01-01", periods=100)
    df_orig = pd.DataFrame({"close": [100.0 + i * 0.5 for i in range(100)]}, index=dates)

    p_data = df_to_price_data("req-1", df_orig, ticker="TEST", source="cache")
    assert p_data.ok is True
    assert p_data.bars == 100
    assert len(p_data.dates) == 100
    assert len(p_data.closes) == 100

    df_recovered = prices_to_df(p_data)
    assert len(df_recovered) == 100
    assert (df_recovered["close"].values == df_orig["close"].values).all()


def test_payload_sizes_5y_and_10y():
    """
    Measure the serialized JSON size of 5-year and 10-year PriceData.
    Compare against the standard 1MB message limit to assess risk.
    """
    df = load_cached("RELIANCE.NS")

    # 5-year slice (~1,250 bars)
    dt_5y = df.index[-1] - pd.DateOffset(years=5)
    df_5y = df[df.index >= dt_5y]
    p_data_5y = df_to_price_data("req-5y", df_5y, ticker="RELIANCE.NS", source="cache")
    json_5y = json.dumps(p_data_5y.dict())
    size_5y_bytes = len(json_5y.encode("utf-8"))
    size_5y_kb = size_5y_bytes / 1024.0

    # 10-year slice (~2,500 bars)
    dt_10y = df.index[-1] - pd.DateOffset(years=10)
    df_10y = df[df.index >= dt_10y]
    p_data_10y = df_to_price_data("req-10y", df_10y, ticker="RELIANCE.NS", source="cache")
    json_10y = json.dumps(p_data_10y.dict())
    size_10y_bytes = len(json_10y.encode("utf-8"))
    size_10y_kb = size_10y_bytes / 1024.0

    print(f"\n[Payload Size Benchmark]")
    print(f"  5-Year  ({p_data_5y.bars} bars):  {size_5y_bytes:,} bytes ({size_5y_kb:.1f} KB)")
    print(f"  10-Year ({p_data_10y.bars} bars): {size_10y_bytes:,} bytes ({size_10y_kb:.1f} KB)")

    # Standard uAgents limit is 1MB (1,048,576 bytes); both must be well under 100 KB
    assert size_5y_bytes < 50_000, f"5-year payload unexpectedly large: {size_5y_bytes} bytes"
    assert size_10y_bytes < 100_000, f"10-year payload unexpectedly large: {size_10y_bytes} bytes"
