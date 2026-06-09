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


# --------------------------------------------------------------------------- #
# v2.2 — "Snapshot as of" header + good/bad emoji signals
# In-process render() (not subprocess) so non-ASCII emoji don't hit the
# Windows cp1252 stdout-encoding wall.
# --------------------------------------------------------------------------- #
def _render_inproc(json_path):
    sys.path.insert(0, str(SCRIPTS))
    from render_brief import render

    return render(json.loads(Path(json_path).read_text(encoding="utf-8")))


def test_morning_header_uses_snapshot_as_of():
    md = _render_inproc(EXAMPLES / "sample_morning.json")
    assert "Snapshot as of 07:00 ET" in md
    assert "Generated " not in md  # old label replaced


def test_afternoon_header_uses_snapshot_as_of():
    md = _render_inproc(EXAMPLES / "sample_afternoon.json")
    assert "Snapshot as of" in md


def test_morning_premarket_change_gets_signal():
    from signals import BAD, GOOD

    md = _render_inproc(EXAMPLES / "sample_morning.json")
    # spy_premarket carries a signed change → should be tagged green or red.
    assert (GOOD in md) or (BAD in md)


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
