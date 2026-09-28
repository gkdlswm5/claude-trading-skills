"""Unit tests for google_calendar_client + google_drive_client (v2.0).

These tests mock the Google API discovery Resource so they run without
google-api-python-client installed. The goal is to verify the upsert
logic — the actual API calls are exercised manually via --dry-run +
real-calendar smoke tests (deferred to v2.1).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPTS = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS))

from google_calendar_client import (  # noqa: E402
    extract_mtb_key,
    list_events_for_day,
    upsert_event,
    delete_events_by_key,
)
from google_drive_client import find_file_by_name, upsert_markdown  # noqa: E402


# ---------------------------------------------------------------------------
# extract_mtb_key
# ---------------------------------------------------------------------------


def test_extract_mtb_key_finds_marker():
    desc = "Some body text\n\n<!-- mtb-key: mtb:2026-05-27:earnings:crm -->"
    assert extract_mtb_key(desc) == "mtb:2026-05-27:earnings:crm"


def test_extract_mtb_key_handles_none():
    assert extract_mtb_key(None) is None


def test_extract_mtb_key_handles_empty_string():
    assert extract_mtb_key("") is None


def test_extract_mtb_key_handles_no_marker():
    assert extract_mtb_key("just description, no marker here") is None


def test_extract_mtb_key_tolerates_whitespace():
    # Renderers / users sometimes mangle the marker; be a little forgiving.
    desc = "<!--   mtb-key:   mtb:2026-05-27:macro_events:cpi   -->"
    assert extract_mtb_key(desc) == "mtb:2026-05-27:macro_events:cpi"


# ---------------------------------------------------------------------------
# Calendar — list_events_for_day
# ---------------------------------------------------------------------------


def _calendar_service_listing(items_per_page: list[list[dict]]) -> MagicMock:
    """Build a MagicMock service.events().list().execute() chain that returns
    successive pages from items_per_page (last page must not include a
    nextPageToken).
    """
    service = MagicMock()
    calls: list[dict] = []
    pages = list(items_per_page)
    page_tokens = [f"tok{i}" for i in range(len(pages) - 1)] + [None]

    def list_call(**kwargs):
        calls.append(kwargs)
        idx = len(calls) - 1
        execute = MagicMock()
        execute.execute.return_value = {
            "items": pages[idx],
            **({"nextPageToken": page_tokens[idx]} if page_tokens[idx] else {}),
        }
        return execute

    service.events.return_value.list.side_effect = list_call
    return service


def test_list_events_for_day_paginates():
    pages = [
        [{"id": "a"}, {"id": "b"}],
        [{"id": "c"}],
    ]
    service = _calendar_service_listing(pages)
    events = list_events_for_day(service, "cal@x", "2026-05-27")
    assert [e["id"] for e in events] == ["a", "b", "c"]
    # Two pages → two list calls.
    assert service.events.return_value.list.call_count == 2


def test_list_events_for_day_uses_utc_midnight_bounds():
    service = _calendar_service_listing([[]])
    list_events_for_day(service, "cal@x", "2026-05-27")
    kwargs = service.events.return_value.list.call_args.kwargs
    assert kwargs["timeMin"] == "2026-05-27T00:00:00Z"
    assert kwargs["timeMax"] == "2026-05-28T00:00:00Z"
    assert kwargs["singleEvents"] is True
    assert kwargs["showDeleted"] is False


# ---------------------------------------------------------------------------
# Calendar — upsert_event
# ---------------------------------------------------------------------------


KEY = "mtb:2026-05-27:earnings:crm"
PAYLOAD = {
    "summary": "CRM earnings AMC",
    "description": f"body\n\n<!-- mtb-key: {KEY} -->",
    "start": {"dateTime": "2026-05-27T16:00:00", "timeZone": "America/New_York"},
    "end": {"dateTime": "2026-05-27T16:15:00", "timeZone": "America/New_York"},
}


def _upsert_service(existing: list[dict]) -> MagicMock:
    """Build a service mock with one list page + insert + patch endpoints."""
    service = MagicMock()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": existing
    }
    service.events.return_value.insert.return_value.execute.return_value = {
        "id": "new_event_id"
    }
    service.events.return_value.patch.return_value.execute.return_value = {
        "id": "existing_event_id"
    }
    service.events.return_value.delete.return_value.execute.return_value = None
    return service


class _Exec:
    """Tiny wrapper so a built request's `.execute()` returns a preset value."""

    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _StatefulCalendar:
    """Minimal in-memory fake of the Calendar discovery Resource.

    Supports the events().list/insert/patch/delete().execute() chain that
    google_calendar_client uses, holding real state so back-to-back upserts
    can be asserted on. Time-window filtering is ignored (the client filters
    by mtb-key, which is the behavior under test); list() returns all events
    in one page.
    """

    def __init__(self, seed: list[dict] | None = None):
        self._store: list[dict] = [dict(e) for e in (seed or [])]
        self._next = 1

    # discovery-style chain: events() returns self; verbs return _Exec.
    def events(self):
        return self

    def list(self, **kwargs):
        return _Exec({"items": [dict(e) for e in self._store]})

    def insert(self, calendarId=None, body=None):
        event = dict(body or {}, id=f"gen{self._next}")
        self._next += 1
        self._store.append(event)
        return _Exec(dict(event))

    def patch(self, calendarId=None, eventId=None, body=None):
        for e in self._store:
            if e["id"] == eventId:
                e.update(body or {})
                return _Exec(dict(e))
        raise KeyError(eventId)

    def delete(self, calendarId=None, eventId=None):
        self._store = [e for e in self._store if e["id"] != eventId]
        return _Exec(None)

    # assertion helpers
    def count_with_key(self, key: str) -> int:
        return sum(
            1 for e in self._store if extract_mtb_key(e.get("description")) == key
        )

    def only_id_with_key(self, key: str) -> str:
        ids = [
            e["id"]
            for e in self._store
            if extract_mtb_key(e.get("description")) == key
        ]
        assert len(ids) == 1, f"expected exactly one event with key, got {ids}"
        return ids[0]


def test_upsert_event_inserts_when_no_match():
    service = _upsert_service(existing=[])
    result = upsert_event(service, "cal@x", KEY, PAYLOAD, "2026-05-27")
    assert result["id"] == "new_event_id"
    service.events.return_value.insert.assert_called_once_with(
        calendarId="cal@x", body=PAYLOAD
    )
    service.events.return_value.patch.assert_not_called()


def test_upsert_event_patches_when_match_exists():
    existing = [{"id": "existing_event_id", "description": f"old\n<!-- mtb-key: {KEY} -->"}]
    service = _upsert_service(existing=existing)
    result = upsert_event(service, "cal@x", KEY, PAYLOAD, "2026-05-27")
    assert result["id"] == "existing_event_id"
    service.events.return_value.patch.assert_called_once_with(
        calendarId="cal@x", eventId="existing_event_id", body=PAYLOAD
    )
    service.events.return_value.insert.assert_not_called()


def test_upsert_event_ignores_non_matching_existing():
    existing = [
        {"id": "other1", "description": "no marker here"},
        {"id": "other2", "description": "<!-- mtb-key: mtb:2026-05-27:earnings:other -->"},
    ]
    service = _upsert_service(existing=existing)
    upsert_event(service, "cal@x", KEY, PAYLOAD, "2026-05-27")
    # Both existing events have different (or missing) keys → no match → insert.
    service.events.return_value.insert.assert_called_once()


def test_upsert_event_patches_first_and_deletes_extras_when_multiple_match():
    """v2.1: when an old run left dupes, patch the first and delete the rest.

    This is the self-healing behavior that recovers from the 2026-05-27
    incident — a rerun collapses N duplicates of a key back down to one.
    """
    dup_desc = f"<!-- mtb-key: {KEY} -->"
    existing = [
        {"id": "dupe1", "description": dup_desc},
        {"id": "dupe2", "description": dup_desc},
        {"id": "dupe3", "description": dup_desc},
    ]
    service = _upsert_service(existing=existing)
    upsert_event(service, "cal@x", KEY, PAYLOAD, "2026-05-27")

    # First match is patched (updated in place), not deleted.
    service.events.return_value.patch.assert_called_once()
    assert service.events.return_value.patch.call_args.kwargs["eventId"] == "dupe1"

    # The two extras are deleted so the day converges to one event per key.
    deleted_ids = [
        call.kwargs["eventId"]
        for call in service.events.return_value.delete.call_args_list
    ]
    assert sorted(deleted_ids) == ["dupe2", "dupe3"]
    service.events.return_value.insert.assert_not_called()


def test_upsert_event_idempotent_across_back_to_back_runs():
    """v2.1 rerun assertion (HANDOFF): run the same upsert twice against a
    stateful fake calendar; the key must resolve to exactly one event both
    times — no duplicate accumulates on the second pass.
    """
    service = _StatefulCalendar()
    upsert_event(service, "cal@x", KEY, PAYLOAD, "2026-05-27")
    assert service.count_with_key(KEY) == 1
    first_id = service.only_id_with_key(KEY)

    # Second back-to-back run with the same payload.
    upsert_event(service, "cal@x", KEY, PAYLOAD, "2026-05-27")
    assert service.count_with_key(KEY) == 1
    # Same event was updated in place, not replaced.
    assert service.only_id_with_key(KEY) == first_id


def test_upsert_event_collapses_preexisting_duplicates_on_first_run():
    """A stateful end-to-end check that three seeded duplicates collapse to
    one after a single upsert (and stay at one on a rerun)."""
    dup_desc = f"body\n<!-- mtb-key: {KEY} -->"
    service = _StatefulCalendar(
        seed=[
            {"id": "seed1", "description": dup_desc},
            {"id": "seed2", "description": dup_desc},
            {"id": "seed3", "description": dup_desc},
        ]
    )
    assert service.count_with_key(KEY) == 3
    upsert_event(service, "cal@x", KEY, PAYLOAD, "2026-05-27")
    assert service.count_with_key(KEY) == 1
    # The kept event is the first seeded one, patched in place.
    assert service.only_id_with_key(KEY) == "seed1"
    upsert_event(service, "cal@x", KEY, PAYLOAD, "2026-05-27")
    assert service.count_with_key(KEY) == 1


def test_upsert_event_rejects_payload_without_mtb_key():
    """Refuse to write if the payload doesn't carry the dedup marker — the
    next run would silently duplicate it."""
    service = _upsert_service(existing=[])
    bad_payload = dict(PAYLOAD, description="no marker, just body")
    with pytest.raises(ValueError, match="mtb-key"):
        upsert_event(service, "cal@x", KEY, bad_payload, "2026-05-27")


# ---------------------------------------------------------------------------
# Calendar — delete_events_by_key
# ---------------------------------------------------------------------------


def test_delete_events_by_key_counts_only_matches():
    existing = [
        {"id": "match1", "description": f"<!-- mtb-key: {KEY} -->"},
        {"id": "other", "description": "<!-- mtb-key: mtb:2026-05-27:earnings:other -->"},
        {"id": "match2", "description": f"<!-- mtb-key: {KEY} -->"},
    ]
    service = MagicMock()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": existing
    }
    service.events.return_value.delete.return_value.execute.return_value = None

    assert delete_events_by_key(service, "cal@x", KEY, "2026-05-27") == 2
    deleted_ids = [
        call.kwargs["eventId"]
        for call in service.events.return_value.delete.call_args_list
    ]
    assert sorted(deleted_ids) == ["match1", "match2"]


# ---------------------------------------------------------------------------
# Drive — find_file_by_name
# ---------------------------------------------------------------------------


def test_find_file_by_name_returns_id_when_found():
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "drive_id_1", "name": "2026-05-27-morning.md"}]
    }
    fid = find_file_by_name(service, "folder123", "2026-05-27-morning.md")
    assert fid == "drive_id_1"
    q = service.files.return_value.list.call_args.kwargs["q"]
    assert "name = '2026-05-27-morning.md'" in q
    assert "'folder123' in parents" in q
    assert "trashed = false" in q


def test_find_file_by_name_returns_none_when_missing():
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {"files": []}
    assert find_file_by_name(service, "folder123", "absent.md") is None


def test_find_file_by_name_escapes_single_quotes():
    """Filenames with apostrophes shouldn't break the Drive query string."""
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {"files": []}
    find_file_by_name(service, "folder123", "Joe's brief.md")
    q = service.files.return_value.list.call_args.kwargs["q"]
    # The single quote is escaped — the literal substring 'Joe\'s' appears.
    assert "Joe\\'s brief.md" in q


# ---------------------------------------------------------------------------
# Drive — upsert_markdown
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_media(monkeypatch):
    """Replace MediaInMemoryUpload with a sentinel so we can assert on it.

    The real class needs google-api-python-client installed; we don't.
    """
    sentinel = MagicMock(name="MediaInMemoryUpload-sentinel")

    def fake_factory(content, mimetype, resumable):
        sentinel.calls.append({"content": content, "mimetype": mimetype, "resumable": resumable})
        return sentinel

    sentinel.calls = []
    # Patch the symbol where it's looked up (inside upsert_markdown's local
    # import) by injecting a fake googleapiclient.http module.
    import types

    fake_module = types.ModuleType("googleapiclient.http")
    fake_module.MediaInMemoryUpload = fake_factory
    fake_pkg = types.ModuleType("googleapiclient")
    fake_pkg.http = fake_module
    monkeypatch.setitem(sys.modules, "googleapiclient", fake_pkg)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", fake_module)
    return sentinel


def test_upsert_markdown_creates_when_missing(fake_media):
    service = MagicMock()
    # find_file_by_name → no match
    service.files.return_value.list.return_value.execute.return_value = {"files": []}
    service.files.return_value.create.return_value.execute.return_value = {
        "id": "new_drive_id",
        "name": "2026-05-27-morning.md",
        "modifiedTime": "2026-05-27T11:00:00Z",
        "webViewLink": "https://drive.google.com/...",
    }
    result = upsert_markdown(service, "folder123", "2026-05-27-morning.md", "# Brief")
    assert result["id"] == "new_drive_id"
    service.files.return_value.create.assert_called_once()
    body = service.files.return_value.create.call_args.kwargs["body"]
    assert body == {
        "name": "2026-05-27-morning.md",
        "parents": ["folder123"],
        "mimeType": "text/markdown",
    }
    service.files.return_value.update.assert_not_called()
    assert fake_media.calls[0]["content"] == b"# Brief"
    assert fake_media.calls[0]["mimetype"] == "text/markdown"


def test_upsert_markdown_updates_when_present(fake_media):
    service = MagicMock()
    service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "existing_drive_id", "name": "2026-05-27-morning.md"}]
    }
    service.files.return_value.update.return_value.execute.return_value = {
        "id": "existing_drive_id",
        "name": "2026-05-27-morning.md",
        "modifiedTime": "2026-05-27T13:00:00Z",
        "webViewLink": "https://drive.google.com/...",
    }
    result = upsert_markdown(
        service, "folder123", "2026-05-27-morning.md", "# Brief v2"
    )
    assert result["id"] == "existing_drive_id"
    service.files.return_value.update.assert_called_once()
    # Same file ID → content swap, no rename, no re-parent.
    update_kwargs = service.files.return_value.update.call_args.kwargs
    assert update_kwargs["fileId"] == "existing_drive_id"
    assert "body" not in update_kwargs  # not renaming
    service.files.return_value.create.assert_not_called()
    assert fake_media.calls[0]["content"] == b"# Brief v2"
