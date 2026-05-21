---
name: morning-trading-briefing
description: Two-times-daily trading briefing (7am pre-open + 3:30pm afternoon). Personalized to IB portfolio + market-wide. Covers macro events with full "why it matters" context, earnings with implied moves, position action items, and fresh setups. Writes timed events to Google Calendar sub-calendars (Macro Events / Earnings / My Positions) and archives markdown to Google Drive. Invoked by /morning-brief or /afternoon-brief commands.
---

# Morning Trading Briefing

Produces personalized pre-open and afternoon briefings for stocks, options, rates, commodities, and FX. Content is driven by `config.yaml` so iteration happens without code changes.

## Invocation

- `/morning-brief` → `mode=morning`
- `/afternoon-brief` → `mode=afternoon`

## Pipeline overview

The skill is hybrid: Python scripts handle deterministic work (alert math, template rendering, calendar-event JSON generation); the LLM handles synthesis (assembling sub-skill outputs into `brief_data.json`, writing the "must-read top 3", calling MCP tools to write events + Drive files).

```
┌──────────────┐      ┌─────────────────┐      ┌───────────────┐
│  Sub-skills  │─────▶│  LLM assembles  │─────▶│ compose_brief │
│ (ib-*, econ- │      │ brief_data.json │      │ render +      │
│  calendar,   │      └────────┬────────┘      │ events.json   │
│  scanner, …) │               │               └───────┬───────┘
└──────────────┘               │                       │
                               ▼                       ▼
                        check_alerts.py        ┌───────────────┐
                        lookup_indicator.py    │ MCP writes:   │
                                               │  Calendar     │
                                               │  Drive        │
                                               └───────────────┘
```

## Step-by-step procedure (morning mode)

### Step 0 — Load config

Read `skills/morning-trading-briefing/config.yaml`. If it doesn't exist, halt and tell the user to copy `config.example.yaml` → `config.yaml` and fill in calendar IDs + watchlist (see `references/CALENDAR_SETUP.md`).

### Step 1 — Gather raw data (parallel where possible)

| Need | Skill / source |
|---|---|
| Today's econ events | `economic-calendar-fetcher` (FMP API, today's date range) |
| Today's earnings | `earnings-calendar` (today, filtered by config.mega_caps + watchlist + holdings) |
| IB positions | `ib-portfolio` |
| Pre-market quotes | `stock-quote` for SPY/QQQ/DXY/UUP/TLT/USO/GLD/HG=F/UNG + crypto |
| Overnight Asia/Europe | `market-news-analyst` or WebFetch on Nikkei/HSI/KOSPI/DAX/FTSE close prices |
| Rates snapshot | `stock-quote` on ^TNX (10Y), ^FVX (5Y), ^IRX (3M); FRED for real yields if needed |
| Sector ETFs | `sector-analyst` or `stock-quote` on XLF/XLE/XLK/XLI/XLV |
| Pre-market movers | `finviz-screener` (pre-market gainers/losers >$1B mcap) |
| News on holdings | `news-sentiment` per holding ticker |
| Unusual flow | `whale-hunting` per holding ticker |
| Insider buying | `insider-trading` (watchlist + holdings) |
| Fresh setups | `scanner-bullish` + `scanner-pmcc` (top 3 each) |

### Step 2 — Enrich econ events with explainer cards

For each event from `economic-calendar-fetcher`:

```bash
python3 skills/econ-indicator-explainer/scripts/lookup_indicator.py --json "<event.event>"
```

- On match: parse JSON `.sections` → populate `what`, `how_measured`, `why_matters`, `reaction_history`, `watch_for_today` on the brief_data econ_releases entry.
- On no match (exit 2): include the event with only the FMP-supplied fields, and append the unmapped name to `skills/morning-trading-briefing/state/unmapped_indicators.log` so the user can add a card later.

### Step 3 — Run alert checker

Write positions + today's earnings to temp JSON, then:

```bash
python3 skills/morning-trading-briefing/scripts/check_alerts.py \
  --positions /tmp/positions.json \
  --earnings /tmp/earnings.json \
  --config skills/morning-trading-briefing/config.yaml \
  > /tmp/alerts.json
```

Merge `stop_alerts`, `short_leg_alerts`, `upcoming_earnings` into the brief_data `my_positions` section.

### Step 4 — Assemble brief_data.json

Build the structured object matching `references/BRIEF_DATA_SCHEMA.md`. Populate:

- `snapshot`, `econ_releases`, `fed_speakers`, `overnight`, `rates`, `commodities`, `eia_opec_today`
- `fx`, `sector_etfs`, `rotation_read`, `premarket_movers`
- `earnings_today` (split mega-caps vs. my_positions)
- `my_positions` (pnl_rows + alerts from step 3 + holding_events + upcoming_earnings)
- `opportunities`

For each section that ends with a `so_what` field (rates, fx, sector rotation): write one sentence tying the data to the user's actual positions. This is the discipline that turns the brief from a data dump into actionable signal.

### Step 5 — Write the "must-read top 3" LAST

This is the most important synthesis step. After everything else is assembled, look at the entire brief_data and pick the 3 items that will materially affect today's P&L. Examples:

- "8:30 ET CPI — consensus 3.1%. Hot Core (>3.4%) tanks your TLT long and Jan26 LEAPS."
- "NVDA reports AMC, implied move 8.5%. Your short Jun20 145C has 0.42 delta — roll before close."
- "USD/JPY at 155.4 — BOJ intervention risk overnight. Could spike VIX into open."

Tight, actionable, ties to holdings. If you can't write 3 items that meet this bar, write fewer — don't fluff.

### Step 6 — Render + emit events.json

```bash
python3 skills/morning-trading-briefing/scripts/compose_brief.py \
  --input /tmp/brief_data.json \
  --config skills/morning-trading-briefing/config.yaml \
  --out-dir briefings/
```

Produces:
- `briefings/YYYY-MM-DD-morning.md` — full markdown
- `briefings/YYYY-MM-DD-morning.events.json` — list of calendar events to create

### Step 7 — Write to Google Calendar (skip if --skip-calendar or --dry-run)

Iterate `events.json` and call the Calendar MCP `create_event` for each. Map fields directly:

| events.json field | MCP param |
|---|---|
| `summary` | `summary` |
| `startTime` | `startTime` |
| `endTime` | `endTime` |
| `timeZone` | `timeZone` |
| `calendarId` | `calendarId` |
| `description` | `description` |
| `colorId` | `colorId` |
| `allDay` | `allDay` (only set on summary event) |

If a Calendar MCP call fails (invalid calendar ID, network), log it and continue with the others — don't abort the whole briefing.

### Step 8 — Archive to Drive (skip if --skip-drive or --dry-run)

Upload the rendered `.md` to the Drive `briefings_folder_id` from config via Drive MCP `create_file`. Filename: `YYYY-MM-DD-morning.md`. MIME type: `text/markdown`.

### Step 9 — Print summary to user

```
Morning Brief written: briefings/2026-05-21-morning.md (5.8KB)
  Calendar events created: 5
    Macro Events: 3 (CPI, ECB, Powell)
    Earnings: 1 (NVDA)
    My Positions: 1 (summary)
  Drive: briefings/2026-05-21-morning.md uploaded
  Action items: 1 stop alert (TLT), 1 short-leg alert (NVDA Jun20 145C)
```

## Afternoon mode procedure

Same overall structure with these differences:

- **Step 1 data**: close prices instead of pre-market; today's P&L (BOD vs. current portfolio value); end-of-day news/headlines for "what moved & why"; AMC earnings on holdings; tomorrow's econ calendar (next-day filter)
- **Step 4 sections**: `snapshot` (close), `market_moves` (today's drivers), `pnl_recap`, `my_top_movers`, `closing_bell_actions`, `asia_releases`, `amc_earnings`, `geopolitical_summary`, `tomorrow_econ`, `tomorrow_fed_speakers`, `tomorrow_earnings`, `key_levels`
- **Step 7**: only writes the all-day "Afternoon Brief" event to My Positions (no macro/earnings events — those were created in morning)

## First-run checklist

1. ☐ Create the 3 Google Calendars manually (see `references/CALENDAR_SETUP.md`)
2. ☐ Create the Drive folder `Trading Briefings`, grab its ID
3. ☐ `cp config.example.yaml config.yaml`; paste calendar + Drive IDs; edit watchlist
4. ☐ Set `FMP_API_KEY` env var (for economic-calendar-fetcher)
5. ☐ Run `/morning-brief --dry-run` — verify markdown looks right, no events written
6. ☐ Run `/morning-brief --skip-calendar` — verify Drive upload
7. ☐ Run `/morning-brief` — full flow, calendar + Drive
8. ☐ Run for 10 sessions; keep the noise log; refine config weekly

## Status

- ✅ Step C: scaffolding, config, templates, calendar setup, skills inventory
- ✅ Step A: econ-indicator-explainer with 31 indicator cards + lookup script
- ✅ Step B: render/alerts/compose scripts + tests + JSON schema + sample data
- Ready for first dry-run.
