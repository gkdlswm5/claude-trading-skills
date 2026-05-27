"""Tests for check_geo_quality.py — the geo-wrap anti-bias validator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from check_geo_quality import check_geo_quality  # noqa: E402


def test_clean_factual_wrap_passes():
    text = (
        "CONFIRMED ECB held the deposit rate at 3.00% (ECB statement) — "
        "EUR/USD +0.4% to 1.16, DXY -0.3%.\n"
        "REPORTED Hormuz transit restriction eased (Reuters, Bloomberg) — Brent -1.8%."
    )
    r = check_geo_quality(text)
    assert r["passed"] is True
    assert r["hard_fails"] == []


def test_banned_lexicon_hard_fails():
    r = check_geo_quality("Oil soared on the news (Reuters) — WTI +5%")
    assert r["passed"] is False
    assert any("soared" in f for f in r["hard_fails"])


def test_quantified_claim_without_source_hard_fails():
    r = check_geo_quality("Brent jumped +2.1% to $90 overnight.")
    assert r["passed"] is False
    assert any("without allowlisted source" in f for f in r["hard_fails"])


def test_quantified_claim_with_source_passes():
    r = check_geo_quality("Brent +2.1% to $90 (Reuters, Bloomberg).")
    assert r["passed"] is True


def test_prediction_language_warns_but_passes():
    r = check_geo_quality("ECB held rates (ECB) — EUR/USD flat; analysts expect more volatility.")
    assert r["passed"] is True
    assert any("prediction" in w for w in r["warnings"])


def test_unconfirmed_marker_warns():
    r = check_geo_quality("Ceasefire reportedly agreed (Reuters) — gold -0.5%.")
    assert any("single-source" in w for w in r["warnings"])


def test_empty_text_passes():
    r = check_geo_quality("")
    assert r["passed"] is True
    assert r["hard_fails"] == []


def test_qualitative_no_number_no_source_passes():
    """A purely qualitative line with no market number isn't a quantified claim."""
    r = check_geo_quality("Trade talks resume Thursday in Geneva.")
    assert r["passed"] is True
