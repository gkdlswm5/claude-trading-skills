"""Direct Google Calendar API client for the morning-trading-briefing.

Replaces the LLM-driven MCP write path. The LLM produces brief_data.json;
compose_brief.py renders it into a per-day events list; this module reads
those events and upserts each by mtb-key, making the calendar-write step
deterministic and idempotent.

See `references/GOOGLE_API_SETUP.md` for one-time OAuth setup and
`state/HANDOFF.md` for the v2.0/v2.1 slice plan. v2.0 ships the upsert
helper as documented; v2.1 adds the back-to-back idempotency test and the
multi-match cleanup edge case.

CLI:
    python3 google_calendar_client.py --authenticate \\
        --credentials ~/.config/morning-briefing/credentials.json \\
        --token       ~/.config/morning-briefing/token.json

Runs the InstalledAppFlow once, opens a browser, writes token.json. Use
the union scope (calendar + drive.file) so the same token.json also
works for google_drive_client.py.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Scope this module requires. The CLI entrypoint adds drive.file too so
# one consent flow produces a token usable by both clients.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"

# mtb-key marker convention embedded in event descriptions.
# Example: <!-- mtb-key: mtb:2026-05-27:earnings:crm-earnings-amc -->
MTB_KEY_PATTERN = re.compile(r"<!--\s*mtb-key:\s*(\S+)\s*-->")


def _load_or_refresh_credentials(
    credentials_path: str | Path,
    token_path: str | Path,
    scopes: list[str],
    interactive: bool = False,
) -> Any:
    """Load token.json, refresh if expired, or run OAuth flow if interactive.

    Non-interactive callers (write_brief_outputs.py) get a clear error
    pointing at the CLI fix instead of silently hanging on a browser flow
    that can't complete on a headless VPS.
    """
    # Local imports keep the module importable even when google-* libs aren't
    # installed (e.g. the dry-run / unit-test path). The error surfaces only
    # when somebody actually tries to authenticate.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path = Path(credentials_path).expanduser()
    token_path = Path(token_path).expanduser()

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:  # transport, invalid_grant, etc.
            if not interactive:
                raise RuntimeError(
                    f"Token refresh failed: {e}. Re-run "
                    f"`python3 {Path(__file__).name} --authenticate` to re-consent."
                ) from e
            creds = None  # fall through to flow
        else:
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds

    if not interactive:
        raise RuntimeError(
            f"No usable credentials at {token_path}. Run "
            f"`python3 {Path(__file__).name} --authenticate "
            f"--credentials {credentials_path} --token {token_path}` once on a "
            f"machine with a browser, then copy token.json to wherever this "
            f"script runs."
        )

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {credentials_path}. Download it "
            f"from Google Cloud Console — see references/GOOGLE_API_SETUP.md."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def authenticate(
    credentials_path: str | Path,
    token_path: str | Path,
    scopes: list[str] | None = None,
    interactive: bool = False,
) -> Any:
    """Return an authenticated Calendar v3 service.

    Args:
        credentials_path: Path to credentials.json downloaded from Google
            Cloud Console (Step 4 of GOOGLE_API_SETUP.md).
        token_path: Path where token.json is stored (created on first
            interactive run, refreshed automatically thereafter).
        scopes: Override scopes. Defaults to this module's SCOPES; pass the
            union of calendar + drive.file when sharing token.json with
            google_drive_client.
        interactive: When True, run the InstalledAppFlow if no usable token
            exists. When False (the default), raise instead — safe for cron.

    Returns:
        A googleapiclient.discovery.Resource for the Calendar v3 API.
    """
    from googleapiclient.discovery import build

    creds = _load_or_refresh_credentials(
        credentials_path, token_path, scopes or SCOPES, interactive=interactive
    )
    # cache_discovery=False silences the "file_cache is unavailable" warning
    # that pops on headless runs with newer oauth2client.
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def extract_mtb_key(description: str | None) -> str | None:
    """Pull the mtb-key marker out of an event description.

    Returns None if no marker is present (legacy / hand-created events).
    """
    if not description:
        return None
    match = MTB_KEY_PATTERN.search(description)
    return match.group(1) if match else None


def list_events_for_day(service: Any, calendar_id: str, date_iso: str) -> list[dict]:
    """List all events on `calendar_id` that touch the given YYYY-MM-DD day.

    The window is UTC-midnight to next-UTC-midnight. That's slightly wider
    than the ET day across DST, which is the right side to over-cover on:
    we only care about events whose description matches our mtb-key, so a
    few false positives don't matter and we never miss a real match.
    """
    d = datetime.strptime(date_iso, "%Y-%m-%d").date()
    time_min = f"{d.isoformat()}T00:00:00Z"
    time_max = f"{(d + timedelta(days=1)).isoformat()}T00:00:00Z"
    events: list[dict] = []
    page_token: str | None = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                showDeleted=False,
                maxResults=250,
                pageToken=page_token,
            )
            .execute()
        )
        events.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return events


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

    v2.1 behavior: when multiple existing events match the same mtb-key
    (a leftover from the 2026-05-27 incident), patch the first to the new
    payload and delete the extras, so the day converges to exactly one
    event per key. This makes the write self-healing — a rerun cleans up
    duplicates a prior bad run left behind, not just avoids new ones.

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
    if extract_mtb_key(event_payload.get("description")) != mtb_key:
        raise ValueError(
            f"event_payload.description must embed the mtb-key marker "
            f"`<!-- mtb-key: {mtb_key} -->` so future runs can find it. "
            f"compose_brief.py stamps this; check the upstream pipeline if "
            f"it's missing."
        )
    matches = [
        e
        for e in list_events_for_day(service, calendar_id, date_iso)
        if extract_mtb_key(e.get("description")) == mtb_key
    ]
    if matches:
        target = matches[0]
        result = (
            service.events()
            .patch(calendarId=calendar_id, eventId=target["id"], body=event_payload)
            .execute()
        )
        # Collapse any leftover duplicates of this key down to the one we kept.
        for dup in matches[1:]:
            service.events().delete(
                calendarId=calendar_id, eventId=dup["id"]
            ).execute()
        return result
    return service.events().insert(calendarId=calendar_id, body=event_payload).execute()


def delete_events_by_key(
    service: Any, calendar_id: str, mtb_key: str, date_iso: str
) -> int:
    """Delete all events on `calendar_id` for `date_iso` matching mtb_key.

    Cleanup utility for hand-recovering from a bad run. Not called in the
    normal pipeline. Returns the count of events deleted.
    """
    deleted = 0
    for e in list_events_for_day(service, calendar_id, date_iso):
        if extract_mtb_key(e.get("description")) == mtb_key:
            service.events().delete(calendarId=calendar_id, eventId=e["id"]).execute()
            deleted += 1
    return deleted


def _cli() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="One-time OAuth flow for the morning-trading-briefing.",
        epilog=(
            "After this completes, the same token.json works for both the "
            "Calendar and Drive clients because the flow consents to both "
            "scopes."
        ),
    )
    ap.add_argument(
        "--authenticate",
        action="store_true",
        help="Run the InstalledAppFlow and write token.json.",
    )
    ap.add_argument(
        "--credentials",
        default="~/.config/morning-briefing/credentials.json",
        help="Path to credentials.json from Google Cloud Console.",
    )
    ap.add_argument(
        "--token",
        default="~/.config/morning-briefing/token.json",
        help="Path where token.json is written/refreshed.",
    )
    args = ap.parse_args()

    if not args.authenticate:
        ap.print_help(sys.stderr)
        return 1

    # Union scope so one consent grants Calendar + Drive.
    scopes = sorted(set(SCOPES) | {DRIVE_SCOPE})
    _load_or_refresh_credentials(args.credentials, args.token, scopes, interactive=True)
    token_path = Path(args.token).expanduser()
    print(f"Wrote {token_path}", file=sys.stderr)
    print(
        "Done. token.json is now valid for both Calendar + Drive scopes. "
        "Copy it (and credentials.json) to the VPS when you're ready.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
