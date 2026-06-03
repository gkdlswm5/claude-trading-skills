"""Direct Google Calendar API client for the morning-trading-briefing.

Replaces the LLM-driven MCP write path. The LLM produces brief_data.json;
this module reads event payloads (built by compose_brief.build_calendar_events)
and upserts them by mtb-key, making the calendar-write step deterministic and
idempotent.

See `references/GOOGLE_API_SETUP.md` for OAuth setup and v2.0 in
`state/HANDOFF.md` for implementation order. All googleapiclient imports are
deferred so this module imports (and unit-tests with a fake service) without the
Google libraries installed.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

# Scopes are requested combined (Calendar + Drive) by google_oauth so one
# token.json serves both clients.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# mtb-key marker convention embedded in event descriptions.
# Example: <!-- mtb-key: mtb:2026-05-27:earnings:crm-earnings-amc -->
MTB_KEY_PATTERN = re.compile(r"<!--\s*mtb-key:\s*(\S+)\s*-->")


def authenticate(credentials_path: str, token_path: str) -> Any:
    """Run OAuth flow (first time) or refresh existing token.

    Args:
        credentials_path: Path to credentials.json downloaded from Google
            Cloud Console.
        token_path: Path where token.json is stored (created on first run,
            refreshed automatically thereafter).

    Returns:
        An authenticated googleapiclient.discovery.Resource for Calendar v3.
    """
    from google_oauth import SCOPES as ALL_SCOPES
    from google_oauth import build_service, load_credentials

    creds = load_credentials(credentials_path, token_path, ALL_SCOPES)
    return build_service("calendar", "v3", creds)


def extract_mtb_key(description: str) -> str | None:
    """Pull the mtb-key marker out of an event description.

    Returns None if no marker is present (legacy / hand-created events).
    """
    if not description:
        return None
    match = MTB_KEY_PATTERN.search(description)
    return match.group(1) if match else None


def _to_google_event(payload: dict) -> dict:
    """Translate a compose_brief event payload to a Calendar v3 event resource.

    Compose payloads carry: summary, startTime, endTime, timeZone, description,
    colorId, and (for all-day events) allDay + UTC-midnight start/end. Calendar
    v3 wants {date} for all-day and {dateTime, timeZone} for timed events.
    """
    body: dict[str, Any] = {
        "summary": payload.get("summary", ""),
        "description": payload.get("description", ""),
    }
    if payload.get("colorId"):
        body["colorId"] = payload["colorId"]

    if payload.get("allDay"):
        # Compose emits "YYYY-MM-DDT00:00:00Z" for both bounds; take the date part.
        start_date = payload["startTime"][:10]
        end_date = payload["endTime"][:10]
        body["start"] = {"date": start_date}
        body["end"] = {"date": end_date}
    else:
        tz = payload.get("timeZone", "America/New_York")
        body["start"] = {"dateTime": payload["startTime"], "timeZone": tz}
        body["end"] = {"dateTime": payload["endTime"], "timeZone": tz}

    return body


def list_events_for_day(service: Any, calendar_id: str, date_iso: str) -> list[dict]:
    """List events on `calendar_id` overlapping the YYYY-MM-DD `date_iso` day.

    Queries a wide UTC window (day-1 .. day+1) so it captures both timed ET
    events and all-day events stored at UTC midnight, then returns the full
    items. Callers filter by mtb-key. Paginates fully.
    """
    d = date.fromisoformat(date_iso)
    time_min = f"{(d - timedelta(days=1)).isoformat()}T00:00:00Z"
    time_max = f"{(d + timedelta(days=2)).isoformat()}T00:00:00Z"

    items: list[dict] = []
    page_token = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                showDeleted=False,
                maxResults=2500,
                pageToken=page_token,
            )
            .execute()
        )
        items.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def _find_by_key(service: Any, calendar_id: str, mtb_key: str, date_iso: str) -> list[dict]:
    """Return existing events on the day whose description carries `mtb_key`."""
    return [
        ev
        for ev in list_events_for_day(service, calendar_id, date_iso)
        if extract_mtb_key(ev.get("description", "")) == mtb_key
    ]


def upsert_event(
    service: Any,
    calendar_id: str,
    mtb_key: str,
    event_payload: dict,
    date_iso: str,
) -> dict:
    """Create or update a calendar event by mtb-key.

    Lists existing events for the day, finds any with a matching mtb-key in the
    description, and either patches the first match or creates a new one. This is
    the core idempotency primitive — same input always converges to the same
    calendar state. If duplicates already exist for the key (e.g. from a prior
    bad run), the first is patched and the rest are deleted so the day collapses
    back to one event per key.

    Args:
        service: Authenticated Calendar API client.
        calendar_id: Target sub-calendar ID.
        mtb_key: Unique key for this event (e.g. mtb:2026-05-27:earnings:crm).
        event_payload: Compose event payload (summary, start/end, timeZone,
            description with the embedded mtb-key marker, colorId, allDay).
        date_iso: YYYY-MM-DD; the day to scan for existing events.

    Returns:
        The created or updated event resource.
    """
    body = _to_google_event(event_payload)
    existing = _find_by_key(service, calendar_id, mtb_key, date_iso)

    if not existing:
        return service.events().insert(calendarId=calendar_id, body=body).execute()

    keep = existing[0]
    result = (
        service.events()
        .patch(calendarId=calendar_id, eventId=keep["id"], body=body)
        .execute()
    )
    # Collapse any accidental duplicates of the same key down to the one we kept.
    for dup in existing[1:]:
        service.events().delete(calendarId=calendar_id, eventId=dup["id"]).execute()
    return result


def delete_events_by_key(service: Any, calendar_id: str, mtb_key: str, date_iso: str) -> int:
    """Delete all events on `calendar_id` for `date_iso` matching mtb_key.

    Cleanup utility for hand-recovering from a bad run. Not called in the normal
    pipeline.

    Returns:
        Count of events deleted.
    """
    matches = _find_by_key(service, calendar_id, mtb_key, date_iso)
    for ev in matches:
        service.events().delete(calendarId=calendar_id, eventId=ev["id"]).execute()
    return len(matches)


def _cli(argv: list[str]) -> int:
    import argparse

    from google_oauth import DEFAULT_CREDENTIALS_PATH, DEFAULT_TOKEN_PATH

    ap = argparse.ArgumentParser(description="Calendar client OAuth + sanity check.")
    ap.add_argument(
        "--authenticate",
        action="store_true",
        help="Run/refresh the OAuth flow, write token.json, and list calendars.",
    )
    ap.add_argument("--credentials", default=DEFAULT_CREDENTIALS_PATH)
    ap.add_argument("--token", default=DEFAULT_TOKEN_PATH)
    args = ap.parse_args(argv)

    if not args.authenticate:
        ap.print_help()
        return 1

    service = authenticate(args.credentials, args.token)
    print(f"Authenticated. Token at: {args.token}")
    cals = service.calendarList().list().execute().get("items", [])
    print(f"Visible calendars ({len(cals)}):")
    for c in cals:
        print(f"  {c.get('summary', '?')}  ->  {c.get('id', '?')}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_cli(sys.argv[1:]))
