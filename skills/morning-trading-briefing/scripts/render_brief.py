#!/usr/bin/env python3
"""Render a briefing markdown file from a structured JSON input.

Usage:
    render_brief.py --input brief_data.json [--output brief.md]
    cat brief_data.json | render_brief.py --stdin

The input JSON schema is documented in references/BRIEF_DATA_SCHEMA.md.
Mode is determined by the "mode" field in the input ("morning" | "afternoon").

This is the deterministic half of step B — given a fully-assembled brief_data
dict, produce the markdown. Section assembly (calling sub-skills, synthesizing
the "must-read top 3", etc.) happens upstream in the orchestrator skill.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from event_filters import filter_releases, impact_rank, impact_tag
from sparkline import spark_label


def _bold_tickers(text: str, tickers: list[str]) -> str:
    """Bold whole-word ticker occurrences so position-relevant items pop."""
    if not text or not tickers:
        return text
    for t in sorted({t for t in tickers if t}, key=len, reverse=True):
        text = re.sub(rf"(?<![\w*]){re.escape(t)}(?![\w*])", f"**{t}**", text)
    return text


def _get(d: dict, *keys: str, default: Any = "—") -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur not in (None, "") else default


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_no data_\n"
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out) + "\n"


def render_morning(d: dict) -> str:
    lines: list[str] = []
    snap = d.get("snapshot", {})

    lines.append(f"# Morning Brief — {_get(d, 'date')}")
    lines.append(
        f"*Generated {_get(d, 'generated_at_et')} — "
        f"SPY {_get(snap, 'spy')} ({_get(snap, 'spy_premarket')}) | "
        f"DXY {_get(snap, 'dxy')} | "
        f"10Y {_get(snap, 'us10y')} | "
        f"VIX {_get(snap, 'vix')}*"
    )
    lines.append("")

    tickers = d.get("watchlist", [])

    if d.get("bottom_line"):
        lines.append(f"**Bottom line:** {_bold_tickers(d['bottom_line'], tickers)}")
        lines.append("")

    regime = d.get("risk_regime")
    if regime and regime.get("label"):
        lines.append(f"**Regime:** {regime['label']} — {regime.get('reason', '')}")
        lines.append("")

    must = d.get("must_read", [])
    if must:
        lines.append("## Must-read today")
        for i, item in enumerate(must, 1):
            lines.append(f"{i}. {_bold_tickers(item, tickers)}")
        lines.append("")

    lines.append("---\n")
    lines.append("## Macro day-ahead\n")

    flt = d.get("filters", {})
    releases = filter_releases(
        d.get("econ_releases", []), drop_minor=flt.get("drop_minor_econ", True)
    )
    if releases:
        lines.append("### Economic releases\n")
        if not any(impact_rank(r.get("impact")) >= 2 for r in releases):
            lines.append("_Light macro day — no high-impact releases scheduled._\n")
        for r in releases:
            tag = impact_tag(r.get("impact"))
            tag_str = f"{tag} " if tag else ""
            lines.append(
                f"**{tag_str}{r.get('time_et', '?')} ET — {r.get('name', '?')}** "
                f"*(consensus {r.get('consensus', 'n/a')} | "
                f"prior {r.get('prior', 'n/a')})*\n"
            )
            for label, key in [
                ("What", "what"),
                ("How measured", "how_measured"),
                ("Why it matters", "why_matters"),
                ("Reaction history", "reaction_history"),
            ]:
                val = r.get(key)
                if val:
                    lines.append(f"*{label}:* {val}\n")
            watch = r.get("watch_for_today")
            if watch:
                lines.append(f"→ *Watch:* {watch}\n")
            if r.get("eli5"):
                lines.append(f"→ *In plain English:* {r['eli5']}\n")
        lines.append("")

    speakers = d.get("fed_speakers", [])
    if speakers:
        lines.append("### Fed speakers")
        for s in speakers:
            lines.append(
                f"- **{s.get('time_et', '?')} ET** — {s.get('name', '?')} "
                f"({s.get('voter_status', '?')}, recent lean: {s.get('lean', '?')}) — "
                f"{s.get('topic', '')}"
            )
            if s.get("eli5"):
                lines.append(f"  → *In plain English:* {s['eli5']}")
        lines.append("")

    on = d.get("overnight", {})
    if on:
        lines.append("### Overnight")
        lines.append(
            f"- Asia close: Nikkei {_get(on, 'nikkei')} | HSI {_get(on, 'hsi')} | KOSPI {_get(on, 'kospi')}"
        )
        lines.append(
            f"- Europe open: DAX {_get(on, 'dax')} | FTSE {_get(on, 'ftse')} | STOXX {_get(on, 'stoxx')}"
        )
        top = on.get("top_headline")
        if top:
            lines.append(f"- Top overnight headline: {top}")
        lines.append("")

    rates = d.get("rates", {})
    if rates:
        lines.append("### Rates")
        lines.append(
            f"- 2Y {_get(rates, 'us2y')} | 10Y {_get(rates, 'us10y')} | 30Y {_get(rates, 'us30y')}"
        )
        lines.append(
            f"- 2s10s: {_get(rates, 'curve_2s10s')} bps ({_get(rates, 'curve_direction', default='')})"
        )
        lines.append(f"- Real 10Y: {_get(rates, 'real_10y')}%")
        lines.append(
            f"- Fed funds futures imply {_get(rates, 'ff_implied_path')} through "
            f"{_get(rates, 'ff_horizon')}"
        )
        trends = d.get("trends", {})
        for key, lbl in [("us2y", "2Y"), ("us10y", "10Y"), ("us30y", "30Y")]:
            if trends.get(key):
                sl = spark_label(lbl, trends[key], unit="%")
                if sl:
                    lines.append(f"- Trend: {sl}")
        if rates.get("so_what"):
            lines.append(f"→ *So what:* {rates['so_what']}")
        if d.get("rates_news"):
            lines.append(f"→ *News:* {d['rates_news']}")
        lines.append("")

    levels = d.get("key_levels", [])
    if levels:
        lines.append("### Key levels")
        lines.append(
            _table(
                ["Ticker", "Last", "50DMA", "200DMA", "20d S/R", "Trend"],
                [
                    [
                        lv.get("ticker", "?"),
                        lv.get("last", "—"),
                        lv.get("sma50", "—"),
                        lv.get("sma200", "—"),
                        f"{lv.get('support_20d', '—')}–{lv.get('resistance_20d', '—')}",
                        lv.get("trend", ""),
                    ]
                    for lv in levels
                ],
            )
        )

    comm = d.get("commodities", [])
    if comm:
        lines.append("### Commodities")
        lines.append(
            _table(
                ["Ticker", "Last", "1d%", "Catalyst"],
                [[c.get("ticker", "?"), c.get("last", "—"), c.get("chg", "—"), c.get("catalyst", "")] for c in comm],
            )
        )
        if d.get("eia_opec_today"):
            lines.append(f"*EIA/OPEC days flagged: {d['eia_opec_today']}*\n")
        if d.get("commodities_news"):
            lines.append(f"→ *News:* {d['commodities_news']}\n")

    fx = d.get("fx", {})
    if fx:
        lines.append("### FX / crypto")
        lines.append(
            f"- DXY {_get(fx, 'dxy')} ({_get(fx, 'dxy_chg')}) | "
            f"EUR/USD {_get(fx, 'eurusd')} | USD/JPY {_get(fx, 'usdjpy')}"
        )
        if fx.get("btc") or fx.get("eth"):
            lines.append(
                f"- BTC {_get(fx, 'btc')} ({_get(fx, 'btc_chg')}) | "
                f"ETH {_get(fx, 'eth')} ({_get(fx, 'eth_chg')})"
            )
        if fx.get("so_what"):
            lines.append(f"→ *So what:* {fx['so_what']}")
        lines.append("")

    sectors = d.get("sector_etfs", [])
    if sectors:
        lines.append("### Sector ETF pre-market")
        lines.append(
            _table(
                ["ETF", "Pre-market %", "Note"],
                [[s.get("ticker", "?"), s.get("chg", "—"), s.get("note", "")] for s in sectors],
            )
        )
        if d.get("rotation_read"):
            lines.append(f"→ *Rotation read:* {d['rotation_read']}\n")

    charts = d.get("charts", [])
    if charts:
        lines.append("### Trend charts")
        for c in charts:
            title = c.get("title", c.get("group", "chart"))
            ref = c.get("url") or c.get("path", "")
            lines.append(f"- [{title}]({ref})")
        lines.append("")

    movers = d.get("premarket_movers", [])
    if movers:
        lines.append("### Pre-market movers")
        for m in movers:
            lines.append(
                f"- **{m.get('ticker', '?')}** {m.get('change', '—')} — {m.get('catalyst', '')}"
            )
        lines.append("")

    geo = d.get("geopolitical_summary")
    if geo:
        lines.append("### Geopolitical")
        lines.append(geo)
        lines.append("")

    earn = d.get("earnings_today", {})
    if earn.get("megacaps") or earn.get("my_positions"):
        lines.append("---\n")
        lines.append("## Earnings today\n")
        mc = earn.get("megacaps", [])
        if mc:
            lines.append("### Mega-caps reporting")
            for e in mc:
                lines.append(
                    f"**{e.get('ticker')} — {e.get('timing', '?')}** | "
                    f"EPS est {e.get('eps_est', '?')} | "
                    f"Rev est {e.get('rev_est', '?')} — implied move {e.get('implied_move', '?')}%"
                )
            lines.append("")
        mp = earn.get("my_positions", [])
        if mp:
            lines.append("### Your positions reporting")
            for e in mp:
                lines.append(f"**{e.get('ticker')} — {e.get('timing', '?')}**")
                lines.append(f"- EPS est: {e.get('eps_est', '?')} | Rev est: {e.get('rev_est', '?')}")
                lines.append(f"- Implied move from IV: {e.get('implied_move', '?')}%")
                lines.append(
                    f"- Your exposure: {e.get('position_summary', '?')} "
                    f"(delta {e.get('delta', '?')})"
                )
                if e.get("hedge_recommendation"):
                    lines.append(f"- Recommendation: {e['hedge_recommendation']}")
                lines.append("")

    pos = d.get("my_positions", {})
    if pos:
        lines.append("---\n")
        lines.append("## My positions\n")
        pnl = pos.get("pnl_rows", [])
        if pnl:
            lines.append("### Overnight P&L")
            lines.append(
                _table(
                    ["Ticker", "Qty", "Value", "Overnight P&L"],
                    [
                        [r.get("ticker", "?"), r.get("qty", "—"), r.get("value", "—"), r.get("pnl_overnight", "—")]
                        for r in pnl
                    ],
                )
            )

        stops = pos.get("stop_alerts", [])
        if stops:
            lines.append("### Stop-loss alerts")
            for s in stops:
                lines.append(
                    f"- **{s.get('ticker', '?')}** — closed {s.get('last', '?')} "
                    f"vs. stop {s.get('stop_price', '?')} "
                    f"({s.get('distance_pct', '?')}% away) — {s.get('action', '')}"
                )
            lines.append("")

        legs = pos.get("short_leg_alerts", [])
        if legs:
            lines.append("### Short legs needing attention")
            for s in legs:
                rolls = s.get("roll_top_3", [])
                rolls_str = ", ".join(rolls) if isinstance(rolls, list) else str(rolls)
                lines.append(
                    f"- **{s.get('symbol', '?')}** — delta {s.get('delta', '?')} | "
                    f"DTE {s.get('dte', '?')} | {s.get('reason', '')} — "
                    f"roll candidates: {rolls_str}"
                )
            lines.append("")

        events = pos.get("holding_events", [])
        if events:
            lines.append("### News + unusual options flow on holdings")
            for e in events:
                lines.append(
                    f"- **{e.get('ticker', '?')}** — {e.get('event_type', '?')} — {e.get('summary', '')}"
                )
            lines.append("")

        ue = pos.get("upcoming_earnings", [])
        if ue:
            lines.append("### Earnings within 7 days on holdings")
            for e in ue:
                lines.append(
                    f"- **{e.get('ticker', '?')}** — {e.get('date', '?')} {e.get('timing', '')} — "
                    f"implied move {e.get('implied_move', '?')}% — consider: {e.get('prep_action', '')}"
                )
            lines.append("")

    opp = d.get("opportunities", {})
    if opp:
        lines.append("---\n")
        lines.append("## Opportunities\n")
        sb = opp.get("scanner_bullish", [])
        if sb:
            lines.append("### Scanner-bullish top 3")
            for s in sb:
                lines.append(f"- **{s.get('ticker', '?')}** — {s.get('rationale', '')}")
            lines.append("")
        sp = opp.get("scanner_pmcc", [])
        if sp:
            lines.append("### Scanner-PMCC top 3")
            for s in sp:
                lines.append(f"- **{s.get('ticker', '?')}** — {s.get('rationale', '')}")
            lines.append("")
        ib = opp.get("insider_buys", [])
        if ib:
            lines.append("### Notable insider buying")
            for s in ib:
                lines.append(
                    f"- **{s.get('ticker', '?')}** — {s.get('insider_name', '?')} "
                    f"({s.get('title', '')}) bought ${s.get('value', '?')} on {s.get('date', '?')}"
                )
            lines.append("")

    if d.get("noise_log_path"):
        lines.append("---")
        lines.append(
            f"*Noise log: {d['noise_log_path']} — jot one line after market close on "
            "what was missing or unused.*"
        )

    return "\n".join(lines) + "\n"


def render_afternoon(d: dict) -> str:
    lines: list[str] = []
    snap = d.get("snapshot", {})

    lines.append(f"# Afternoon Brief — {_get(d, 'date')}")
    lines.append(
        f"*Generated {_get(d, 'generated_at_et')} — "
        f"SPY {_get(snap, 'spy_close')} ({_get(snap, 'spy_chg')}) | "
        f"DXY {_get(snap, 'dxy_close')} | "
        f"10Y {_get(snap, 'us10y_close')} | "
        f"VIX {_get(snap, 'vix_close')}*"
    )
    lines.append("")

    lines.append("## Today's recap\n")

    moves = d.get("market_moves", [])
    if moves:
        lines.append("### What moved & why")
        for m in moves:
            lines.append(f"- **{m.get('topic', '?')}**: {m.get('summary', '')}")
        lines.append("")

    pnl = d.get("pnl_recap", {})
    if pnl:
        lines.append("### Your P&L")
        rows = pnl.get("rows", [])
        if rows:
            lines.append(
                _table(
                    ["Ticker", "Day P&L", "Day %"],
                    [
                        [r.get("ticker", "?"), r.get("day_pnl", "—"), r.get("day_pct", "—")]
                        for r in rows
                    ],
                )
            )
        lines.append(
            f"*Day P&L: {_get(pnl, 'day_pnl')} | Week P&L: {_get(pnl, 'week_pnl')} | "
            f"YTD: {_get(pnl, 'ytd_pnl')}*"
        )
        lines.append("")

    movers = d.get("my_top_movers", [])
    if movers:
        lines.append("### Biggest position movers")
        for m in movers:
            lines.append(
                f"- **{m.get('ticker', '?')}** {m.get('change', '—')} — {m.get('driver', '')}"
            )
        lines.append("")

    if d.get("closing_bell_actions"):
        lines.append("---\n")
        lines.append(
            f"## Closing-bell positioning ({_get(d, 'minutes_to_close')} min to close)\n"
        )
        lines.append(d["closing_bell_actions"])
        lines.append("")

    lines.append("---\n")
    lines.append("## Overnight risks\n")

    asia = d.get("asia_releases", [])
    if asia:
        lines.append("### Asia data on the docket")
        for r in asia:
            lines.append(
                f"- **{r.get('time_et', '?')} ET — {r.get('name', '?')}** "
                f"(consensus {r.get('consensus', 'n/a')}) — {r.get('impact', '')}"
            )
        lines.append("")

    amc = d.get("amc_earnings", [])
    if amc:
        lines.append("### AMC earnings on your tickers")
        for e in amc:
            lines.append(
                f"- **{e.get('ticker', '?')}** — EPS est {e.get('eps_est', '?')} | "
                f"implied move {e.get('implied_move', '?')}% — "
                f"exposure: {e.get('position_summary', '?')}"
            )
        lines.append("")

    if d.get("geopolitical_summary"):
        lines.append("### Geopolitical / policy headlines")
        lines.append(d["geopolitical_summary"])
        lines.append("")

    lines.append("---\n")
    lines.append("## Tomorrow's setup\n")

    te = d.get("tomorrow_econ", [])
    if te:
        lines.append("### Econ calendar")
        lines.append(
            _table(
                ["Time ET", "Event", "Consensus", "Prior"],
                [
                    [r.get("time_et", "?"), r.get("name", "?"), r.get("consensus", "n/a"), r.get("prior", "n/a")]
                    for r in te
                ],
            )
        )

    tfs = d.get("tomorrow_fed_speakers", [])
    if tfs:
        lines.append("### Fed speakers tomorrow")
        for s in tfs:
            lines.append(
                f"- **{s.get('time_et', '?')} ET** — {s.get('name', '?')} "
                f"({s.get('voter_status', '?')})"
            )
        lines.append("")

    tearn = d.get("tomorrow_earnings", [])
    if tearn:
        lines.append("### Earnings tomorrow (mega-caps + your tickers)")
        lines.append(
            _table(
                ["Ticker", "Timing", "EPS est", "Implied move"],
                [
                    [r.get("ticker", "?"), r.get("timing", "?"), r.get("eps_est", "?"), r.get("implied_move", "?")]
                    for r in tearn
                ],
            )
        )

    levels = d.get("key_levels", {})
    if levels:
        lines.append("### Key levels to watch")
        if levels.get("spy_support") or levels.get("spy_resistance"):
            lines.append(
                f"- SPY: support {_get(levels, 'spy_support')} / "
                f"resistance {_get(levels, 'spy_resistance')}"
            )
        if levels.get("custom"):
            lines.append(f"- {levels['custom']}")
        lines.append("")

    return "\n".join(lines) + "\n"


def render(data: dict) -> str:
    mode = data.get("mode", "morning")
    if mode == "morning":
        return render_morning(data)
    if mode == "afternoon":
        return render_afternoon(data)
    raise ValueError(f"Unknown mode: {mode}")


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", type=Path, help="JSON file path")
    src.add_argument("--stdin", action="store_true", help="Read JSON from stdin")
    ap.add_argument("--output", type=Path, help="Output markdown path (default: stdout)")
    args = ap.parse_args()

    if args.stdin:
        data = json.load(sys.stdin)
    else:
        data = json.loads(args.input.read_text(encoding="utf-8"))

    md = render(data)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(md, encoding="utf-8")
        print(f"Wrote {args.output} ({len(md)} bytes)", file=sys.stderr)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
