#!/usr/bin/env python3
"""Impact ranking, minor-event detection, and notability filtering.

Pure functions shared by render_brief + compose_brief (and usable by the
orchestrator at assembly time). "Minor" items are suppressed unless they're the
only data of the day (the notability override), so a surprise or a data-empty
morning still surfaces them.
"""
from __future__ import annotations

IMPACT_ORDER = {"high": 3, "medium": 2, "low": 1}

# Minor-by-name patterns (lowercased substring). High/Medium impact is never minor.
# Coupon auctions (note/bond) are intentionally NOT here — only bills are minor.
DEFAULT_MINOR_PATTERNS = [
    "mba ", "mortgage application", "mortgage market", "mortgage refinance",
    "purchase index", "redbook", "foreign bond", "foreign investment",
    "bill auction", "4-week bill", "8-week bill", "17-week bill", "26-week bill",
    "52-week bill", "richmond fed", "dallas fed", "empire state", "kansas city fed",
]


def impact_rank(impact: str | None) -> int:
    return IMPACT_ORDER.get((impact or "").strip().lower(), 0)


def is_minor(release: dict, patterns: list[str] | None = None) -> bool:
    """Low-impact or denylisted-by-name. High/Medium and unknown-impact are kept
    (we never hide something just because impact wasn't tagged)."""
    if impact_rank(release.get("impact")) >= 2:  # High/Medium never minor
        return False
    name = (release.get("name") or "").lower()
    pats = patterns if patterns is not None else DEFAULT_MINOR_PATTERNS
    if any(p in name for p in pats):
        return True
    return impact_rank(release.get("impact")) == 1  # explicit Low = minor


def sort_releases(releases: list[dict]) -> list[dict]:
    """Highest impact first, then by time."""
    return sorted(releases, key=lambda r: (-impact_rank(r.get("impact")), r.get("time_et", "99:99")))


def filter_releases(releases: list[dict], *, drop_minor: bool = True, patterns=None) -> list[dict]:
    """Drop minor releases unless they're the only data (notability override)."""
    if not drop_minor:
        return sort_releases(releases)
    major = [r for r in releases if not is_minor(r, patterns)]
    return sort_releases(major if major else releases)


def is_voter(speaker: dict) -> bool:
    v = (speaker.get("voter_status") or "").lower()
    return any(t in v for t in ("voter", "governor", "chair"))


def filter_speakers(speakers: list[dict], *, voters_only: bool = True) -> list[dict]:
    """Keep voters with a real topic; drop non-voters / ceremonial / empty-topic."""
    if not voters_only:
        return speakers
    return [s for s in speakers if is_voter(s) and (s.get("topic") or "").strip()]


def impact_tag(impact: str | None) -> str:
    return {3: "[HIGH]", 2: "[MED]", 1: "[LOW]"}.get(impact_rank(impact), "")


def impact_color(impact: str | None) -> str:
    """Google Calendar colorId: 11 Tomato (high), 5 Banana (med), 8 Graphite (low),
    7 Peacock (untagged default)."""
    return {3: "11", 2: "5", 1: "8"}.get(impact_rank(impact), "7")
