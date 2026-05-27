"""Tests for event_filters.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from event_filters import (  # noqa: E402
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
