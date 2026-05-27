#!/usr/bin/env python3
"""Validate the geopolitical wrap against the anti-bias contract.

Enforces the mechanical parts of references/GEO_WRAP_QUALITY.md:
  - HARD FAIL: banned emotive/judgment lexicon present
  - HARD FAIL: a quantified market claim (%/$/bps) with no allowlisted source
  - WARN: prediction language (will, likely, expect, target, ...)
  - WARN: unconfirmed / reportedly / rumored single-source markers

Usage:
    check_geo_quality.py --text "CONFIRMED ECB held ... — EUR/USD +0.4%"
    check_geo_quality.py --file geo.txt [--json]

Exit code 1 on any hard fail (caller should omit the geo block), 0 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# Emotive / judgment words that smuggle in framing bias. Direction + magnitude
# only; these are never acceptable in a factual wrap.
BANNED_LEXICON = [
    "soared", "soar", "plunged", "plunge", "plummeted", "plummet", "skyrocketed",
    "skyrocket", "tanked", "crushed", "slammed", "cratered", "collapsed", "collapse",
    "exploded", "panic", "fears", "fear", "chaos", "carnage", "bloodbath",
    "meltdown", "routed", "rout", "devastating", "stunning", "shocking", "massive",
    "frenzy", "turmoil",
]

# Forward-looking language — predictions are where opinion masquerades as fact.
PREDICTION_TERMS = [
    "will likely", "likely to", "expected to", "expect ", "poised to", "set to surge",
    "set to fall", "headed to", "heading to", "target ", "forecast", "we think",
    "we expect", "projected to", "should rise", "should fall",
]

# Single-source hedges → corroboration not met.
UNCONFIRMED_MARKERS = ["unconfirmed", "reportedly", "rumored", "rumour", "sources say"]

# Allowlisted source tokens (Tier-1 + primary). Lowercased substring match.
SOURCE_ALLOWLIST = [
    "reuters", "associated press", "ap)", "ap,", "(ap", "bloomberg",
    "financial times", "ft)", "ft,", "(ft", "wall street journal", "wsj",
    "federal reserve", "fed)", "fed,", "(fed", "ecb", "boj", "pboc",
    "bank of england", "boe", "sec", "eia", "opec", "treasury", "white house",
]

# A clause carries a quantified market claim if it has a %, $ figure, or bps.
_QUANT = re.compile(r"(?<![\w])([+-]?\d+(?:\.\d+)?\s?%|\$\s?\d|\d+\s?bps|\d+\s?bp\b)")


def _split_items(text: str) -> list[str]:
    """Split the wrap into claim units: bullets/lines, then sentences."""
    raw = re.split(r"[\n\r]+|(?<=[.!])\s+(?=[A-Z(])", text)
    return [seg.strip(" -•*\t") for seg in raw if seg.strip(" -•*\t")]


def _has_source(segment: str) -> bool:
    low = segment.lower()
    return any(tok in low for tok in SOURCE_ALLOWLIST)


def check_geo_quality(text: str) -> dict:
    text = text or ""
    low = text.lower()
    hard_fails: list[str] = []
    warnings: list[str] = []

    found_banned = sorted({w for w in BANNED_LEXICON if re.search(rf"\b{re.escape(w)}\b", low)})
    for w in found_banned:
        hard_fails.append(f"banned lexicon: '{w}' — use direction + magnitude only")

    for seg in _split_items(text):
        if _QUANT.search(seg) and not _has_source(seg):
            hard_fails.append(f"quantified claim without allowlisted source: '{seg[:80]}'")

    for term in PREDICTION_TERMS:
        if term in low:
            warnings.append(f"prediction language: '{term.strip()}' — geo wrap states facts, not forecasts")
    for m in UNCONFIRMED_MARKERS:
        if m in low:
            warnings.append(f"single-source marker: '{m}' — require >=2 Tier-1 corroboration")

    return {
        "passed": not hard_fails,
        "hard_fails": hard_fails,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="geopolitical_summary text to validate")
    g.add_argument("--file", help="path to a file containing the text")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    text = args.text if args.text is not None else open(args.file, encoding="utf-8").read()
    result = check_geo_quality(text)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("PASS" if result["passed"] else "FAIL")
        for f in result["hard_fails"]:
            print(f"  [hard] {f}")
        for w in result["warnings"]:
            print(f"  [warn] {w}")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
