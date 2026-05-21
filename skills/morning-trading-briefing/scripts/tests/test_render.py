"""Tests for render_brief.py.

Run: python3 -m pytest skills/morning-trading-briefing/scripts/tests/
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent
EXAMPLES = SCRIPTS / "examples"


def _render(json_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "render_brief.py"), "--input", str(json_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_morning_sample_renders():
    md = _render(EXAMPLES / "sample_morning.json")
    assert "# Morning Brief" in md
    assert "Must-read today" in md
    assert "Consumer Price Index" in md
    assert "ECB Interest Rate Decision" in md
    assert "Stop-loss alerts" in md
    assert "Scanner-bullish top 3" in md


def test_afternoon_sample_renders():
    md = _render(EXAMPLES / "sample_afternoon.json")
    assert "# Afternoon Brief" in md
    assert "Today's recap" in md
    assert "Overnight risks" in md
    assert "Tomorrow's setup" in md
    assert "Initial Jobless Claims" in md


def test_empty_sections_dont_crash():
    """A minimal brief with missing optional sections should still render."""
    minimal = {
        "mode": "morning",
        "date": "2026-01-15",
        "generated_at_et": "2026-01-15 07:00 ET",
        "snapshot": {"spy": "475", "spy_premarket": "+0.1%"},
        "must_read": ["Slow news day."],
    }
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(minimal, f)
        path = f.name
    md = _render(path)
    assert "# Morning Brief" in md
    assert "Slow news day" in md


def test_stdin_mode():
    sample = (EXAMPLES / "sample_morning.json").read_text()
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "render_brief.py"), "--stdin"],
        input=sample,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "# Morning Brief" in r.stdout
