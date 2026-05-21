"""Tests for check_alerts.py."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent
EXAMPLES = SCRIPTS / "examples"
CONFIG = SCRIPTS.parent / "config.example.yaml"


def _run(positions_json, earnings_json=None, today=None):
    args = [
        sys.executable,
        str(SCRIPTS / "check_alerts.py"),
        "--positions",
        str(positions_json),
        "--config",
        str(CONFIG),
    ]
    if earnings_json:
        args.extend(["--earnings", str(earnings_json)])
    if today:
        args.extend(["--today", today])
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_stop_alerts_triggers_near():
    """TLT at 89 with stop at 87.50 = 1.7% above stop → within 3% threshold."""
    out = _run(EXAMPLES / "sample_positions.json")
    tickers = [a["ticker"] for a in out["stop_alerts"]]
    assert "TLT" in tickers


def test_stop_alerts_ignores_safe():
    """AAPL at 224 with stop at 200 = 12% above stop → no alert."""
    out = _run(EXAMPLES / "sample_positions.json")
    tickers = [a["ticker"] for a in out["stop_alerts"]]
    assert "AAPL" not in tickers


def test_short_leg_delta_breach():
    """NVDA 145C has delta 0.42 > 0.35 threshold."""
    out = _run(EXAMPLES / "sample_positions.json")
    symbols = [a["symbol"] for a in out["short_leg_alerts"]]
    assert any("NVDA" in s for s in symbols)


def test_short_leg_safe_skipped():
    """XOM 130P has delta 0.18 < 0.35 AND DTE 60 > 14 → no alert."""
    out = _run(EXAMPLES / "sample_positions.json")
    symbols = [a["symbol"] for a in out["short_leg_alerts"]]
    assert not any("XOM" in s for s in symbols)


def test_upcoming_earnings_matches_underlying():
    """NVDA earnings tomorrow should match NVDA option positions via underlying extraction."""
    out = _run(
        EXAMPLES / "sample_positions.json",
        EXAMPLES / "sample_earnings.json",
        today="2026-05-20",
    )
    tickers = [e["ticker"] for e in out["upcoming_earnings"]]
    assert "NVDA" in tickers


def test_earnings_outside_window():
    """AAPL earnings 2026-07-30, today 2026-05-20 → 71 days out, outside 7-day window."""
    out = _run(
        EXAMPLES / "sample_positions.json",
        EXAMPLES / "sample_earnings.json",
        today="2026-05-20",
    )
    tickers = [e["ticker"] for e in out["upcoming_earnings"]]
    assert "AAPL" not in tickers


def test_breached_stop_flagged():
    """Position where stop is already breached should get BREACHED message."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            [{"ticker": "ZZZ", "asset_type": "stock", "last_price": 95, "stop_price": 100}],
            f,
        )
        path = f.name
    out = _run(path)
    assert len(out["stop_alerts"]) == 1
    assert "BREACHED" in out["stop_alerts"][0]["action"]
