#!/usr/bin/env python3
"""Validate the geopolitical_summary field against the anti-bias contract.

Thin wrapper around check_news_quality.py scoped to the geo block.
Same contract: banned lexicon + unattributed quantified claims are hard fails;
prediction language is a warning.

Usage:
    check_geo_quality.py --text "CONFIRMED ECB held ..."
    check_geo_quality.py --file geo.txt [--json]

Exit 1 on any hard fail (caller should omit the geo block), 0 otherwise.
"""
import sys
from pathlib import Path

# Re-use the shared validator; keep this wrapper thin.
sys.path.insert(0, str(Path(__file__).parent))
from check_news_quality import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
