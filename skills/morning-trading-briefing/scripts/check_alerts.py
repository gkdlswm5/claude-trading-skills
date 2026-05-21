#!/usr/bin/env python3
"""Compute briefing alerts from IB position data + config thresholds.

Usage:
    check_alerts.py --positions positions.json --config config.yaml

Reads:
- positions.json: list of position dicts (schema in BRIEF_DATA_SCHEMA.md)
- config.yaml: full briefing config (we only read the alerts: + earnings_within_days: sections)

Writes to stdout: JSON {stop_alerts, short_leg_alerts, upcoming_earnings} ready
to drop into the brief_data my_positions section.

Pure logic — no API calls. Sub-skills fetch the raw data; this aggregates it
into the actionable items.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


def _parse_yaml_thresholds(yaml_text: str) -> dict:
    """Minimal YAML extractor for the keys we care about.

    We don't pull in PyYAML to keep stdlib-only. We only need flat
    key: value pairs under alerts: and a couple of toplevel toggles.
    """
    out: dict = {"alerts": {}, "earnings_within_days": 7}
    in_alerts = False
    for raw in yaml_text.splitlines():
        line = raw.rstrip()
        if line.startswith("alerts:"):
            in_alerts = True
            continue
        if in_alerts:
            if line and not line.startswith((" ", "\t")):
                in_alerts = False
            elif ":" in line:
                k, v = line.strip().split(":", 1)
                v = v.strip().split("#", 1)[0].strip()
                try:
                    out["alerts"][k.strip()] = float(v) if "." in v else int(v)
                except ValueError:
                    out["alerts"][k.strip()] = v
    # earnings_within_days lives under alerts in our config
    if "earnings_within_days" in out["alerts"]:
        out["earnings_within_days"] = int(out["alerts"]["earnings_within_days"])
    return out


def stop_alerts(positions: list[dict], proximity_pct: float) -> list[dict]:
    """Flag long-stock positions whose last price is within `proximity_pct`
    of stop, or has breached stop entirely."""
    alerts = []
    for p in positions:
        if p.get("asset_type") != "stock":
            continue
        last = p.get("last_price")
        stop = p.get("stop_price")
        if last is None or stop is None:
            continue
        try:
            last = float(last)
            stop = float(stop)
        except (TypeError, ValueError):
            continue
        if stop <= 0:
            continue
        distance_pct = (last - stop) / stop * 100
        if distance_pct < 0:
            action = f"STOP BREACHED — review immediately ({distance_pct:.1f}% below)"
        elif distance_pct <= proximity_pct:
            action = f"approaching stop ({distance_pct:.1f}% above)"
        else:
            continue
        alerts.append(
            {
                "ticker": p.get("ticker", "?"),
                "last": f"{last:.2f}",
                "stop_price": f"{stop:.2f}",
                "distance_pct": f"{distance_pct:.1f}",
                "action": action,
            }
        )
    return alerts


def short_leg_alerts(
    positions: list[dict],
    delta_breach: float,
    dte_threshold: int,
) -> list[dict]:
    """Flag short option legs that breach |delta| > threshold OR DTE <= threshold."""
    alerts = []
    for p in positions:
        if p.get("asset_type") not in ("option_short", "short_call", "short_put"):
            continue
        delta = p.get("delta")
        dte = p.get("dte")
        try:
            d_val = abs(float(delta)) if delta is not None else None
            dte_val = int(dte) if dte is not None else None
        except (TypeError, ValueError):
            continue

        reasons = []
        if d_val is not None and d_val > delta_breach:
            reasons.append(f"|delta|={d_val:.2f} > {delta_breach}")
        if dte_val is not None and dte_val <= dte_threshold:
            reasons.append(f"DTE={dte_val} <= {dte_threshold}")
        if not reasons:
            continue

        alerts.append(
            {
                "symbol": p.get("ticker", "?"),
                "delta": f"{d_val:.2f}" if d_val is not None else "—",
                "dte": dte_val if dte_val is not None else "—",
                "reason": "; ".join(reasons),
                "roll_top_3": p.get("roll_candidates", []),
            }
        )
    return alerts


def upcoming_earnings(
    positions: list[dict],
    earnings_calendar: list[dict],
    within_days: int,
    today: date | None = None,
) -> list[dict]:
    """Cross-reference holdings against the earnings calendar.

    earnings_calendar entries: {ticker, date (YYYY-MM-DD), timing (BMO|AMC),
    eps_est, implied_move}.
    """
    if today is None:
        today = date.today()

    # Match earnings ticker against the *underlying* of each position.
    # For option positions ("NVDA Jun20 145C"), the underlying is the first token.
    # Positions may also supply an explicit "underlying" field to override.
    held_underlyings = set()
    for p in positions:
        if p.get("underlying"):
            held_underlyings.add(p["underlying"])
        elif p.get("ticker"):
            held_underlyings.add(p["ticker"].split()[0])

    out = []
    for e in earnings_calendar:
        ticker = e.get("ticker")
        if ticker not in held_underlyings:
            continue
        try:
            edate = datetime.strptime(e.get("date", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        delta_days = (edate - today).days
        if 0 <= delta_days <= within_days:
            out.append(
                {
                    "ticker": ticker,
                    "date": e.get("date"),
                    "timing": e.get("timing", "?"),
                    "implied_move": e.get("implied_move", "?"),
                    "prep_action": _prep_action(delta_days, e.get("implied_move")),
                }
            )
    return sorted(out, key=lambda x: x["date"])


def _prep_action(days_out: int, implied_move: Any) -> str:
    try:
        im = float(implied_move) if implied_move is not None else None
    except (TypeError, ValueError):
        im = None
    if days_out <= 1:
        if im is not None and im >= 7:
            return f"high IV ({im:.1f}%) — collar or close stock leg before report"
        return "report imminent — review hedge"
    if days_out <= 3:
        return "report this week — prepare hedge plan"
    return "report next week — note on watchlist"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", type=Path, required=True, help="JSON list of positions")
    ap.add_argument("--config", type=Path, required=True, help="config.yaml")
    ap.add_argument(
        "--earnings", type=Path, help="Optional JSON list of upcoming earnings (ticker/date/timing/eps_est/implied_move)"
    )
    ap.add_argument("--today", help="Override today (YYYY-MM-DD) for deterministic tests")
    args = ap.parse_args()

    positions = json.loads(args.positions.read_text(encoding="utf-8"))
    config = _parse_yaml_thresholds(args.config.read_text(encoding="utf-8"))
    earnings = (
        json.loads(args.earnings.read_text(encoding="utf-8")) if args.earnings else []
    )

    today = (
        datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    )

    thresholds = config["alerts"]
    out = {
        "stop_alerts": stop_alerts(
            positions,
            float(thresholds.get("stop_loss_proximity_pct", 3.0)),
        ),
        "short_leg_alerts": short_leg_alerts(
            positions,
            float(thresholds.get("short_leg_delta_breach", 0.35)),
            int(thresholds.get("short_leg_dte_threshold", 14)),
        ),
        "upcoming_earnings": upcoming_earnings(
            positions,
            earnings,
            int(config.get("earnings_within_days", 7)),
            today,
        ),
    }
    json.dump(out, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
