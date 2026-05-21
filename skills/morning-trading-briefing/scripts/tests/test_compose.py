"""Tests for compose_brief.py end-to-end."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent
EXAMPLES = SCRIPTS / "examples"


def _compose(input_json, config=None, dry_run=False):
    out_dir = tempfile.mkdtemp()
    args = [
        sys.executable,
        str(SCRIPTS / "compose_brief.py"),
        "--input",
        str(input_json),
        "--out-dir",
        out_dir,
    ]
    if config:
        args.extend(["--config", str(config)])
    if dry_run:
        args.append("--dry-run")
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return Path(out_dir)


def test_dry_run_writes_markdown_only():
    out = _compose(EXAMPLES / "sample_morning.json", dry_run=True)
    files = list(out.iterdir())
    assert any(f.suffix == ".md" for f in files)
    assert not any(f.name.endswith(".events.json") for f in files)


def test_empty_config_no_events():
    """When config has no calendar IDs, events.json is empty list (won't trigger writes)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("# empty config\n")
        cfg = f.name
    out = _compose(EXAMPLES / "sample_morning.json", config=cfg)
    events = json.loads(next(out.glob("*.events.json")).read_text())
    assert events == []


def test_full_config_generates_events():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(
            "calendars:\n"
            "  macro_events: macro@x.com\n"
            "  earnings: earn@x.com\n"
            "  my_positions: pos@x.com\n"
        )
        cfg = f.name
    out = _compose(EXAMPLES / "sample_morning.json", config=cfg)
    events = json.loads(next(out.glob("*.events.json")).read_text())
    cals = {e["calendarId"] for e in events}
    assert cals == {"macro@x.com", "earn@x.com", "pos@x.com"}

    # Confirm dedup: NVDA appears in megacaps AND my_positions but only one event.
    nvda_events = [e for e in events if "NVDA" in e["summary"]]
    assert len(nvda_events) == 1
    # And the dedup kept the my_positions version (has "Your exposure")
    assert "Your exposure" in nvda_events[0]["description"]


def test_afternoon_compose():
    out = _compose(EXAMPLES / "sample_afternoon.json", dry_run=True)
    md = next(out.glob("*afternoon.md")).read_text()
    assert "# Afternoon Brief" in md
    assert "Tomorrow's setup" in md
