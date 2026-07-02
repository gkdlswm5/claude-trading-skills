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
    "mba ",
    "mortgage application",
    "mortgage market",
    "mortgage refinance",
    "purchase index",
    "redbook",
    "foreign bond",
    "foreign investment",
    "bill auction",
    "4-week bill",
    "8-week bill",
    "17-week bill",
    "26-week bill",
    "52-week bill",
    "richmond fed",
    "dallas fed",
    "empire state",
    "kansas city fed",
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
    return sorted(
        releases, key=lambda r: (-impact_rank(r.get("impact")), r.get("time_et", "99:99"))
    )


def filter_releases(
    releases: list[dict],
    *,
    drop_minor: bool = True,
    patterns=None,
    include_tier3: bool = True,
) -> list[dict]:
    """Drop minor releases unless they're the only data (notability override).

    include_tier3=False (v2.3 noise reduction) additionally drops any release
    that is_minor() flags as low-impact/denylisted — i.e. it folds the
    "Tier-3" macro (regional Fed surveys, mortgage apps, bill auctions) out of
    the calendar entirely. Default True preserves prior behavior. The
    notability override still applies: if EVERYTHING is minor, the day's
    releases are kept rather than blanked out, so a quiet morning isn't empty.

    Note: with drop_minor=True the visible result is the same either way today
    (both drop the minor set); include_tier3 is the explicit, config-driven
    knob the orchestrator threads from `macro.include_tier3`, and the override
    semantics differ — see tests.
    """
    if not drop_minor and include_tier3:
        return sort_releases(releases)
    major = [r for r in releases if not is_minor(r, patterns)]
    if major:
        return sort_releases(major)
    # Everything is minor → notability override keeps the day from going blank.
    return sort_releases(releases)


def is_voter(speaker: dict) -> bool:
    v = (speaker.get("voter_status") or "").lower()
    return any(t in v for t in ("voter", "governor", "chair"))


def filter_speakers(speakers: list[dict], *, voters_only: bool = True) -> list[dict]:
    """Keep voters with a real topic; drop non-voters / ceremonial / empty-topic."""
    if not voters_only:
        return speakers
    return [s for s in speakers if is_voter(s) and (s.get("topic") or "").strip()]


def _implied_move_pct(entry: dict) -> float:
    """Parse implied_move ('8.5' or '8.5%') to a float; missing/garbage → 0."""
    try:
        return float(str(entry.get("implied_move", "")).strip().rstrip("%"))
    except (ValueError, TypeError):
        return 0.0


def _market_cap(entry: dict) -> float:
    """Parse market_cap to a float. Accepts a number or a string like
    '2.5T', '900B', '450M', '1,200000000', or plain digits. Missing → 0."""
    raw = entry.get("market_cap")
    if raw is None or raw == "":
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(",", "").replace("$", "")
    mult = 1.0
    if s and s[-1].upper() in {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}:
        mult = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}[s[-1].upper()]
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def earnings_importance(entry: dict) -> float:
    """Rank value for an earnings entry, faithful to the HANDOFF intent
    `max(market_cap, implied_move × market_cap)`.

    With market_cap in dollars and implied_move a percent, the raw formula
    reduces to market_cap, so we implement the clear intent: size, amplified
    when a large move is priced in →  market_cap × max(1, implied_move_pct).
    When market_cap is absent (orchestrator didn't supply it), fall back to
    implied_move alone so ranking still degrades gracefully.
    """
    mcap = _market_cap(entry)
    move = _implied_move_pct(entry)
    if mcap > 0:
        return mcap * max(1.0, move)
    return move


def cap_earnings(
    entries: list[dict], max_count: int = 8, *, positions_first: bool = True
) -> list[dict]:
    """Rank earnings entries and keep the top `max_count`.

    positions_first: entries with a truthy `position_summary` (your holdings)
    sort ahead of the rest, then by earnings_importance() within each group.
    max_count <= 0 means no cap (return all, ranked).
    """

    def key(e: dict):
        held = 0 if (positions_first and e.get("position_summary")) else 1
        return (held, -earnings_importance(e))

    ranked = sorted(entries, key=key)
    return ranked if max_count <= 0 else ranked[:max_count]


def impact_tag(impact: str | None) -> str:
    return {3: "[HIGH]", 2: "[MED]", 1: "[LOW]"}.get(impact_rank(impact), "")


def impact_color(impact: str | None) -> str:
    """Google Calendar colorId: 11 Tomato (high), 5 Banana (med), 8 Graphite (low),
    7 Peacock (untagged default)."""
    return {3: "11", 2: "5", 1: "8"}.get(impact_rank(impact), "7")
