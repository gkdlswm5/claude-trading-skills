#!/usr/bin/env python3
"""Generate BI trend charts (PNG) for the morning brief.

Calendar event bodies are text-only, so PNGs are for the markdown + Drive archive
(sparklines cover the calendar). Reads a series JSON, writes one PNG per group
plus a manifest the orchestrator uses to upload + reference the images.

Input (--data series.json):
    {
      "date": "YYYY-MM-DD",
      "series": {
        "SPY":   {"group": "indices",     "points": [{"date": "...", "close": 1.0}, ...]},
        "US10Y": {"group": "rates",        "points": [...]},
        "WTI":   {"group": "commodities",  "points": [...]}
      },
      "sectors": {"XLK": 3.66, "XLE": -2.16, ...}   // optional, single-value bars
    }

Usage:
    generate_charts.py --data series.json --out-dir briefings/charts/2026-05-27/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — required for unattended/scheduled runs
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

GROUP_TITLES = {
    "indices": "Index trend (rebased = 100)",
    "rates": "Rates (%)",
    "commodities": "Commodities (rebased = 100)",
}
NORMALIZE = {"indices": True, "commodities": True, "rates": False}


def _series_df(members: dict) -> pd.DataFrame:
    cols = {}
    for name, pts in members.items():
        if pts:
            cols[name] = pd.Series({p["date"]: float(p["close"]) for p in pts})
    return pd.DataFrame(cols).sort_index() if cols else pd.DataFrame()


def build_charts(data: dict, out_dir: Path) -> list[dict]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    date = data.get("date", "")
    manifest: list[dict] = []

    groups: dict[str, dict] = {}
    for name, spec in data.get("series", {}).items():
        groups.setdefault(spec.get("group", "misc"), {})[name] = spec.get("points", [])

    for group, members in groups.items():
        df = _series_df(members)
        if df.empty:
            continue
        if NORMALIZE.get(group):
            df = df / df.iloc[0] * 100.0
        fig, ax = plt.subplots(figsize=(6, 3))
        for col in df.columns:
            ax.plot(range(len(df)), df[col], label=col, linewidth=1.5)
        ax.set_title(GROUP_TITLES.get(group, group))
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        ax.set_xticks([0, len(df) - 1])
        ax.set_xticklabels([str(df.index[0]), str(df.index[-1])], fontsize=7)
        path = out_dir / f"{date}_{group}.png"
        fig.savefig(path, dpi=90, bbox_inches="tight")
        plt.close(fig)
        manifest.append({"group": group, "title": GROUP_TITLES.get(group, group), "path": str(path)})

    sectors = data.get("sectors")
    if sectors:
        items = sorted(sectors.items(), key=lambda kv: kv[1])
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.barh(
            [k for k, _ in items],
            [v for _, v in items],
            color=["#c0392b" if v < 0 else "#27ae60" for _, v in items],
        )
        ax.set_title("Sector performance (%)")
        ax.grid(alpha=0.3, axis="x")
        path = out_dir / f"{date}_sectors.png"
        fig.savefig(path, dpi=90, bbox_inches="tight")
        plt.close(fig)
        manifest.append({"group": "sectors", "title": "Sector performance", "path": str(path)})

    (out_dir / "charts_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True, help="series JSON")
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    manifest = build_charts(data, args.out_dir)
    print(f"Wrote {len(manifest)} chart(s) to {args.out_dir}", file=sys.stderr)
    for m in manifest:
        print(m["path"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
