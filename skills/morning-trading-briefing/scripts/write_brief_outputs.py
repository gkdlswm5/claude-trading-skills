#!/usr/bin/env python3
"""Deterministic write step for the morning-trading-briefing (v2.0).

Reads a brief_data.json (the LLM/Python boundary), renders the markdown and
builds the calendar events with the existing deterministic helpers, then writes
them directly to Google Calendar + Drive via the API clients. No LLM and no MCP
in the write loop — this is the rail that fixes the duplicate-event bug.

Usage:
    write_brief_outputs.py --input brief_data.json --config config.yaml
    write_brief_outputs.py --input brief_data.json --config config.yaml --dry-run
    write_brief_outputs.py --input brief_data.json --config config.yaml --skip-drive

Credentials default to ~/.config/morning-briefing/{credentials,token}.json
(override with --credentials/--token or the MTB_CONFIG_DIR env var). See
references/GOOGLE_API_SETUP.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compose_brief import _config_calendars, build_calendar_events  # noqa: E402
from render_brief import render  # noqa: E402


def _config_drive(config_path: Path) -> dict:
    """Pull the drive: block from config.yaml (stdlib YAML-lite, same approach
    as compose_brief._config_calendars)."""
    if not config_path or not config_path.exists():
        return {}
    out: dict[str, str] = {}
    in_drive = False
    for raw in config_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("drive:"):
            in_drive = True
            continue
        if in_drive:
            if line and not line.startswith((" ", "\t")):
                in_drive = False
            elif ":" in line:
                k, v = line.strip().split(":", 1)
                v = v.strip().split("#", 1)[0].strip().strip('"').strip("'")
                if v:
                    out[k.strip()] = v
    return out


def _drive_filename(drive_cfg: dict, date_str: str, mode: str) -> str:
    """Resolve the canonical Drive filename from config.filename_pattern.

    Pattern default: "briefings/{date}-{mode}.md". Only the basename is used as
    the Drive file name (Drive has no nested path semantics here)."""
    pattern = drive_cfg.get("filename_pattern", "briefings/{date}-{mode}.md")
    return Path(pattern.format(date=date_str, mode=mode)).name


def write_outputs(
    data: dict,
    *,
    calendars: dict,
    drive_cfg: dict,
    out_dir: Path,
    credentials_path: str,
    token_path: str,
    dry_run: bool = False,
    skip_calendar: bool = False,
    skip_drive: bool = False,
) -> dict:
    """Render + build events, write a local markdown archive, and (unless dry-run)
    upsert to Calendar/Drive. Returns a summary dict."""
    date_str = data.get("date") or date.today().isoformat()
    mode = data.get("mode", "morning")

    md = render(data)
    events = build_calendar_events(data, calendars)

    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{date_str}-{mode}.md"
    md_path.write_text(md, encoding="utf-8")
    events_path = out_dir / f"{date_str}-{mode}.events.json"
    events_path.write_text(json.dumps(events, indent=2), encoding="utf-8")

    summary: dict = {
        "date": date_str,
        "mode": mode,
        "markdown_path": str(md_path),
        "markdown_bytes": len(md.encode("utf-8")),
        "events_total": len(events),
        "calendar": {"written": 0, "skipped": skip_calendar, "errors": []},
        "drive": {"written": False, "skipped": skip_drive, "error": None},
        "dry_run": dry_run,
    }

    if dry_run:
        return summary

    # ---- Calendar: upsert each event by its embedded mtb-key ----
    if not skip_calendar and events:
        if not calendars:
            summary["calendar"]["errors"].append("no calendar IDs in config")
        else:
            import google_calendar_client as gcal

            cal_service = gcal.authenticate(credentials_path, token_path)
            for ev in events:
                try:
                    gcal.upsert_event(
                        cal_service,
                        ev["calendarId"],
                        ev["dedupKey"],
                        ev,
                        date_str,
                    )
                    summary["calendar"]["written"] += 1
                except Exception as exc:  # one bad event must not abort the rest
                    summary["calendar"]["errors"].append(
                        f"{ev.get('dedupKey', '?')}: {exc}"
                    )
                    print(f"WARN calendar upsert failed: {exc}", file=sys.stderr)

    # ---- Drive: overwrite the canonical per-day markdown ----
    folder_id = drive_cfg.get("briefings_folder_id")
    if not skip_drive:
        if not folder_id:
            summary["drive"]["error"] = "no drive.briefings_folder_id in config"
        else:
            try:
                import google_drive_client as gdrive

                drive_service = gdrive.authenticate(credentials_path, token_path)
                filename = _drive_filename(drive_cfg, date_str, mode)
                gdrive.upsert_markdown(drive_service, folder_id, filename, md)
                summary["drive"]["written"] = True
            except Exception as exc:
                summary["drive"]["error"] = str(exc)
                print(f"WARN drive upload failed: {exc}", file=sys.stderr)

    return summary


def _print_summary(s: dict) -> None:
    label = "Morning Brief" if s["mode"] == "morning" else "Afternoon Brief"
    kb = s["markdown_bytes"] / 1024
    print(f"{label} written: {s['markdown_path']} ({kb:.1f}KB)", file=sys.stderr)
    if s["dry_run"]:
        print(f"  Dry-run: {s['events_total']} events composed, nothing written.", file=sys.stderr)
        return
    cal = s["calendar"]
    if cal["skipped"]:
        print("  Calendar: skipped", file=sys.stderr)
    else:
        print(f"  Calendar events upserted: {cal['written']}/{s['events_total']}", file=sys.stderr)
        for err in cal["errors"]:
            print(f"    ERROR: {err}", file=sys.stderr)
    dr = s["drive"]
    if dr["skipped"]:
        print("  Drive: skipped", file=sys.stderr)
    elif dr["written"]:
        print("  Drive: markdown uploaded (canonical overwrite)", file=sys.stderr)
    else:
        print(f"  Drive: NOT written ({dr['error']})", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    from google_oauth import DEFAULT_CREDENTIALS_PATH, DEFAULT_TOKEN_PATH

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True, help="brief_data.json")
    ap.add_argument("--config", type=Path, help="config.yaml (calendar IDs + drive folder)")
    ap.add_argument("--out-dir", type=Path, default=Path("briefings"))
    ap.add_argument("--credentials", default=DEFAULT_CREDENTIALS_PATH)
    ap.add_argument("--token", default=DEFAULT_TOKEN_PATH)
    ap.add_argument("--dry-run", action="store_true", help="Compose + write local md only; no Google calls")
    ap.add_argument("--skip-calendar", action="store_true")
    ap.add_argument("--skip-drive", action="store_true")
    args = ap.parse_args(argv)

    data = json.loads(args.input.read_text(encoding="utf-8"))
    calendars = _config_calendars(args.config) if args.config else {}
    drive_cfg = _config_drive(args.config) if args.config else {}

    if not args.dry_run and not calendars and not args.skip_calendar:
        print(
            "WARNING: no calendar IDs in config — calendar writes will be skipped. "
            "Fill calendars: in config.yaml (see references/GOOGLE_API_SETUP.md).",
            file=sys.stderr,
        )

    summary = write_outputs(
        data,
        calendars=calendars,
        drive_cfg=drive_cfg,
        out_dir=args.out_dir,
        credentials_path=args.credentials,
        token_path=args.token,
        dry_run=args.dry_run,
        skip_calendar=args.skip_calendar,
        skip_drive=args.skip_drive,
    )
    _print_summary(summary)

    # Non-zero exit if a requested write path produced an error.
    failed = bool(summary["calendar"]["errors"]) or (
        not summary["drive"]["skipped"]
        and not summary["drive"]["written"]
        and not summary["dry_run"]
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
