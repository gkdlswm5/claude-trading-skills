"""Direct Google Calendar API client for the morning-trading-briefing.

Replaces the LLM-driven MCP write path. The LLM produces brief_data.json;
this module reads event payloads from that JSON and upserts them by
mtb-key, making the calendar-write step deterministic and idempotent.

Implementation scaffold — function bodies raise NotImplementedError.
See `references/GOOGLE_API_SETUP.md` for OAuth setup and v2.0 in
`state/HANDOFF.md` for implementation order.
"""

from __future__ import annotations

import re
from typing import Any

# Scopes required for this module. Keep narrow.
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
    raise NotImplementedError("v2.0 work item — see HANDOFF.md")


def extract_mtb_key(description: str) -> str | None:
    """Pull the mtb-key marker out of an event description.

    Returns None if no marker is present (legacy / hand-created events).
    """
    if not description:
        return None
    match = MTB_KEY_PATTERN.search(description)
    return match.group(1) if match else None


def list_events_for_day(service: Any, calendar_id: str, date_iso: str) -> list[dict]:
    """List all events on `calendar_id` for the given YYYY-MM-DD date.

    Used by upsert_event to find existing events to update.
    """
    raise NotImplementedError("v2.0 work item — see HANDOFF.md")


def upsert_event(
    service: Any,
    calendar_id: str,
    mtb_key: str,
    event_payload: dict,
    date_iso: str,
) -> dict:
    """Create or update a calendar event by mtb-key.

    Lists existing events for the day, finds any with a matching mtb-key
    in the description, and either patches that event or creates a new
    one. This is the core idempotency primitive — same input always
    produces the same calendar state.

    Args:
        service: Authenticated Calendar API client.
        calendar_id: Target sub-calendar ID.
        mtb_key: Unique key for this event (e.g. mtb:2026-05-27:earnings:crm).
        event_payload: Google Calendar event resource (summary, start, end,
            description, etc.). The description MUST contain the mtb-key
            marker so future runs can find this event.
        date_iso: YYYY-MM-DD; the day to scan for existing events.

    Returns:
        The created or updated event resource.
    """
    raise NotImplementedError("v2.0 work item — see HANDOFF.md")


def delete_events_by_key(service: Any, calendar_id: str, mtb_key: str, date_iso: str) -> int:
    """Delete all events on `calendar_id` for `date_iso` matching mtb_key.

    Cleanup utility for hand-recovering from a bad run. Not called in
    the normal pipeline.

    Returns:
        Count of events deleted.
    """
    raise NotImplementedError("v2.0 work item — see HANDOFF.md")


if __name__ == "__main__":
    # CLI entrypoint for one-time OAuth setup.
    # Will be: python3 google_calendar_client.py --authenticate
    import sys

    print("v2.0 scaffold — implementation pending. See HANDOFF.md.", file=sys.stderr)
    sys.exit(1)
