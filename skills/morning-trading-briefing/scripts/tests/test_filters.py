"""Tests for event_filters.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from event_filters import (  # noqa: E402
    cap_earnings,
    earnings_importance,
    filter_releases,
    filter_speakers,
    impact_color,
    impact_rank,
    impact_tag,
    is_minor,
    sort_releases,
)


def test_impact_rank():
    assert impact_rank("High") == 3
    assert impact_rank("medium") == 2
    assert impact_rank("Low") == 1
    assert impact_rank(None) == 0


def test_is_minor_by_impact_and_name():
    assert is_minor({"name": "Richmond Fed Manufacturing Index", "impact": "Low"})
    assert is_minor({"name": "MBA Mortgage Applications", "impact": "Low"})
    assert is_minor({"name": "17-Week Bill Auction", "impact": "Low"})
    # High/Medium never minor, even if name matches
    assert not is_minor({"name": "Richmond Fed", "impact": "High"})
    # Coupon auctions are NOT minor
    assert not is_minor({"name": "30-Year Bond Auction", "impact": "Medium"})
    # Unknown impact is kept (not hidden just for missing tag)
    assert not is_minor({"name": "Some New Print"})


def test_filter_drops_minor_but_keeps_major():
    rel = [
        {"name": "CPI", "impact": "High", "time_et": "08:30"},
        {"name": "Redbook", "impact": "Low", "time_et": "08:55"},
        {"name": "Richmond Fed", "impact": "Low", "time_et": "10:00"},
    ]
    out = filter_releases(rel)
    names = [r["name"] for r in out]
    assert names == ["CPI"]


def test_notability_override_when_only_minor():
    """Data-empty day: if everything is minor, keep it rather than blank out."""
    rel = [
        {"name": "Redbook", "impact": "Low", "time_et": "08:55"},
        {"name": "MBA Mortgage Applications", "impact": "Low", "time_et": "07:00"},
    ]
    out = filter_releases(rel)
    assert len(out) == 2  # nothing dropped — it's the only data


def test_sort_by_impact_then_time():
    rel = [
        {"name": "Low2", "impact": "Low", "time_et": "09:00"},
        {"name": "High1", "impact": "High", "time_et": "10:00"},
        {"name": "Med1", "impact": "Medium", "time_et": "08:00"},
    ]
    assert [r["name"] for r in sort_releases(rel)] == ["High1", "Med1", "Low2"]


def test_filter_speakers():
    sp = [
        {"name": "Cook", "voter_status": "Governor (permanent voter)", "topic": "policy path"},
        {"name": "Logan", "voter_status": "Dallas Fed Pres", "topic": "minor"},
        {"name": "X", "voter_status": "voter", "topic": ""},
    ]
    out = filter_speakers(sp)
    assert [s["name"] for s in out] == ["Cook"]


def test_tags_and_colors():
    assert impact_tag("High") == "[HIGH]"
    assert impact_tag("Low") == "[LOW]"
    assert impact_tag(None) == ""
    assert impact_color("High") == "11"
    assert impact_color("Medium") == "5"
    assert impact_color(None) == "7"


# --------------------------------------------------------------------------- #
# v2.3 — tier-3 macro switch
# --------------------------------------------------------------------------- #
def test_include_tier3_false_drops_minor():
    rel = [
        {"name": "CPI", "impact": "High", "time_et": "08:30"},
        {"name": "Dallas Fed Services", "impact": "Low", "time_et": "10:30"},
    ]
    out = filter_releases(rel, drop_minor=False, include_tier3=False)
    assert [r["name"] for r in out] == ["CPI"]


def test_include_tier3_true_with_drop_minor_false_keeps_all():
    rel = [
        {"name": "CPI", "impact": "High", "time_et": "08:30"},
        {"name": "Dallas Fed Services", "impact": "Low", "time_et": "10:30"},
    ]
    out = filter_releases(rel, drop_minor=False, include_tier3=True)
    assert len(out) == 2


def test_tier3_notability_override_keeps_quiet_day():
    rel = [
        {"name": "Redbook", "impact": "Low", "time_et": "08:55"},
        {"name": "Richmond Fed", "impact": "Low", "time_et": "10:00"},
    ]
    out = filter_releases(rel, include_tier3=False)
    assert len(out) == 2  # all-minor day not blanked out


# --------------------------------------------------------------------------- #
# v2.3 — earnings importance + cap
# --------------------------------------------------------------------------- #
def test_market_cap_parsing_via_importance():
    # 2T mega-cap, no move → importance == market cap.
    assert earnings_importance({"ticker": "AAPL", "market_cap": "2T"}) == 2e12


def test_importance_amplifies_by_move():
    # 100B with 10% implied move → 100B × 10.
    assert earnings_importance({"market_cap": "100B", "implied_move": "10"}) == 1e12


def test_importance_falls_back_to_move_without_mcap():
    assert earnings_importance({"implied_move": "8.5"}) == 8.5
    assert earnings_importance({}) == 0.0


def test_cap_earnings_keeps_top_n_by_importance():
    entries = [
        {"ticker": "A", "market_cap": "10B"},
        {"ticker": "B", "market_cap": "500B"},
        {"ticker": "C", "market_cap": "50B"},
    ]
    out = cap_earnings(entries, max_count=2)
    assert [e["ticker"] for e in out] == ["B", "C"]


def test_cap_earnings_positions_first():
    entries = [
        {"ticker": "BIG", "market_cap": "2T"},
        {"ticker": "MINE", "market_cap": "5B", "position_summary": "long 100sh"},
    ]
    out = cap_earnings(entries, max_count=8)
    # Held name sorts first despite far smaller cap.
    assert out[0]["ticker"] == "MINE"


def test_cap_earnings_no_cap_when_nonpositive():
    entries = [{"ticker": "A"}, {"ticker": "B"}, {"ticker": "C"}]
    assert len(cap_earnings(entries, max_count=0)) == 3


def test_cap_earnings_default_is_eight():
    entries = [{"ticker": str(i), "market_cap": f"{i}B"} for i in range(1, 12)]
    assert len(cap_earnings(entries)) == 8
