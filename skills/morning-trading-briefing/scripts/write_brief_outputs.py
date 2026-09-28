#!/usr/bin/env python3
"""Python-driven write path for the morning-trading-briefing (v2.0).

Reads the artifacts compose_brief.py produced for a given date+mode and
pushes them to Google Calendar + Drive via the direct API clients in
google_calendar_client.py and google_drive_client.py. This replaces the
old LLM/MCP write path that produced 37 duplicate events on 2026-05-27.

Pipeline:
    LLM-orchestrator → brief_data.json
       └─→ compose_brief.py → YYYY-MM-DD-{mode}.md + .events.json
              └─→ write_brief_outputs.py → Google APIs

Usage:
    # Smoke-test wiring without authenticating against Google:
    python3 write_brief_outputs.py --config config.yaml --dry-run \\
        --date 2026-05-27 --mode morning

    # Full run (requires token.json — see google_calendar_client.py CLI):
    python3 write_brief_outputs.py --config config.yaml \\
        --date 2026-05-27 --mode morning

    # Selectively skip one writer:
    python3 write_brief_outputs.py --config config.yaml --skip-drive

Idempotency: every event in events.json carries an mtb-key marker in its
description; upsert_event() finds-and-patches by that key. The same Drive
filename + folder upserts in place via upsert_markdown(). Running this
script twice back-to-back should produce zero net changes — v2.1 wires
that into an automated test.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as date_cls
from pathlib import Path
from typing import Any

# Import siblings by relative path so the script works when run directly
# OR via `python -m`. compose_brief.py uses the same pattern.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google_calendar_client import (  # noqa: E402
    DRIVE_SCOPE,
    SCOPES as CALENDAR_SCOPES,
    extract_mtb_key,
)

DEFAULT_CREDENTIALS = "~/.config/morning-briefing/credentials.json"
DEFAULT_TOKEN = "~/.config/morning-briefing/token.json"

# Order matters: route lane name → label used in --dry-run output.
LANES = ("macro_events", "earnings", "my_positions", "market_updates")


def _parse_config_sections(text: str, *section_names: str) -> dict[str, dict[str, str]]:
    """Pull named top-level sections out of a YAML-ish config.

    Mirrors the stdlib-only parser pattern in compose_brief.py and
    check_alerts.py — PyYAML is intentionally not a runtime dep. Handles
    only string-valued leaves under named top-level sections (the only
    shape we need). Top-level scalars, list items (`- foo`), and deeper
    nesting are ignored.
    """
    wanted = set(section_names)
    out: dict[str, dict[str, str]] = {s: {} for s in wanted}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            key, _, _ = line.partition(":")
            current = key.strip() if key.strip() in wanted else None
            continue
        if current and ":" in line:
            k, _, v = line.strip().partition(":")
            v = v.strip().split("#", 1)[0].strip().strip('"').strip("'")
            if k.strip() and v:
                out[current][k.strip()] = v
    return out


def _to_calendar_event(ev: dict) -> dict:
    """Convert a compose_brief.py event dict to a Google Calendar Event resource.

    Timed events: {dateTime, timeZone} pair under start/end.
    All-day events: {date} only (the API rejects timeZone for all-day).
    Drops the writer-internal fields (calendarId, dedupKey, allDay).
    """
    payload: dict[str, Any] = {
        "summary": ev["summary"],
        "description": ev.get("description", ""),
    }
    if "colorId" in ev:
        payload["colorId"] = ev["colorId"]

    if ev.get("allDay"):
        # compose_brief.py emits all-day bounds as YYYY-MM-DDT00:00:00Z; the
        # API wants bare YYYY-MM-DD under start.date / end.date.
        payload["start"] = {"date": ev["startTime"][:10]}
        payload["end"] = {"date": ev["endTime"][:10]}
    else:
        tz = ev.get("timeZone", "America/New_York")
        payload["start"] = {"dateTime": ev["startTime"], "timeZone": tz}
        payload["end"] = {"dateTime": ev["endTime"], "timeZone": tz}
    return payload


def _validate_events(events: list[dict]) -> list[str]:
    """Return a list of issues; empty list = OK.

    Catches the kind of upstream pipeline breakage that would silently
    bypass the dedup contract (and reintroduce the 2026-05-27 dupe storm).
    """
    issues: list[str] = []
    for i, ev in enumerate(events):
        if not ev.get("calendarId"):
            issues.append(f"event[{i}] missing calendarId: {ev.get('summary')!r}")
            continue
        key_marker = extract_mtb_key(ev.get("description", ""))
        if not key_marker:
            issues.append(
                f"event[{i}] description missing <!-- mtb-key: ... --> marker "
                f"({ev.get('summary')!r}) — without it, re-runs WILL duplicate."
            )
        if ev.get("dedupKey") and key_marker and ev["dedupKey"] != key_marker:
            issues.append(
                f"event[{i}] dedupKey {ev['dedupKey']!r} disagrees with "
                f"marker {key_marker!r} — the upstream stamping is broken."
            )
    return issues


def _lane_for_calendar(
    calendar_id: str, calendars_cfg: dict[str, str]
) -> str:
    """Reverse-lookup which lane a calendar ID belongs to (for log lines)."""
    for lane, cid in calendars_cfg.items():
        if cid == calendar_id:
            return lane
    return "unknown"


def _write_calendar(
    events: list[dict],
    calendars_cfg: dict[str, str],
    date_iso: str,
    credentials_path: str,
    token_path: str,
    dry_run: bool,
) -> tuple[int, int]:
    """Run the calendar upsert loop. Returns (succeeded, failed) counts.

    Per SKILL.md: a failure on one event must NOT abort the rest of the
    briefing. We log the offender and keep going.
    """
    succeeded = 0
    failed = 0

    if dry_run:
        for ev in events:
            lane = _lane_for_calendar(ev["calendarId"], calendars_cfg)
            kind = "all-day" if ev.get("allDay") else f"timed {ev['startTime']}"
            print(
                f"[DRY-RUN] calendar:{lane} upsert "
                f"{ev.get('dedupKey', '?')} ({kind}) — {ev['summary']!r}",
                file=sys.stderr,
            )
            succeeded += 1
        return succeeded, failed

    # Lazy import so --dry-run never imports the Google client libs.
    # Failure here means the user hasn't pip-installed requirements yet;
    # surface that loudly instead of hanging.
    from google_calendar_client import authenticate, upsert_event

    service = authenticate(
        credentials_path,
        token_path,
        scopes=sorted(set(CALENDAR_SCOPES) | {DRIVE_SCOPE}),
        interactive=False,
    )

    for ev in events:
        lane = _lane_for_calendar(ev["calendarId"], calendars_cfg)
        try:
            payload = _to_calendar_event(ev)
            upsert_event(
                service,
                calendar_id=ev["calendarId"],
                mtb_key=ev["dedupKey"],
                event_payload=payload,
                date_iso=date_iso,
            )
        except Exception as e:  # don't let one bad event nuke the brief
            failed += 1
            print(
                f"FAIL calendar:{lane} {ev.get('dedupKey', '?')} — "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )
        else:
            succeeded += 1
            print(
                f"OK   calendar:{lane} {ev['dedupKey']} — {ev['summary']!r}",
                file=sys.stderr,
            )
    return succeeded, failed


def _write_drive(
    md_path: Path,
    folder_id: str,
    credentials_path: str,
    token_path: str,
    dry_run: bool,
) -> bool:
    """Upload the rendered markdown. Returns True on success, False on failure."""
    content = md_path.read_text(encoding="utf-8")
    filename = md_path.name

    if dry_run:
        print(
            f"[DRY-RUN] drive upsert {filename} ({len(content)} bytes) "
            f"→ folder {folder_id!r}",
            file=sys.stderr,
        )
        return True

    from google_drive_client import authenticate as drive_authenticate
    from google_drive_client import upsert_markdown

    service = drive_authenticate(
        credentials_path,
        token_path,
        scopes=sorted(set(CALENDAR_SCOPES) | {DRIVE_SCOPE}),
        interactive=False,
    )
    try:
        result = upsert_markdown(service, folder_id, filename, content)
    except Exception as e:
        print(f"FAIL drive {filename} — {type(e).__name__}: {e}", file=sys.stderr)
        return False
    print(
        f"OK   drive {filename} → id={result.get('id')} "
        f"link={result.get('webViewLink', '?')}",
        file=sys.stderr,
    )
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Push compose_brief.py outputs to Google Calendar + Drive.",
        epilog=(
            "First-time setup: run google_calendar_client.py --authenticate. "
            "Then run this script with --dry-run once to verify the wiring "
            "before pointing at real calendars."
        ),
    )
    ap.add_argument("--config", type=Path, required=True, help="config.yaml")
    ap.add_argument(
        "--date",
        default=None,
        help="YYYY-MM-DD (defaults to today). Used to locate the briefings/ files.",
    )
    ap.add_argument(
        "--mode",
        default="morning",
        choices=["morning", "afternoon"],
        help="morning or afternoon brief.",
    )
    ap.add_argument(
        "--briefings-dir",
        type=Path,
        default=Path("briefings"),
        help="Directory containing the compose_brief.py outputs.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan; don't authenticate, don't call any Google API.",
    )
    ap.add_argument("--skip-calendar", action="store_true")
    ap.add_argument("--skip-drive", action="store_true")
    ap.add_argument(
        "--credentials",
        default=None,
        help="Override config google.credentials_path.",
    )
    ap.add_argument(
        "--token",
        default=None,
        help="Override config google.token_path.",
    )
    args = ap.parse_args()

    date_iso = args.date or date_cls.today().isoformat()
    md_path = args.briefings_dir / f"{date_iso}-{args.mode}.md"
    events_path = args.briefings_dir / f"{date_iso}-{args.mode}.events.json"

    if not md_path.exists():
        print(f"ERROR: {md_path} not found. Run compose_brief.py first.", file=sys.stderr)
        return 2
    if not events_path.exists():
        print(f"ERROR: {events_path} not found. Run compose_brief.py first.", file=sys.stderr)
        return 2

    cfg_text = args.config.read_text(encoding="utf-8") if args.config.exists() else ""
    sections = _parse_config_sections(cfg_text, "calendars", "drive", "google")
    calendars_cfg = sections["calendars"]
    drive_cfg = sections["drive"]
    google_cfg = sections["google"]

    credentials_path = (
        args.credentials or google_cfg.get("credentials_path") or DEFAULT_CREDENTIALS
    )
    token_path = args.token or google_cfg.get("token_path") or DEFAULT_TOKEN

    events: list[dict] = json.loads(events_path.read_text(encoding="utf-8"))
    issues = _validate_events(events)
    if issues:
        print(
            "events.json failed validation — refusing to write so we don't "
            "reintroduce the 2026-05-27 dupe storm:",
            file=sys.stderr,
        )
        for msg in issues:
            print(f"  - {msg}", file=sys.stderr)
        return 3

    exit_code = 0

    if args.skip_calendar:
        print("Skipping calendar (--skip-calendar).", file=sys.stderr)
    elif not events:
        print("No events in events.json — nothing to write to calendar.", file=sys.stderr)
    else:
        ok, fail = _write_calendar(
            events,
            calendars_cfg,
            date_iso=date_iso,
            credentials_path=credentials_path,
            token_path=token_path,
            dry_run=args.dry_run,
        )
        print(
            f"Calendar: {ok} succeeded, {fail} failed "
            f"({len(events)} total).",
            file=sys.stderr,
        )
        if fail:
            exit_code = 1

    if args.skip_drive:
        print("Skipping drive (--skip-drive).", file=sys.stderr)
    elif not drive_cfg.get("briefings_folder_id"):
        print(
            "WARNING: drive.briefings_folder_id not set in config — "
            "skipping Drive upload.",
            file=sys.stderr,
        )
    else:
        ok = _write_drive(
            md_path,
            folder_id=drive_cfg["briefings_folder_id"],
            credentials_path=credentials_path,
            token_path=token_path,
            dry_run=args.dry_run,
        )
        if not ok:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
