#!/usr/bin/env python3
"""Top-level composer: takes a brief_data JSON, renders the markdown brief,
and emits the calendar-events JSON for the LLM to push via the Google Calendar MCP.

Usage:
    compose_brief.py --input brief_data.json --out-dir briefings/
    compose_brief.py --input brief_data.json --dry-run     # write markdown only

Produces in --out-dir (default: ./briefings/):
    YYYY-MM-DD-{morning|afternoon}.md          # the rendered brief
    YYYY-MM-DD-{morning|afternoon}.events.json # list of calendar events to create

The events.json is consumed by the orchestrator skill, which feeds each event to
the Google Calendar MCP create_event tool. We don't call MCP from Python because
MCP tools are LLM-mediated, not direct HTTP.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from render_brief import render
from sparkline import spark_label

DEFAULT_TZ = "America/New_York"


def _et_iso(date_str: str, hhmm: str, tz: str = DEFAULT_TZ) -> str:
    """Format YYYY-MM-DD + HH:MM as ISO 8601 without zone suffix.

    The Calendar MCP create_event accepts a separate timeZone param and reads
    start/end as naive local-time ISO when timeZone is supplied.
    """
    return f"{date_str}T{hhmm}:00"


def _slug(summary: str) -> str:
    """Stable slug for dedup keys. Drops parenthetical content (volatile
    consensus / implied-move values that change between runs) so the same
    logical event maps to the same key across a morning auto-run and a later
    manual refresh."""
    s = re.sub(r"\([^)]*\)", "", summary).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48] or "item"


def _add_minutes(hhmm: str, minutes: int) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    total = h * 60 + m + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def _market_updates_digest(data: dict) -> str:
    """Compose the Market Updates all-day digest body from existing brief_data
    sections. This is the 'soft / narrative context' lane: snapshot + must-reads,
    overnight wrap, energy/commodity catalysts, pre-market movers, and the
    geopolitical wrap. Every part is conditional so the digest degrades cleanly
    when run early (no movers) or without geo."""
    snap = data.get("snapshot", {})
    parts: list[str] = [f"# Market Updates — {data.get('date', '')}".rstrip()]

    snap_line = " | ".join(
        f"{label} {snap[key]}"
        for label, key in [("SPY", "spy"), ("DXY", "dxy"), ("10Y", "us10y"), ("VIX", "vix")]
        if snap.get(key)
    )
    if snap_line:
        parts.append(f"\n**Snapshot:** {snap_line}")

    must = data.get("must_read", [])
    if must:
        parts.append("\n**Must-read:**")
        parts.extend(f"{i}. {item}" for i, item in enumerate(must, 1))

    on = data.get("overnight", {})
    if on:
        asia = " / ".join(
            f"{lbl} {on[k]}" for lbl, k in [("Nikkei", "nikkei"), ("HSI", "hsi"), ("KOSPI", "kospi")] if on.get(k)
        )
        eur = " / ".join(
            f"{lbl} {on[k]}" for lbl, k in [("DAX", "dax"), ("FTSE", "ftse"), ("STOXX", "stoxx")] if on.get(k)
        )
        wrap = "; ".join(p for p in [f"Asia — {asia}" if asia else "", f"Europe — {eur}" if eur else ""] if p)
        if wrap:
            parts.append(f"\n**Overnight:** {wrap}")
        if on.get("top_headline"):
            parts.append(on["top_headline"])

    energy_bits = []
    if data.get("eia_opec_today"):
        energy_bits.append(data["eia_opec_today"])
    for c in data.get("commodities", []):
        if c.get("catalyst"):
            energy_bits.append(f"{c.get('ticker', '?')} ({c.get('chg', '—')}): {c['catalyst']}")
    if energy_bits:
        parts.append("\n**Energy / commodity catalysts:** " + " | ".join(energy_bits))

    movers = data.get("premarket_movers", [])
    if movers:
        rendered = ", ".join(
            f"{m.get('ticker', '?')} {m.get('change', '—')} ({m.get('catalyst', '')})".strip()
            for m in movers
        )
        parts.append(f"\n**Pre-market movers:** {rendered}")

    trends = data.get("trends", {})
    if trends:
        spark_bits = []
        for key, lbl, unit in [("spy", "SPY", ""), ("qqq", "QQQ", ""), ("us10y", "10Y", "%"), ("vix", "VIX", "")]:
            if trends.get(key):
                sl = spark_label(lbl, trends[key], unit=unit)
                if sl:
                    spark_bits.append(sl)
        if spark_bits:
            parts.append("\n**Trends:** " + "  ·  ".join(spark_bits))

    news_bits = []
    if data.get("rates_news"):
        news_bits.append(f"Bonds — {data['rates_news']}")
    if data.get("commodities_news"):
        news_bits.append(f"Commodities — {data['commodities_news']}")
    if news_bits:
        parts.append("\n**Bonds & commodities news:** " + " | ".join(news_bits))

    if data.get("geopolitical_summary"):
        parts.append(f"\n**Geopolitical:** {data['geopolitical_summary']}")

    return "\n".join(parts).strip()


def build_calendar_events(data: dict, calendars: dict) -> list[dict]:
    """Return list of events ready to feed to create_event MCP calls.

    Each event: {calendarId, summary, startTime, endTime, timeZone,
                 description, color hint}.
    """
    events: list[dict] = []
    date_str = data.get("date") or date.today().isoformat()
    mode = data.get("mode", "morning")

    # 1. Timed events for each econ release on Macro Events calendar
    macro_id = calendars.get("macro_events")
    if macro_id and mode == "morning":
        for r in data.get("econ_releases", []):
            time_et = r.get("time_et", "08:30")
            end_et = _add_minutes(time_et, 15)
            body_parts = [
                f"**Consensus:** {r.get('consensus', 'n/a')} | **Prior:** {r.get('prior', 'n/a')}",
                "",
            ]
            for label, key in [
                ("What", "what"),
                ("How measured", "how_measured"),
                ("Why it matters", "why_matters"),
                ("Reaction history", "reaction_history"),
                ("Watch for today", "watch_for_today"),
            ]:
                if r.get(key):
                    body_parts.append(f"**{label}:** {r[key]}")
                    body_parts.append("")
            events.append(
                {
                    "calendarId": macro_id,
                    "summary": f"{r.get('name', 'Econ release')} (consensus {r.get('consensus', 'n/a')})",
                    "startTime": _et_iso(date_str, time_et),
                    "endTime": _et_iso(date_str, end_et),
                    "timeZone": DEFAULT_TZ,
                    "description": "\n".join(body_parts).strip(),
                    "colorId": "7",  # Peacock blue
                }
            )

        for s in data.get("fed_speakers", []):
            time_et = s.get("time_et", "10:00")
            end_et = _add_minutes(time_et, 30)
            events.append(
                {
                    "calendarId": macro_id,
                    "summary": f"Fed: {s.get('name', '?')} ({s.get('voter_status', '?')}) — {s.get('topic', '')}",
                    "startTime": _et_iso(date_str, time_et),
                    "endTime": _et_iso(date_str, end_et),
                    "timeZone": DEFAULT_TZ,
                    "description": f"Recent lean: {s.get('lean', 'unknown')}. Topic: {s.get('topic', '')}",
                    "colorId": "7",
                }
            )

    # 2. Earnings events on Earnings calendar.
    # Dedupe by ticker, preferring my_positions entries (richer: position + hedge).
    earn_id = calendars.get("earnings")
    if earn_id and mode == "morning":
        earn = data.get("earnings_today", {})
        merged: dict[str, dict] = {}
        for e in earn.get("megacaps", []):
            t = e.get("ticker")
            if t:
                merged[t] = e
        for e in earn.get("my_positions", []):
            t = e.get("ticker")
            if t:
                merged[t] = e  # overwrites megacap entry if same ticker
        for e in merged.values():
            timing = e.get("timing", "BMO")
            time_et = "08:00" if timing == "BMO" else "16:15"
            end_et = _add_minutes(time_et, 30)
            body = [
                f"**Timing:** {timing}",
                f"**EPS estimate:** {e.get('eps_est', '?')}",
                f"**Revenue estimate:** {e.get('rev_est', '?')}",
                f"**Implied move from IV:** {e.get('implied_move', '?')}%",
            ]
            if e.get("position_summary"):
                body.append(f"**Your exposure:** {e['position_summary']} (delta {e.get('delta', '?')})")
            if e.get("hedge_recommendation"):
                body.append(f"**Recommendation:** {e['hedge_recommendation']}")
            events.append(
                {
                    "calendarId": earn_id,
                    "summary": f"{e.get('ticker', '?')} earnings — {timing} (implied {e.get('implied_move', '?')}%)",
                    "startTime": _et_iso(date_str, time_et),
                    "endTime": _et_iso(date_str, end_et),
                    "timeZone": DEFAULT_TZ,
                    "description": "\n".join(body),
                    "colorId": "6",  # Tangerine
                }
            )

    # 3. All-day summary event on My Positions calendar
    pos_id = calendars.get("my_positions")
    if pos_id:
        summary = "Morning Brief" if mode == "morning" else "Afternoon Brief"
        # All-day events need midnight start, next-day midnight end, both UTC.
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        nxt = d.fromordinal(d.toordinal() + 1)
        events.append(
            {
                "calendarId": pos_id,
                "summary": summary,
                "startTime": f"{d.isoformat()}T00:00:00Z",
                "endTime": f"{nxt.isoformat()}T00:00:00Z",
                "timeZone": DEFAULT_TZ,
                "allDay": True,
                "description": render(data)[:8000],  # Calendar event body cap
                "colorId": "11",  # Tomato
            }
        )

    # 4. All-day Market Updates digest (soft / narrative context lane).
    # Morning only; bundles snapshot + must-reads + overnight + energy + movers + geo.
    mu_id = calendars.get("market_updates")
    if mu_id and mode == "morning":
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        nxt = d.fromordinal(d.toordinal() + 1)
        events.append(
            {
                "calendarId": mu_id,
                "summary": "Market Updates",
                "startTime": f"{d.isoformat()}T00:00:00Z",
                "endTime": f"{nxt.isoformat()}T00:00:00Z",
                "timeZone": DEFAULT_TZ,
                "allDay": True,
                "description": _market_updates_digest(data)[:8000],
                "colorId": "9",  # Blueberry
            }
        )

    # Finalize: stamp each event with a stable dedup key + embed it as a hidden
    # HTML comment in the description. The orchestrator upserts by searching the
    # day's events for the "mtb-key" marker — update_event if found, else create.
    # This makes re-runs (manual news refresh after the auto-run) idempotent.
    lane_by_id = {v: k for k, v in calendars.items()}
    for ev in events:
        lane = lane_by_id.get(ev["calendarId"], "event")
        key = f"mtb:{date_str}:{lane}:{_slug(ev['summary'])}"
        ev["dedupKey"] = key
        ev["description"] = f"{ev['description']}\n\n<!-- mtb-key: {key} -->"

    return events


def _config_calendars(config_path: Path) -> dict:
    """Pull calendars: section from config.yaml. Stdlib YAML-lite."""
    if not config_path.exists():
        return {}
    out: dict[str, str] = {}
    in_cal = False
    for raw in config_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("calendars:"):
            in_cal = True
            continue
        if in_cal:
            if line and not line.startswith((" ", "\t")):
                in_cal = False
            elif ":" in line:
                k, v = line.strip().split(":", 1)
                v = v.strip().split("#", 1)[0].strip().strip('"').strip("'")
                if v:
                    out[k.strip()] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True, help="brief_data.json")
    ap.add_argument("--config", type=Path, help="config.yaml for calendar IDs")
    ap.add_argument("--out-dir", type=Path, default=Path("briefings"))
    ap.add_argument("--dry-run", action="store_true", help="Don't write events.json — markdown only")
    args = ap.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    md = render(data)

    date_str = data.get("date") or date.today().isoformat()
    mode = data.get("mode", "morning")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    md_path = args.out_dir / f"{date_str}-{mode}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Wrote {md_path}", file=sys.stderr)

    if args.dry_run:
        print(f"Dry-run: skipping events.json. Markdown is {len(md)} bytes.", file=sys.stderr)
        return 0

    calendars = _config_calendars(args.config) if args.config else {}
    if not calendars:
        print(
            "WARNING: no calendar IDs in config — events.json will be empty. "
            "Edit config.yaml first.",
            file=sys.stderr,
        )

    events = build_calendar_events(data, calendars)
    events_path = args.out_dir / f"{date_str}-{mode}.events.json"
    events_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(f"Wrote {events_path} ({len(events)} events)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
