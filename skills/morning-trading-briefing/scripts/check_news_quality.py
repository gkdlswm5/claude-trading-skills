#!/usr/bin/env python3
"""Validate any sourced-news wrap against the anti-bias contract.

Applies to every WebSearch-sourced field in the brief — geopolitical_summary,
rates_news, commodities_news. Enforces the mechanical parts of
references/NEWS_QUALITY.md:
  - HARD FAIL: banned emotive/judgment lexicon present
  - HARD FAIL: a quantified market claim (%/$/bps) with no allowlisted source
  - WARN: prediction language (will, likely, expect, target, ...)
  - WARN: unconfirmed / reportedly / rumored single-source markers

Usage:
    check_news_quality.py --text "CONFIRMED ECB held ... — EUR/USD +0.4%"
    check_news_quality.py --file news.txt [--json]

Exit code 1 on any hard fail (caller should omit the wrap), 0 otherwise.
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

# Allowlisted source names (Tier-1 + primary), matched as whole words.
SOURCE_ALLOWLIST = [
    "reuters", "associated press", "ap", "bloomberg", "financial times", "ft",
    "wall street journal", "wsj", "federal reserve", "fed", "ecb", "boj", "pboc",
    "bank of england", "boe", "sec", "eia", "opec", "us treasury", "treasury",
    "white house",
]

# Attribution must sit in a citation position, not merely be mentioned. We accept
# a source inside parentheses — "(Reuters, Bloomberg)" — or right after a cue word.
# This stops a market actor that is also a source ("OPEC+ cut crude +4%") from
# being mistaken for a citation.
_PAREN = re.compile(r"\(([^)]*)\)")
ATTRIB_CUES = ["per ", "via ", "according to ", "reported by ", "cited ", "said "]

# A clause carries a quantified market claim if it has a %, $ figure, or bps.
_QUANT = re.compile(r"(?<![\w])([+-]?\d+(?:\.\d+)?\s?%|\$\s?\d|\d+\s?bps|\d+\s?bp\b)")


def _split_items(text: str) -> list[str]:
    """Split the wrap into claim units: bullets/lines, then sentences."""
    raw = re.split(r"[\n\r]+|(?<=[.!])\s+(?=[A-Z(])", text)
    return [seg.strip(" -•*\t") for seg in raw if seg.strip(" -•*\t")]


def _src_in(text: str) -> bool:
    return any(re.search(rf"\b{re.escape(tok)}\b", text) for tok in SOURCE_ALLOWLIST)


def _has_source(segment: str) -> bool:
    """True only if an allowlisted source appears in a citation position:
    inside parentheses, or within ~60 chars after an attribution cue word."""
    low = segment.lower()
    if any(_src_in(inside) for inside in _PAREN.findall(low)):
        return True
    for cue in ATTRIB_CUES:
        i = low.find(cue)
        if i != -1 and _src_in(low[i : i + 60]):
            return True
    return False


def check_news_quality(text: str) -> dict:
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
    result = check_news_quality(text)

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
