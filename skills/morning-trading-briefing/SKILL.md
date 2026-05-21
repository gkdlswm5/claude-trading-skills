---
name: morning-trading-briefing
description: Two-times-daily trading briefing (7am pre-open + 3:30pm afternoon). Personalized to IB portfolio + market-wide. Covers macro events with full "why it matters" context, earnings with implied moves, position action items, and fresh setups. Writes timed events to Google Calendar sub-calendars (Macro Events / Earnings / My Positions) and archives markdown to Google Drive. Use when invoked by /morning-brief or /afternoon-brief commands.
---

# Morning Trading Briefing

Produces personalized pre-open and afternoon briefings for stocks, options, rates, commodities, and FX. Briefing content is driven by `config.yaml` (watchlist, thresholds, calendar IDs) so the user can iterate on what gets surfaced without code changes.

## Invocation

Called by:
- `/morning-brief` — mode=morning
- `/afternoon-brief` — mode=afternoon

Both load config from `skills/morning-trading-briefing/config.yaml` (user-edited copy of `config.example.yaml`).

## Sections (morning mode)

1. **Must-read top 3** — the 3 highest-impact items for today (synthesized last, shown first)
2. **Macro day-ahead** (market-wide)
   - Today's economic releases (with full "what / how measured / market reaction history" blurb from `econ-indicator-explainer` skill)
   - Fed speakers on the docket
   - Overnight: Asia close, Europe open
   - Rates snapshot: 2Y/10Y/30Y, 2s10s, real yields, Fed funds futures path
   - Commodities: WTI, Brent, gold, copper, nat gas + EIA/OPEC days
   - FX: DXY, EUR/USD, USD/JPY + BTC/ETH levels
   - Sector ETF pre-market (XLF, XLE, XLK, XLI, XLV)
   - Pre-market movers w/ catalysts
3. **Earnings today**
   - Mega-caps reporting (always shown)
   - Your positions reporting: date, BMO/AMC, EPS est, implied move from IV, current delta, hedge recommendation
4. **My positions** (personalized from IB)
   - Overnight P&L per position
   - Stop-loss alerts (positions near/breached triggers)
   - Short legs needing roll attention
   - News + unusual options flow on holdings
   - Earnings within 7 days on holdings
5. **Opportunities**
   - Top 3 from scanner-bullish
   - Top 3 from scanner-pmcc
   - Notable insider buying

## Sections (afternoon mode)

1. **Today's recap** — SPY/QQQ/DXY/10Y/oil close, your P&L, what moved & why, biggest position movers
2. **Closing-bell positioning** — any final adjustments for the last 30 minutes of trading
3. **Overnight risks** — Asia data on the docket, AMC earnings on your tickers, geopolitical events
4. **Tomorrow's setup** — econ releases, Fed speakers, earnings, key levels to watch

## Macro section pipeline (uses econ-indicator-explainer)

For today's economic releases:

```
1. economic-calendar-fetcher → list of FMP events for today (US + global filtered by config)
2. For each event:
   a. lookup_indicator.py --json "<event.event_name>"
   b. If matched: render full card (what / how / why / reaction / watch-for)
   c. If unmatched: render minimal card + log to state/unmapped_indicators.log
3. Render fed-speakers section separately (not in indicators KB — they're people, not data)
```

The indicator card already contains `## Reaction history` and `## Watch for today` — those flow straight into the brief and the Calendar event description.

## Skill dependencies

See `references/SKILLS_INVENTORY.md` for the full mapping. High-level:

- IB positions / P&L → `ib-portfolio`, `ib-portfolio-action-report`
- Stops + rolls + PMCC → `ib-stop-loss`, `ib-find-short-roll`, `ib-pmcc-advisor`
- Earnings → `earnings-calendar` + `earnings-trade-analyzer` + `greeks` for implied move
- News / sentiment → `news-sentiment` + `market-news-analyst`
- Macro events → `economic-calendar-fetcher` + `econ-indicator-explainer` ✅ (step A complete)
- Sector rotation / breadth → `sector-analyst`, `market-breadth-analyzer`
- Setups → `scanner-bullish`, `scanner-pmcc`, `whale-hunting`, `insider-trading`
- Calendar write → Google Calendar MCP
- Drive archive → Google Drive MCP

## Output destinations

- **Macro Events calendar** — timed events at release time (e.g. 8:30am CPI, 2pm FOMC); body = full indicator blurb + consensus + your watch points
- **Earnings calendar** — timed events at BMO (8am) or AMC (4:15pm); body = EPS est, revenue est, implied move, exposure if any
- **My Positions calendar** — single all-day event ("Morning Brief" / "Afternoon Brief") with full briefing in description
- **Google Drive** — `briefings/YYYY-MM-DD-morning.md` and `briefings/YYYY-MM-DD-afternoon.md`

## Status

- STEP C complete: scaffolding, config, templates, calendar setup docs, skills inventory.
- STEP A complete: `econ-indicator-explainer` skill with 30+ indicator cards + lookup script + tests.
- STEP B pending: orchestration logic that ties everything together and renders the brief.

Do not invoke for real use until Step B is complete.
