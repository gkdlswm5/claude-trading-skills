#!/usr/bin/env python3
"""Key technical levels + a lightweight risk-regime read.

Pure stdlib (the stats are simple means/min/max — no pandas needed). Consumed by
the orchestrator at assembly time; results go on brief_data `key_levels` /
`risk_regime` and the renderer just displays them.

    build_levels({"SPY": [..closes..], "QQQ": [...]}) -> [{ticker, last, sma50, ...}]
    risk_regime(spy_closes=[...], vix=17.0, breadth_pct=70) -> {label, score, reason}
"""
from __future__ import annotations

import argparse
import json
import sys


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _sma(closes: list[float], n: int) -> float | None:
    if not closes:
        return None
    return round(_mean(closes[-n:]) if len(closes) >= n else _mean(closes), 2)


def key_levels(closes: list[float]) -> dict:
    """Levels from a daily-close series (oldest→newest)."""
    nums = [float(c) for c in closes if isinstance(c, (int, float))]
    if not nums:
        return {}
    last = round(nums[-1], 2)
    sma50, sma200 = _sma(nums, 50), _sma(nums, 200)
    window = nums[-20:]
    resistance, support = round(max(window), 2), round(min(window), 2)

    above50 = sma50 is not None and last >= sma50
    above200 = sma200 is not None and last >= sma200
    if above50 and above200:
        trend = "uptrend (above 50 & 200 DMA)"
    elif not above50 and not above200:
        trend = "downtrend (below 50 & 200 DMA)"
    else:
        trend = "mixed (between 50 & 200 DMA)"

    return {
        "last": last,
        "prior_close": round(nums[-2], 2) if len(nums) >= 2 else None,
        "sma50": sma50,
        "sma200": sma200,
        "support_20d": support,
        "resistance_20d": resistance,
        "pct_vs_sma50": round((last / sma50 - 1) * 100, 1) if sma50 else None,
        "pct_vs_sma200": round((last / sma200 - 1) * 100, 1) if sma200 else None,
        "trend": trend,
    }


def build_levels(series: dict[str, list]) -> list[dict]:
    out = []
    for ticker, closes in series.items():
        lv = key_levels(closes)
        if lv:
            out.append({"ticker": ticker, **lv})
    return out


def risk_regime(spy_closes: list | None = None, vix: float | None = None, breadth_pct: float | None = None) -> dict:
    """Risk-on/off score from trend (SPY vs MAs) + volatility (VIX) + breadth."""
    score = 0
    reasons = []
    if spy_closes:
        lv = key_levels(spy_closes)
        if lv.get("sma50") is not None:
            if lv["last"] >= lv["sma50"]:
                score += 1
                reasons.append("SPY > 50DMA")
            else:
                score -= 1
                reasons.append("SPY < 50DMA")
        if lv.get("sma200") is not None:
            score += 1 if lv["last"] >= lv["sma200"] else -1
            reasons.append("> 200DMA" if lv["last"] >= lv["sma200"] else "< 200DMA")
    if vix is not None:
        if vix < 18:
            score += 1
            reasons.append(f"VIX calm ({vix})")
        elif vix > 25:
            score -= 1
            reasons.append(f"VIX elevated ({vix})")
    if breadth_pct is not None:
        if breadth_pct >= 55:
            score += 1
            reasons.append(f"breadth {breadth_pct:.0f}% green")
        elif breadth_pct <= 45:
            score -= 1
            reasons.append(f"breadth weak ({breadth_pct:.0f}%)")

    label = "risk-on" if score >= 2 else "risk-off" if score <= -1 else "neutral"
    return {"label": label, "score": score, "reason": "; ".join(reasons) or "insufficient data"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="JSON: {series:{T:[closes]}, vix, breadth_pct}")
    args = ap.parse_args()
    data = json.loads(open(args.data, encoding="utf-8").read())
    series = data.get("series", {})
    out = {
        "key_levels": build_levels(series),
        "risk_regime": risk_regime(
            spy_closes=series.get("SPY") or series.get("spy"),
            vix=data.get("vix"),
            breadth_pct=data.get("breadth_pct"),
        ),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
