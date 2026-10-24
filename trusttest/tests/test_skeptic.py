"""
tests/test_skeptic.py – Placeholder tests for core/skeptic.py

Offline tests that DO NOT require yfinance (use synthetic DataFrames).
"""

import pandas as pd
import pytest

from trusttest.core.skeptic import decide_verdict, oos_split, perturb_params


# ---------------------------------------------------------------------------
# Tests that work offline right now (no run_audit() needed)
# ---------------------------------------------------------------------------

def _make_df(n: int = 500) -> pd.DataFrame:
    """Synthetic rising price series."""
    import numpy as np
    dates = pd.bdate_range("2015-01-01", periods=n)
    rng = np.random.default_rng(42)
    close = 100 * (1 + rng.normal(0.0003, 0.01, n)).cumprod()
    return pd.DataFrame(
        {"Open": close, "High": close * 1.005, "Low": close * 0.995,
         "Close": close, "Volume": 1_000_000},
        index=dates,
    )


class TestOosSplit:
    def test_correct_fractions(self):
        df = _make_df(500)
        train, test = oos_split(df, train_frac=0.70)
        assert len(train) == 350
        assert len(test) == 150
        assert train.index[-1] < test.index[0]

    def test_no_data_leakage(self):
        df = _make_df(500)
        train, test = oos_split(df, train_frac=0.70)
        assert set(train.index).isdisjoint(set(test.index))


class TestPerturbParams:
    def test_plus_10_pct(self):
        params = {"short_window": 50, "long_window": 200, "label": "sma"}
        out = perturb_params(params, delta=0.10)
        assert out["short_window"] == 55
        assert out["long_window"] == 220
        assert out["label"] == "sma"   # strings unchanged

    def test_minus_20_pct(self):
        params = {"period": 14}
        out = perturb_params(params, delta=-0.20)
        assert out["period"] == 11   # int(14 * 0.80) = 11

    def test_float_preserved(self):
        params = {"threshold": 0.5}
        out = perturb_params(params, delta=0.10)
        assert isinstance(out["threshold"], float)
        assert abs(out["threshold"] - 0.55) < 1e-9


class TestDecideVerdict:
    def _tests(self, n_pass: int, n_total: int) -> list:
        return [{"passed": i < n_pass} for i in range(n_total)]

    def test_trustworthy(self):
        tests = self._tests(8, 8)
        verdict, rationale = decide_verdict(tests, mc_beat_rate_pct=75.0)
        assert verdict == "Trustworthy"
        assert "Trustworthy" in verdict

    def test_fragile(self):
        tests = self._tests(4, 8)   # 50 % pass
        verdict, _ = decide_verdict(tests, mc_beat_rate_pct=75.0)
        assert verdict == "Fragile"

    def test_likely_overfit(self):
        tests = self._tests(2, 8)   # 25 % pass
        verdict, _ = decide_verdict(tests, mc_beat_rate_pct=20.0)
        assert verdict == "Likely Overfit"

    def test_good_pass_rate_but_low_mc(self):
        tests = self._tests(8, 8)   # 100 % pass…
        verdict, _ = decide_verdict(tests, mc_beat_rate_pct=40.0)  # but poor MC
        assert verdict == "Fragile"


# ---------------------------------------------------------------------------
# Placeholder for run_audit() tests (Phase 2)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Phase 2 – run_audit() not yet implemented")
def test_oos_sharpe_less_than_full_sample():
    pass


@pytest.mark.skip(reason="Phase 2 – run_audit() not yet implemented")
def test_monte_carlo_beat_rate_range():
    pass
