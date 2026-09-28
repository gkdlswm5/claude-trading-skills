"""Tests for technicals.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from technicals import build_levels, key_levels, risk_regime  # noqa: E402


def test_key_levels_uptrend():
    closes = list(range(100, 260))  # steadily rising → last above both MAs
    lv = key_levels(closes)
    assert lv["last"] == 259
    assert lv["sma50"] is not None and lv["sma200"] is not None
    assert lv["last"] > lv["sma50"] > lv["sma200"]
    assert "uptrend" in lv["trend"]
    assert lv["resistance_20d"] == 259
    assert lv["pct_vs_sma50"] > 0


def test_key_levels_short_series_uses_available():
    lv = key_levels([10, 12, 11])
    assert lv["last"] == 11
    assert lv["sma50"] == round((10 + 12 + 11) / 3, 2)  # falls back to mean-all


def test_key_levels_empty():
    assert key_levels([]) == {}


def test_build_levels_multi():
    out = build_levels({"SPY": [1, 2, 3], "QQQ": [5, 4, 6]})
    assert {r["ticker"] for r in out} == {"SPY", "QQQ"}


def test_risk_regime_risk_on():
    r = risk_regime(spy_closes=list(range(100, 260)), vix=14.0, breadth_pct=70)
    assert r["label"] == "risk-on"
    assert r["score"] >= 2


def test_risk_regime_risk_off():
    r = risk_regime(spy_closes=list(range(260, 100, -1)), vix=30.0, breadth_pct=30)
    assert r["label"] == "risk-off"
    assert r["score"] <= -1


def test_risk_regime_insufficient_data():
    r = risk_regime()
    assert r["label"] == "neutral"
    assert r["reason"] == "insufficient data"
