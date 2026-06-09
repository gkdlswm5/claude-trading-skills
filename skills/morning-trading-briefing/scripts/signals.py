"""Shared snapshot + good/bad-signal helpers for the morning-trading-briefing.

v2.2 — snapshot consistency + readability signals.

Two concerns live here so render_brief.py and compose_brief.py share one
source of truth:

1. as_of_et(): derive a single "HH:MM ET" stamp from the one
   `generated_at_et` field the LLM captures in brief_data.json. This is the
   v2.2 "snapshot as of" moment — captured once, shown everywhere (header +
   all-day event titles), so a re-run can't show three different times.

2. signal()/tag(): a "good-for-your-book" 🟢/🔴 marker (standard risk-on
   convention). Emoji is the only formatting that survives across all three
   surfaces — Drive PDF, Calendar event body, AND Calendar event title
   (verified empirically; inline color spans are stripped by Google's UI).
   Kept deliberately minimal: snapshot, P&L, and movers only.
"""

from __future__ import annotations

import re

GOOD = "\U0001f7e2"  # 🟢
BAD = "\U0001f534"  # 🔴

# Metrics where a RISE is bad for a net-long, risk-on book. Everything else
# (indices, single equities, P&L) is good when it rises.
INVERTED_METRICS = frozenset({"vix", "us2y", "us10y", "us30y", "dxy"})


def as_of_et(generated_at_et: str | None) -> str:
    """Return 'HH:MM ET' from a 'YYYY-MM-DD HH:MM ET' generated_at_et string.

    Falls back to the raw input (or '') if it doesn't match the expected
    shape, so a malformed stamp degrades to something rather than crashing.
    """
    if not generated_at_et:
        return ""
    m = re.search(r"\b(\d{1,2}:\d{2})\b", generated_at_et)
    if not m:
        return generated_at_et.strip()
    return f"{m.group(1)} ET"


def pct_sign(value: str | float | None) -> int:
    """Sign of a change value: +1 up, -1 down, 0 flat/unknown.

    Accepts strings like '+0.4%', '-1.2%', '+$420', '(1.2%)' (accounting
    negative), plain numbers, or junk ('—', None) → 0.
    """
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return (value > 0) - (value < 0)
    s = str(value).strip()
    if not s or s in {"—", "-", "n/a", "N/A"}:
        return 0
    # Accounting-style negatives: (1.2%)
    neg_paren = s.startswith("(") and s.endswith(")")
    if s.startswith("+"):
        return 1
    if s.startswith("-") or neg_paren or s.startswith("−"):  # − U+2212
        return -1
    # No explicit sign: look for a leading number; treat positive as up.
    m = re.search(r"-?\d", s)
    if m and m.group(0) == "-":
        return -1
    return 1 if re.search(r"\d", s) else 0


def signal(value: str | float | None, *, metric: str = "") -> str:
    """Return 🟢 / 🔴 / '' for a change value under good-for-your-book rules.

    metric (case-insensitive) selects direction: INVERTED_METRICS rise = bad.
    A flat/unknown value returns '' (no marker — don't clutter).
    """
    sign = pct_sign(value)
    if sign == 0:
        return ""
    if metric.lower() in INVERTED_METRICS:
        sign = -sign
    return GOOD if sign > 0 else BAD


def tag(value: str | float | None, *, metric: str = "") -> str:
    """'🟢 +0.4%' — emoji + a space + the original value. Bare value if flat."""
    emo = signal(value, metric=metric)
    if not emo:
        return "" if value in (None, "") else str(value)
    return f"{emo} {value}"
