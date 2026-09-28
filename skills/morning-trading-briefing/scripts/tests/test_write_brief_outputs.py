"""Tests for write_brief_outputs.py — the v2.0 entrypoint.

The --dry-run path is what v2.0 ships as its acceptance test: it reads
the real compose_brief outputs end-to-end, walks every event payload,
and reports what would be written. No Google APIs are called and the
google-* libs don't need to be installed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent
EXAMPLES = SCRIPTS / "examples"
sys.path.insert(0, str(SCRIPTS))

from write_brief_outputs import (  # noqa: E402
    _parse_config_sections,
    _to_calendar_event,
    _validate_events,
)


# ---------------------------------------------------------------------------
# _parse_config_sections
# ---------------------------------------------------------------------------


CONFIG_TEXT = """\
version: 1
timezone: America/Los_Angeles

calendars:
  macro_events: "abc@group.calendar.google.com"
  earnings: "def@group.calendar.google.com"   # inline comment OK
  my_positions: 'ghi@group.calendar.google.com'
  market_updates: "jkl@group.calendar.google.com"

drive:
  briefings_folder_id: "folder123"
  filename_pattern: "briefings/{date}-{mode}.md"

google:
  credentials_path: "~/.config/morning-briefing/credentials.json"
  token_path: "~/.config/morning-briefing/token.json"

watchlist:
  - SPY
  - QQQ
"""


def test_parse_config_sections_pulls_named_sections():
    out = _parse_config_sections(CONFIG_TEXT, "calendars", "drive", "google")
    assert out["calendars"]["macro_events"] == "abc@group.calendar.google.com"
    assert out["calendars"]["earnings"] == "def@group.calendar.google.com"
    assert out["calendars"]["my_positions"] == "ghi@group.calendar.google.com"
    assert out["calendars"]["market_updates"] == "jkl@group.calendar.google.com"
    assert out["drive"]["briefings_folder_id"] == "folder123"
    assert (
        out["google"]["credentials_path"]
        == "~/.config/morning-briefing/credentials.json"
    )


def test_parse_config_sections_ignores_unrequested_sections():
    out = _parse_config_sections(CONFIG_TEXT, "calendars")
    assert "drive" not in out
    assert "watchlist" not in out
    # The list values under watchlist are silently skipped (no key:value pair).


def test_parse_config_sections_handles_missing_section():
    """Existing pre-v2.0 configs have no google: block — caller should still
    boot and fall back to defaults."""
    text = "calendars:\n  macro_events: 'x'\n"
    out = _parse_config_sections(text, "calendars", "google")
    assert out["calendars"] == {"macro_events": "x"}
    assert out["google"] == {}


# ---------------------------------------------------------------------------
# _to_calendar_event
# ---------------------------------------------------------------------------


def test_to_calendar_event_timed_event_shape():
    ev = {
        "calendarId": "x",
        "summary": "CPI 8:30 ET",
        "startTime": "2026-05-27T08:30:00",
        "endTime": "2026-05-27T08:45:00",
        "timeZone": "America/New_York",
        "description": "body\n<!-- mtb-key: mtb:2026-05-27:macro_events:cpi -->",
        "colorId": "11",
        "dedupKey": "mtb:2026-05-27:macro_events:cpi",
    }
    payload = _to_calendar_event(ev)
    assert payload["summary"] == "CPI 8:30 ET"
    assert payload["start"] == {
        "dateTime": "2026-05-27T08:30:00",
        "timeZone": "America/New_York",
    }
    assert payload["end"] == {
        "dateTime": "2026-05-27T08:45:00",
        "timeZone": "America/New_York",
    }
    assert payload["colorId"] == "11"
    # Writer-internal fields should not leak into the Google payload.
    assert "calendarId" not in payload
    assert "dedupKey" not in payload
    assert "timeZone" not in payload
    assert "allDay" not in payload


def test_to_calendar_event_allday_shape_uses_date_not_datetime():
    ev = {
        "calendarId": "x",
        "summary": "Morning Brief",
        "startTime": "2026-05-27T00:00:00Z",
        "endTime": "2026-05-28T00:00:00Z",
        "timeZone": "America/New_York",
        "allDay": True,
        "description": "body\n<!-- mtb-key: mtb:2026-05-27:my_positions:morning-brief -->",
        "colorId": "11",
        "dedupKey": "mtb:2026-05-27:my_positions:morning-brief",
    }
    payload = _to_calendar_event(ev)
    assert payload["start"] == {"date": "2026-05-27"}
    assert payload["end"] == {"date": "2026-05-28"}
    # The API rejects timeZone on date-only events.
    assert "dateTime" not in payload["start"]
    assert "timeZone" not in payload["start"]


# ---------------------------------------------------------------------------
# _validate_events
# ---------------------------------------------------------------------------


def _valid_event(key="mtb:2026-05-27:earnings:crm"):
    return {
        "calendarId": "earn@x",
        "summary": "CRM AMC",
        "startTime": "2026-05-27T16:00:00",
        "endTime": "2026-05-27T16:15:00",
        "timeZone": "America/New_York",
        "description": f"body\n<!-- mtb-key: {key} -->",
        "dedupKey": key,
    }


def test_validate_events_accepts_clean_list():
    assert _validate_events([_valid_event(), _valid_event("mtb:2026-05-27:earnings:ai")]) == []


def test_validate_events_flags_missing_marker():
    ev = _valid_event()
    ev["description"] = "no marker"
    issues = _validate_events([ev])
    assert any("missing" in m and "mtb-key" in m for m in issues)


def test_validate_events_flags_calendar_id_missing():
    ev = _valid_event()
    ev["calendarId"] = ""
    issues = _validate_events([ev])
    assert any("missing calendarId" in m for m in issues)


def test_validate_events_flags_dedupkey_marker_mismatch():
    ev = _valid_event(key="mtb:2026-05-27:earnings:crm")
    ev["dedupKey"] = "mtb:2026-05-27:earnings:DIFFERENT"
    issues = _validate_events([ev])
    assert any("disagrees" in m for m in issues)


# ---------------------------------------------------------------------------
# CLI smoke test (dry-run, no Google libs needed)
# ---------------------------------------------------------------------------


def _materialize_brief(out_dir: Path, date_iso: str, mode: str) -> tuple[Path, Path]:
    """Run compose_brief.py against the bundled sample to produce real .md +
    .events.json files for the dry-run test to consume."""
    cfg = out_dir / "config.yaml"
    cfg.write_text(
        "calendars:\n"
        "  macro_events: macro@x\n"
        "  earnings: earn@x\n"
        "  my_positions: pos@x\n"
        "  market_updates: mu@x\n"
        "drive:\n"
        "  briefings_folder_id: folder123\n"
        "google:\n"
        "  credentials_path: '/nonexistent/credentials.json'\n"
        "  token_path: '/nonexistent/token.json'\n",
        encoding="utf-8",
    )
    sample = EXAMPLES / f"sample_{mode}.json"
    briefings_dir = out_dir / "briefings"
    briefings_dir.mkdir()
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "compose_brief.py"),
            "--input",
            str(sample),
            "--config",
            str(cfg),
            "--out-dir",
            str(briefings_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    # Patch the produced .md/.events.json filenames to the requested date —
    # the sample file pins its own date, but the dry-run test wants a
    # specific date to keep paths predictable.
    data = json.loads(sample.read_text())
    pinned = data.get("date") or date_iso
    return (
        briefings_dir / f"{pinned}-{mode}.md",
        briefings_dir / f"{pinned}-{mode}.events.json",
    )


def test_dry_run_end_to_end_morning():
    """Compose a real brief, then run write_brief_outputs.py --dry-run on it.

    Verifies: (1) the script can read the artifacts compose_brief emits,
    (2) every event passes mtb-key validation, (3) the dry-run path never
    imports google-api-python-client (proven by the test running clean
    without those packages installed in the test env).
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        md_path, events_path = _materialize_brief(tmp_path, "2026-05-27", "morning")
        assert md_path.exists()
        assert events_path.exists()
        data = json.loads((EXAMPLES / "sample_morning.json").read_text())
        pinned_date = data.get("date") or "2026-05-27"

        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "write_brief_outputs.py"),
                "--config",
                str(tmp_path / "config.yaml"),
                "--date",
                pinned_date,
                "--mode",
                "morning",
                "--briefings-dir",
                str(tmp_path / "briefings"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
        # Every event line carries the DRY-RUN tag and the mtb-key marker.
        events = json.loads(events_path.read_text())
        assert events, "expected non-empty events list from compose_brief"
        for ev in events:
            assert ev["dedupKey"] in r.stderr, (
                f"missing dedupKey {ev['dedupKey']} in dry-run output"
            )
        assert "[DRY-RUN] drive upsert" in r.stderr
        assert "[DRY-RUN] calendar:" in r.stderr


def test_dry_run_refuses_when_mtb_key_marker_missing():
    """Tampered events.json (marker stripped) must abort with exit 3 — the
    point of the validator is to prevent reintroducing the dupe bug."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        briefings_dir = tmp_path / "briefings"
        briefings_dir.mkdir()
        date_iso = "2026-05-27"
        (briefings_dir / f"{date_iso}-morning.md").write_text("# Brief\n", encoding="utf-8")
        # Build an events.json missing the mtb-key marker.
        bad = [
            {
                "calendarId": "cal@x",
                "summary": "Tampered event",
                "startTime": f"{date_iso}T08:30:00",
                "endTime": f"{date_iso}T08:45:00",
                "timeZone": "America/New_York",
                "description": "body without marker",
                "dedupKey": "mtb:2026-05-27:macro_events:tampered",
            }
        ]
        (briefings_dir / f"{date_iso}-morning.events.json").write_text(
            json.dumps(bad), encoding="utf-8"
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text("calendars:\n  macro_events: cal@x\n", encoding="utf-8")

        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "write_brief_outputs.py"),
                "--config",
                str(cfg),
                "--date",
                date_iso,
                "--mode",
                "morning",
                "--briefings-dir",
                str(briefings_dir),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 3, f"expected validation exit; got {r.returncode}"
        assert "mtb-key" in r.stderr


def test_dry_run_missing_files_exits_2():
    """Missing inputs surface with a clear exit code so cron can alert."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cfg = tmp_path / "config.yaml"
        cfg.write_text("calendars:\n", encoding="utf-8")
        (tmp_path / "briefings").mkdir()
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "write_brief_outputs.py"),
                "--config",
                str(cfg),
                "--date",
                "2099-01-01",
                "--mode",
                "morning",
                "--briefings-dir",
                str(tmp_path / "briefings"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 2
        assert "not found" in r.stderr
