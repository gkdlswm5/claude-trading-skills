#!/usr/bin/env python3
"""Unicode sparklines — the only trend visual that fits in text-only channels
(Google Calendar event bodies, the digest). Zero dependencies.

    sparkline([1,3,2,5,4]) -> "▁▅▃█▆"
    spark_label("10Y", [4.40, 4.45, 4.49], unit="%") -> "10Y ▁▄█ 4.49% (+2.0% / 3pt)"
"""
from __future__ import annotations

_BARS = "▁▂▃▄▅▆▇█"


def _nums(values: list) -> list[float]:
    return [float(v) for v in values if isinstance(v, (int, float))]


def sparkline(values: list) -> str:
    nums = _nums(values)
    if not nums:
        return ""
    lo, hi = min(nums), max(nums)
    if hi == lo:
        return _BARS[0] * len(nums)
    span = hi - lo
    n = len(_BARS) - 1
    return "".join(_BARS[min(n, int((v - lo) / span * n + 0.5))] for v in nums)


def pct_change(values: list) -> float | None:
    nums = _nums(values)
    if len(nums) < 2 or nums[0] == 0:
        return None
    return (nums[-1] - nums[0]) / abs(nums[0]) * 100.0


def spark_label(label: str, values: list, *, unit: str = "", places: int = 2) -> str:
    """Compact 'label ▁▄█ last (+x% / Npt)' line. Empty string if no data."""
    nums = _nums(values)
    if not nums:
        return ""
    bars = sparkline(nums)
    last = f"{nums[-1]:.{places}f}{unit}"
    chg = pct_change(nums)
    chg_str = f" ({chg:+.1f}% / {len(nums)}pt)" if chg is not None else ""
    return f"{label} {bars} {last}{chg_str}"
