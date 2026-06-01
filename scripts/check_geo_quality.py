#!/usr/bin/env python3
"""Thin wrapper: run the morning-briefing news-quality gate on a geopolitical wrap.

Usage:
    check_geo_quality.py --text "Geopolitical wrap text here..."
    check_geo_quality.py --file geo.txt [--json]

Delegates entirely to
    skills/morning-trading-briefing/scripts/check_news_quality.py

Exit code 1 on any hard fail (caller should omit the geo block).
Exit code 0 on clean or warnings-only.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CHECKER = _REPO_ROOT / "skills" / "morning-trading-briefing" / "scripts" / "check_news_quality.py"


def main() -> int:
    ap = argparse.ArgumentParser(description="Geo wrap quality gate")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="Geo wrap text (inline)")
    src.add_argument("--file", help="Path to a text file containing the geo wrap")
    ap.add_argument("--json", action="store_true", help="Pass --json to the checker")
    args = ap.parse_args()

    cmd = [sys.executable, str(_CHECKER)]
    if args.text:
        cmd += ["--text", args.text]
    elif args.file:
        cmd += ["--file", args.file]
    if args.json:
        cmd.append("--json")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
