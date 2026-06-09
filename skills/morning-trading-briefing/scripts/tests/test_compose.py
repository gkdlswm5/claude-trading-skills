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
            "  market_updates: mu@x.com\n"
        )
        cfg = f.name
    out = _compose(EXAMPLES / "sample_morning.json", config=cfg)
    events = json.loads(next(out.glob("*.events.json")).read_text())
    cals = {e["calendarId"] for e in events}
    assert cals == {"macro@x.com", "earn@x.com", "pos@x.com", "mu@x.com"}

    # Earnings is now ONE ranked all-day digest, not per-company events.
    earn_events = [e for e in events if e["calendarId"] == "earn@x.com"]
    assert len(earn_events) == 1
    digest = earn_events[0]
    assert digest.get("allDay") is True
    assert "Earnings —" in digest["summary"]
    # NVDA (in both megacaps + my_positions) appears once, with position detail.
    assert digest["description"].count("NVDA") == 1
    assert "exposure:" in digest["description"]


def test_market_updates_digest():
    """market_updates calendar gets exactly one all-day digest event with the
    snapshot + must-reads bundled into the body."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("calendars:\n  market_updates: mu@x.com\n")
        cfg = f.name
    out = _compose(EXAMPLES / "sample_morning.json", config=cfg)
    events = json.loads(next(out.glob("*.events.json")).read_text())
    mu = [e for e in events if e["calendarId"] == "mu@x.com"]
    assert len(mu) == 1
    ev = mu[0]
    # v2.2: title is "Market Updates" plus the snapshot stamp.
    assert ev["summary"].startswith("Market Updates")
    assert "(as of 07:00 ET)" in ev["summary"]
    assert ev["allDay"] is True
    assert ev["startTime"].endswith("T00:00:00Z")
    assert "# Market Updates" in ev["description"]
    assert "Snapshot:" in ev["description"]


def test_market_updates_skipped_without_id():
    """No market_updates key → no digest event (3-calendar config unaffected)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("calendars:\n  macro_events: macro@x.com\n")
        cfg = f.name
    out = _compose(EXAMPLES / "sample_morning.json", config=cfg)
    events = json.loads(next(out.glob("*.events.json")).read_text())
    assert all(e["summary"] != "Market Updates" for e in events)


def test_afternoon_compose():
    out = _compose(EXAMPLES / "sample_afternoon.json", dry_run=True)
    md = next(out.glob("*afternoon.md")).read_text()
    assert "# Afternoon Brief" in md
    assert "Tomorrow's setup" in md


# --------------------------------------------------------------------------- #
# v2.2 — snapshot stamp on all-day event titles
# --------------------------------------------------------------------------- #
def _full_cfg():
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(
        "calendars:\n"
        "  macro_events: macro@x.com\n"
        "  earnings: earn@x.com\n"
        "  my_positions: pos@x.com\n"
        "  market_updates: mu@x.com\n"
    )
    f.close()
    return f.name


def test_allday_titles_carry_as_of_stamp():
    """All-day event titles get '(as of HH:MM ET)' from generated_at_et."""
    out = _compose(EXAMPLES / "sample_morning.json", config=_full_cfg())
    events = json.loads(next(out.glob("*.events.json")).read_text())
    allday = [e for e in events if e.get("allDay")]
    assert allday, "expected at least one all-day event"
    for e in allday:
        assert "(as of 07:00 ET)" in e["summary"], e["summary"]


def test_timed_events_have_no_as_of_stamp():
    """Timed macro events should NOT get the all-day snapshot stamp."""
    out = _compose(EXAMPLES / "sample_morning.json", config=_full_cfg())
    events = json.loads(next(out.glob("*.events.json")).read_text())
    timed = [e for e in events if not e.get("allDay")]
    for e in timed:
        assert "(as of" not in e["summary"], e["summary"]


def test_as_of_stamp_does_not_change_dedup_key():
    """The stamp must not leak into the dedup key — else re-runs duplicate.

    The key is built from the original summary and _slug() strips parens, so
    'Morning Brief' and 'Morning Brief (as of 07:00 ET)' map to the same key.
    """
    out = _compose(EXAMPLES / "sample_morning.json", config=_full_cfg())
    events = json.loads(next(out.glob("*.events.json")).read_text())
    pos = [e for e in events if e["calendarId"] == "pos@x.com"][0]
    assert "(as of 07:00 ET)" in pos["summary"]
    # Key is the bare slug, no timestamp digits from the stamp.
    assert pos["dedupKey"] == "mtb:2026-05-21:my_positions:morning-brief"


# --------------------------------------------------------------------------- #
# v2.3 — earnings cap + tier-3, in-process via build_calendar_events
# --------------------------------------------------------------------------- #
def _bce():
    sys.path.insert(0, str(SCRIPTS))
    from compose_brief import build_calendar_events

    return build_calendar_events


def test_earnings_digest_capped_to_max():
    build = _bce()
    megacaps = [
        {"ticker": f"T{i}", "timing": "BMO", "implied_move": "5", "market_cap": f"{i}B"}
        for i in range(1, 13)  # 12 names
    ]
    data = {
        "mode": "morning",
        "date": "2026-05-27",
        "earnings_today": {"megacaps": megacaps, "my_positions": []},
        "filters": {"max_earnings": 8},
    }
    events = build(data, {"earnings": "earn@x.com"})
    digest = [e for e in events if e["calendarId"] == "earn@x.com"][0]
    # 12 reporting, capped to 8 → summary + footer reflect the cap.
    assert "top 8 of 12" in digest["summary"]
    assert "Top 8 of 12 reporting" in digest["description"]
    # Exactly 8 numbered entry lines (lines like "1. T9 (BMO) — ...").
    import re as _re

    numbered = [
        ln for ln in digest["description"].splitlines() if _re.match(r"\d+\.\s", ln.strip())
    ]
    assert len(numbered) == 8


def test_earnings_cap_disabled_with_zero():
    build = _bce()
    megacaps = [
        {"ticker": f"T{i}", "timing": "BMO", "implied_move": "5", "market_cap": f"{i}B"}
        for i in range(1, 13)
    ]
    data = {
        "mode": "morning",
        "date": "2026-05-27",
        "earnings_today": {"megacaps": megacaps, "my_positions": []},
        "filters": {"max_earnings": 0},
    }
    events = build(data, {"earnings": "earn@x.com"})
    digest = [e for e in events if e["calendarId"] == "earn@x.com"][0]
    assert "12 reporting" in digest["summary"]
    assert "top" not in digest["summary"].lower()


def test_tier3_off_drops_low_impact_macro():
    build = _bce()
    data = {
        "mode": "morning",
        "date": "2026-05-27",
        "econ_releases": [
            {"name": "CPI", "impact": "High", "time_et": "08:30"},
            {"name": "Dallas Fed Services", "impact": "Low", "time_et": "10:30"},
        ],
        "filters": {"drop_minor_econ": False, "include_tier3": False},
    }
    events = build(data, {"macro_events": "macro@x.com"})
    names = [e["summary"] for e in events if e["calendarId"] == "macro@x.com"]
    assert any("CPI" in n for n in names)
    assert not any("Dallas Fed" in n for n in names)


def test_no_generated_at_means_no_stamp():
    """If generated_at_et is absent, titles stay clean (graceful degrade)."""
    data = json.loads((EXAMPLES / "sample_morning.json").read_text())
    data.pop("generated_at_et", None)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, tmp)
    tmp.close()
    out = _compose(Path(tmp.name), config=_full_cfg())
    events = json.loads(next(out.glob("*.events.json")).read_text())
    for e in events:
        assert "(as of" not in e["summary"], e["summary"]
