#!/usr/bin/env python3
"""Tests for write_brief_outputs.py — the v2.0 deterministic write step.

Calendar/Drive are exercised through the real client logic against in-memory
fake services (monkeypatched authenticate), so no creds/network are touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import write_brief_outputs as wbo  # noqa: E402
from tests.test_google_clients import FakeCalendarService, FakeDriveService  # noqa: E402


def _data() -> dict:
    return {
        "mode": "morning",
        "date": "2026-05-27",
        "snapshot": {"spy": "590"},
    }


def _cals() -> dict:
    return {
        "macro_events": "macro@cal",
        "earnings": "earn@cal",
        "my_positions": "pos@cal",
        "market_updates": "mu@cal",
    }


def test_dry_run_writes_local_only(tmp_path):
    summary = wbo.write_outputs(
        _data(),
        calendars=_cals(),
        drive_cfg={"briefings_folder_id": "folder1"},
        out_dir=tmp_path,
        credentials_path="x",
        token_path="y",
        dry_run=True,
    )
    assert summary["dry_run"] is True
    assert (tmp_path / "2026-05-27-morning.md").exists()
    assert (tmp_path / "2026-05-27-morning.events.json").exists()
    assert summary["calendar"]["written"] == 0
    assert summary["drive"]["written"] is False
    assert summary["events_total"] >= 1


def test_full_write_with_fakes(tmp_path, monkeypatch):
    cal_svc = FakeCalendarService([])
    drive_svc = FakeDriveService([])
    monkeypatch.setattr(wbo, "render", wbo.render)  # keep real render
    import google_calendar_client as gcal
    import google_drive_client as gdrive

    monkeypatch.setattr(gcal, "authenticate", lambda c, t: cal_svc)
    monkeypatch.setattr(gdrive, "authenticate", lambda c, t: drive_svc)
    monkeypatch.setattr(gdrive, "_make_media", lambda content: ("MEDIA", content))

    summary = wbo.write_outputs(
        _data(),
        calendars=_cals(),
        drive_cfg={"briefings_folder_id": "folder1"},
        out_dir=tmp_path,
        credentials_path="x",
        token_path="y",
    )

    # Every composed event upserted, all created (empty calendar to start).
    assert summary["events_total"] == summary["calendar"]["written"]
    assert summary["calendar"]["written"] == len(cal_svc.events().inserted)
    assert summary["calendar"]["errors"] == []
    assert summary["drive"]["written"] is True
    assert len(drive_svc.files().created) == 1


def test_rerun_is_idempotent_with_fakes(tmp_path, monkeypatch):
    # Shared store across two runs: second run must patch, not insert.
    store: list = []
    import google_calendar_client as gcal
    import google_drive_client as gdrive

    monkeypatch.setattr(gcal, "authenticate", lambda c, t: FakeCalendarService(store))
    monkeypatch.setattr(gdrive, "authenticate", lambda c, t: FakeDriveService([]))
    monkeypatch.setattr(gdrive, "_make_media", lambda content: ("MEDIA", content))

    kw = dict(
        calendars=_cals(),
        drive_cfg={"briefings_folder_id": "folder1"},
        out_dir=tmp_path,
        credentials_path="x",
        token_path="y",
    )
    s1 = wbo.write_outputs(_data(), **kw)
    count_after_first = len(store)
    s2 = wbo.write_outputs(_data(), **kw)

    # Event count in the store is unchanged after the second run.
    assert len(store) == count_after_first
    assert s1["events_total"] == s2["events_total"]
    assert s2["calendar"]["errors"] == []


def test_skip_flags(tmp_path, monkeypatch):
    import google_calendar_client as gcal
    import google_drive_client as gdrive

    # Authenticate must NOT be called when skipped — make it raise if it is.
    monkeypatch.setattr(gcal, "authenticate", lambda c, t: (_ for _ in ()).throw(AssertionError("called")))
    monkeypatch.setattr(gdrive, "authenticate", lambda c, t: (_ for _ in ()).throw(AssertionError("called")))

    summary = wbo.write_outputs(
        _data(),
        calendars=_cals(),
        drive_cfg={"briefings_folder_id": "folder1"},
        out_dir=tmp_path,
        credentials_path="x",
        token_path="y",
        skip_calendar=True,
        skip_drive=True,
    )
    assert summary["calendar"]["skipped"] is True
    assert summary["drive"]["skipped"] is True


def test_config_drive_parsing(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "calendars:\n"
        '  macro_events: "macro@cal"\n'
        "drive:\n"
        '  briefings_folder_id: "FOLDER123"\n'
        '  filename_pattern: "briefings/{date}-{mode}.md"\n'
        "watchlist:\n"
        "  - SPY\n",
        encoding="utf-8",
    )
    drive_cfg = wbo._config_drive(cfg)
    assert drive_cfg["briefings_folder_id"] == "FOLDER123"
    assert drive_cfg["filename_pattern"] == "briefings/{date}-{mode}.md"


def test_drive_filename_basename_only():
    assert wbo._drive_filename({}, "2026-05-27", "morning") == "2026-05-27-morning.md"
    assert (
        wbo._drive_filename({"filename_pattern": "x/y/{date}-{mode}.md"}, "2026-05-27", "afternoon")
        == "2026-05-27-afternoon.md"
    )
