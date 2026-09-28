"""Tests for generate_charts.py — headless PNG generation."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_charts import build_charts  # noqa: E402

_DATA = {
    "date": "2026-05-27",
    "series": {
        "SPY": {"group": "indices", "points": [{"date": "d1", "close": 100}, {"date": "d2", "close": 102}, {"date": "d3", "close": 101}]},
        "QQQ": {"group": "indices", "points": [{"date": "d1", "close": 200}, {"date": "d2", "close": 210}, {"date": "d3", "close": 205}]},
        "US10Y": {"group": "rates", "points": [{"date": "d1", "close": 4.40}, {"date": "d2", "close": 4.45}, {"date": "d3", "close": 4.49}]},
    },
    "sectors": {"XLK": 3.66, "XLE": -2.16, "XLF": 0.23},
}


def test_build_charts_creates_pngs_and_manifest():
    out = Path(tempfile.mkdtemp())
    manifest = build_charts(_DATA, out)
    groups = {m["group"] for m in manifest}
    assert {"indices", "rates", "sectors"} <= groups
    for m in manifest:
        p = Path(m["path"])
        assert p.exists() and p.suffix == ".png" and p.stat().st_size > 0
    assert (out / "charts_manifest.json").exists()
    saved = json.loads((out / "charts_manifest.json").read_text())
    assert len(saved) == len(manifest)


def test_empty_series_no_crash():
    out = Path(tempfile.mkdtemp())
    manifest = build_charts({"date": "2026-05-27", "series": {}}, out)
    assert manifest == []
    assert (out / "charts_manifest.json").exists()
