#!/usr/bin/env python3
"""Tests for the v2.0 direct Google API write path.

These use in-memory fake services (no googleapiclient, no network, no creds), so
they prove the upsert/translate/find logic deterministically. Real OAuth and HTTP
are exercised manually against a throwaway calendar (see HANDOFF.md v2.0).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import google_calendar_client as gcal  # noqa: E402
import google_drive_client as gdrive  # noqa: E402


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _Req:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeEvents:
    def __init__(self, store):
        self.store = store
        self.inserted: list = []
        self.deleted: list = []
        self.patched: list = []
        self._n = 0

    def list(self, **kw):
        # Fake ignores time-window filtering; returns the whole store, one page.
        return _Req({"items": list(self.store)})

    def insert(self, calendarId, body):
        self._n += 1
        ev = dict(body)
        ev["id"] = f"new-{self._n}"
        self.inserted.append((calendarId, ev))
        self.store.append(ev)
        return _Req(ev)

    def patch(self, calendarId, eventId, body):
        self.patched.append((calendarId, eventId, body))
        for ev in self.store:
            if ev.get("id") == eventId:
                ev.update(body)
                return _Req(ev)
        return _Req({"id": eventId, **body})

    def delete(self, calendarId, eventId):
        self.deleted.append((calendarId, eventId))
        self.store[:] = [e for e in self.store if e.get("id") != eventId]
        return _Req({})


class FakeCalendarService:
    def __init__(self, store=None):
        self._events = _FakeEvents(store if store is not None else [])

    def events(self):
        return self._events


def _evt(key: str, eid: str, summary: str = "x") -> dict:
    return {
        "id": eid,
        "summary": summary,
        "description": f"body\n\n<!-- mtb-key: {key} -->",
    }


def _payload(all_day: bool = False) -> dict:
    if all_day:
        return {
            "calendarId": "pos@cal",
            "summary": "Morning Brief",
            "startTime": "2026-05-27T00:00:00Z",
            "endTime": "2026-05-28T00:00:00Z",
            "timeZone": "America/New_York",
            "allDay": True,
            "description": "full brief\n\n<!-- mtb-key: mtb:2026-05-27:my_positions:morning-brief -->",
            "colorId": "11",
        }
    return {
        "calendarId": "macro@cal",
        "summary": "CPI",
        "startTime": "2026-05-27T08:30:00",
        "endTime": "2026-05-27T08:45:00",
        "timeZone": "America/New_York",
        "description": "cons\n\n<!-- mtb-key: mtb:2026-05-27:macro_events:cpi -->",
        "colorId": "11",
    }


# --------------------------------------------------------------------------- #
# extract_mtb_key + translate
# --------------------------------------------------------------------------- #
def test_extract_mtb_key():
    assert gcal.extract_mtb_key("x\n<!-- mtb-key: mtb:2026-05-27:earnings:crm -->") == "mtb:2026-05-27:earnings:crm"
    assert gcal.extract_mtb_key("no marker here") is None
    assert gcal.extract_mtb_key("") is None


def test_to_google_event_timed():
    body = gcal._to_google_event(_payload(all_day=False))
    assert body["start"] == {"dateTime": "2026-05-27T08:30:00", "timeZone": "America/New_York"}
    assert body["end"]["dateTime"] == "2026-05-27T08:45:00"
    assert body["colorId"] == "11"
    assert "date" not in body["start"]


def test_to_google_event_all_day():
    body = gcal._to_google_event(_payload(all_day=True))
    assert body["start"] == {"date": "2026-05-27"}
    assert body["end"] == {"date": "2026-05-28"}
    assert "dateTime" not in body["start"]


# --------------------------------------------------------------------------- #
# upsert_event
# --------------------------------------------------------------------------- #
def test_upsert_creates_when_absent():
    svc = FakeCalendarService([])
    p = _payload()
    gcal.upsert_event(svc, "macro@cal", "mtb:2026-05-27:macro_events:cpi", p, "2026-05-27")
    assert len(svc.events().inserted) == 1
    assert len(svc.events().patched) == 0


def test_upsert_patches_when_present():
    key = "mtb:2026-05-27:macro_events:cpi"
    svc = FakeCalendarService([_evt(key, "existing-1")])
    gcal.upsert_event(svc, "macro@cal", key, _payload(), "2026-05-27")
    assert len(svc.events().inserted) == 0
    assert len(svc.events().patched) == 1
    assert svc.events().patched[0][1] == "existing-1"


def test_upsert_collapses_duplicates_to_one():
    key = "mtb:2026-05-27:macro_events:cpi"
    svc = FakeCalendarService([_evt(key, "dup-a"), _evt(key, "dup-b"), _evt(key, "dup-c")])
    gcal.upsert_event(svc, "macro@cal", key, _payload(), "2026-05-27")
    # first patched, the other two deleted -> store collapses to one
    assert len(svc.events().patched) == 1
    assert len(svc.events().deleted) == 2
    remaining = [e for e in svc.events().store if gcal.extract_mtb_key(e["description"]) == key]
    assert len(remaining) == 1


def test_upsert_ignores_other_keys():
    svc = FakeCalendarService([_evt("mtb:2026-05-27:macro_events:other", "o1")])
    gcal.upsert_event(svc, "macro@cal", "mtb:2026-05-27:macro_events:cpi", _payload(), "2026-05-27")
    # no match for cpi -> insert, leave the other untouched
    assert len(svc.events().inserted) == 1
    assert len(svc.events().deleted) == 0


def test_delete_events_by_key():
    key = "mtb:2026-05-27:macro_events:cpi"
    svc = FakeCalendarService([_evt(key, "a"), _evt(key, "b"), _evt("other", "c")])
    n = gcal.delete_events_by_key(svc, "macro@cal", key, "2026-05-27")
    assert n == 2
    assert {e["id"] for e in svc.events().store} == {"c"}


# --------------------------------------------------------------------------- #
# Drive client
# --------------------------------------------------------------------------- #
class _FakeFiles:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.created: list = []
        self.updated: list = []

    def list(self, **kw):
        self.last_q = kw.get("q")
        return _Req({"files": list(self.existing)})

    def create(self, body, media_body, fields):
        self.created.append((body, media_body))
        return _Req({"id": "created-1", "name": body["name"]})

    def update(self, fileId, media_body, fields):
        self.updated.append((fileId, media_body))
        return _Req({"id": fileId, "name": "updated"})


class FakeDriveService:
    def __init__(self, existing=None):
        self._files = _FakeFiles(existing)

    def files(self):
        return self._files


def test_find_file_by_name_found():
    svc = FakeDriveService([{"id": "f1", "name": "2026-05-27-morning.md"}])
    assert gdrive.find_file_by_name(svc, "folder1", "2026-05-27-morning.md") == "f1"


def test_find_file_by_name_absent():
    svc = FakeDriveService([])
    assert gdrive.find_file_by_name(svc, "folder1", "2026-05-27-morning.md") is None


def test_upsert_markdown_creates(monkeypatch):
    monkeypatch.setattr(gdrive, "_make_media", lambda content: ("MEDIA", content))
    svc = FakeDriveService([])
    gdrive.upsert_markdown(svc, "folder1", "2026-05-27-morning.md", "# hi")
    assert len(svc.files().created) == 1
    assert len(svc.files().updated) == 0
    assert svc.files().created[0][0]["parents"] == ["folder1"]


def test_upsert_markdown_overwrites(monkeypatch):
    monkeypatch.setattr(gdrive, "_make_media", lambda content: ("MEDIA", content))
    svc = FakeDriveService([{"id": "f1", "name": "2026-05-27-morning.md"}])
    gdrive.upsert_markdown(svc, "folder1", "2026-05-27-morning.md", "# hi")
    assert len(svc.files().created) == 0
    assert len(svc.files().updated) == 1
    assert svc.files().updated[0][0] == "f1"
