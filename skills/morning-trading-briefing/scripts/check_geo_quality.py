#!/usr/bin/env python3
"""Validate the geopolitical_summary wrap against the anti-bias contract.

Thin named wrapper around check_news_quality.py for the geopolitical section.
Enforces references/NEWS_QUALITY.md: banned emotive lexicon, unattributed
quantified claims, prediction language, and single-source markers.

Usage:
    check_geo_quality.py --text "CONFIRMED ECB held ... — EUR/USD +0.4%" [--json]
    check_geo_quality.py --file geo_text.txt [--json]

Exit code 1 on any hard fail (caller must omit the geo block), 0 otherwise.
"""
import sys
from pathlib import Path

# Reuse the shared quality checker — same contract, geo-specific name.
sys.path.insert(0, str(Path(__file__).parent))
from check_news_quality import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
