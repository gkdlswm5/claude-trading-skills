---
name: morning-trading-briefing
description: Two-times-daily trading briefing (7am pre-open + 3:30pm afternoon). Personalized to IB portfolio + market-wide. Covers macro events with full "why it matters" context, earnings with implied moves, position action items, and fresh setups. Writes timed events to Google Calendar sub-calendars (Macro Events / Earnings / My Positions) and archives markdown to Google Drive. Invoked by /morning-brief or /afternoon-brief commands.
---

# Morning Trading Briefing

Produces personalized pre-open and afternoon briefings for stocks, options, rates, commodities, and FX. Content is driven by `config.yaml` so iteration happens without code changes.

## Invocation

- `/morning-brief` → `mode=morning`
- `/afternoon-brief` → `mode=afternoon`

## Integration modes

Set `integration.ib_integration` in `config.yaml` to control which sections run:

| Mode | When to use | What runs |
|---|---|---|
| `ib_integration: false` | Claude Code Web, or any environment without local TWS/IB Gateway | Macro day-ahead, market-wide earnings, opportunities, must-read. Skips position-specific sections. |
| `ib_integration: true` | Local Claude Code with TWS or IB Gateway running on `localhost:7497` | All sections, including overnight P&L, stop alerts, short-leg roll candidates, holdings news, earnings-on-holdings. |

When `ib_integration: false`, the watchlist takes over as the proxy for "holdings" — news filtering, unusual flow detection, and earnings-of-interest all run against `config.watchlist + config.mega_caps` instead of IB positions.

## Pipeline overview

The skill is hybrid with a strict boundary at `brief_data.json`: the LLM
handles synthesis (assembling sub-skill outputs into `brief_data.json`,
writing the "must-read top 3"); from there Python takes over for all
deterministic work — alert math, template rendering, event-JSON
generation, **and the Google Calendar + Drive writes** (`v2.0+`, via
`google_calendar_client.py` / `google_drive_client.py`). The LLM no
longer touches MCP for calendar/Drive — that path produced the
2026-05-27 dupe storm (see `state/HANDOFF.md`).

```
┌──────────────┐      ┌─────────────────┐      ┌───────────────┐
│  Sub-skills  │─────▶│  LLM assembles  │─────▶│ compose_brief │
│ (ib-*, econ- │      │ brief_data.json │      │ render +      │
│  calendar,   │      └────────┬────────┘      │ events.json   │
│  scanner, …) │               │               └───────┬───────┘
└──────────────┘               │                       │
                               ▼                       ▼
                        check_alerts.py        ┌───────────────┐
                        lookup_indicator.py    │write_brief_   │
                                               │ outputs.py    │
                                               │ → Calendar API│
                                               │ → Drive API   │
                                               └───────────────┘
```

## Step-by-step procedure (morning mode)

### Step 0 — Load config

Read `skills/morning-trading-briefing/config.yaml`. If it doesn't exist, halt and tell the user to copy `config.example.yaml` → `config.yaml` and fill in calendar IDs + watchlist (see `references/CALENDAR_SETUP.md`).

Check `integration.ib_integration`. The procedure below is for the full IB-integrated path; **see the "No-IB mode" section below for what to skip when `ib_integration: false`**.

### Step 1 — Gather raw data (parallel where possible)

| Need | Skill / source | Skip if no IB? |
|---|---|---|
| Today's econ events | `economic-calendar-fetcher` (FMP API, today's date range) | no |
| Today's earnings | `earnings-calendar` (today, filtered by config.mega_caps + watchlist + holdings) | no |
| IB positions | `ib-portfolio` | **yes** |
| Pre-market quotes | `stock-quote` for SPY/QQQ/DXY/UUP/TLT/USO/GLD/HG=F/UNG + crypto | no |
| Overnight Asia/Europe | `market-news-analyst` or WebFetch on Nikkei/HSI/KOSPI/DAX/FTSE close prices | no |
| Rates snapshot | `stock-quote` on ^TNX (10Y), ^FVX (5Y), ^IRX (3M); FRED for real yields if needed | no |
| Sector ETFs | `sector-analyst` or `stock-quote` on XLF/XLE/XLK/XLI/XLV | no |
| Pre-market movers | `finviz-screener` (pre-market gainers/losers >$1B mcap) | no |
| News on holdings/watchlist | `news-sentiment` per ticker (holdings ∪ watchlist) | no (uses watchlist) |
| Unusual flow | `whale-hunting` per holding/watchlist ticker | no (uses watchlist) |
| Insider buying | `insider-trading` (watchlist + holdings) | no (uses watchlist) |
| Fresh setups | `scanner-bullish` + `scanner-pmcc` (top 3 each) | no |
| Geopolitical wrap | `WebSearch` constrained to trusted sources (see rule below) → `geopolitical_summary` | no |
| Bonds/rates news | `WebSearch` (Treasury supply/auctions, Fed drivers, credit) → `rates_news` | no |
| Commodities news | `WebSearch` (OPEC+/EIA, supply disruptions, metals/ags) → `commodities_news` | no |
| Trend history | `stock-quote` / Yahoo `range=3mo` daily closes for index/rates/commodity tickers → `trends` + chart series (when `style.charts`/`style.sparklines`) | no |

**Sourced-news rule (avoid clickbait / bad data) — applies to all three news
fields** (`geopolitical_summary`, `rates_news`, `commodities_news`): apply the
`market-news-analyst/references/trusted_news_sources.md` tiering. Use **Tier-1
sources only** for facts — Reuters, AP, Bloomberg, FT, WSJ, and primary sources
(central-bank statements, Treasury/EIA/OPEC releases, filings). A claim enters a
wrap only with **≥2 independent Tier-1 corroborations**; single-source items are
dropped or explicitly flagged "unconfirmed." State **facts and the cross-asset
read** ("Brent +2% on Hormuz headline"), never punditry or price predictions.
Exclude social/aggregator/opinion outlets. These are the least reproducible
sections (live search), so keep each tight — 2-4 sentences. Full contract:
`references/NEWS_QUALITY.md`.

**Validate before publishing.** Run the deterministic checker on **each** assembled
news field:

```bash
python3 skills/morning-trading-briefing/scripts/check_news_quality.py --text "<field text>" --json
```

Hard fail (exit 1) = banned emotive lexicon, or a quantified market claim with no
allowlisted source. On hard fail, **omit that field** rather than publish it —
a missing wrap beats a biased/unsourced one. Warnings (prediction language,
single-source markers) are surfaced for a quick manual look but don't block.
This gate is what makes the news wraps safe to run unattended on the daily auto-run.

### Step 2 — Enrich econ events with explainer cards

For each event from `economic-calendar-fetcher`:

```bash
python3 skills/econ-indicator-explainer/scripts/lookup_indicator.py --json "<event.event>"
```

- On match: parse JSON `.sections` → populate `what`, `how_measured`, `why_matters`, `reaction_history`, `watch_for_today` on the brief_data econ_releases entry.
- On no match (exit 2): include the event with only the FMP-supplied fields, and append the unmapped name to `skills/morning-trading-briefing/state/unmapped_indicators.log` so the user can add a card later.

**ELI5 plain-English line** (per econ event + Fed speaker, `eli5` field). Write it at
the level set by `config.style.eli5_level` — the user picks one:

| Level | Audience | Style | Example (ECB) |
|---|---|---|---|
| `off` | — | no eli5 line | — |
| `light` | knows the basics | no jargon, **one sentence** | "ECB sets eurozone rates; leaning toward cuts weakens the euro and firms the dollar — a mild headwind for US tech that earns abroad." |
| `medium` | beginner | defines the institution + cause→effect, **2-3 sentences** | "The ECB is Europe's central bank — it sets how expensive borrowing is. Lower rates make the euro less attractive, so the dollar rises. A stronger dollar trims US tech's overseas sales; DAX/Stoxx react first." |
| `heavy` | true beginner | analogies, everything defined, **very short sentences** | "Think of the ECB as Europe's 'money boss.' Cheaper borrowing → people want euros a bit less → the dollar looks stronger. A strong dollar is like a small tax on US firms selling abroad. Green DAX/Stoxx = the news landed well." |

Keep the same factual content as the technical explanation — just re-leveled. Never add a prediction or a trade call in the eli5 line.

### Step 3 — Run alert checker (IB only)

Skip when `ib_integration: false`.

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

- `snapshot`, `econ_releases` (set `impact` High/Medium/Low per event — drives tag/color/sort/filter), `fed_speakers`, `overnight`, `rates`, `rates_news`, `commodities`, `eia_opec_today`, `commodities_news`
- `fx`, `sector_etfs`, `rotation_read`, `premarket_movers`
- `earnings_today` (split mega-caps vs. my_positions — `my_positions` empty when no IB)
- `my_positions` (omit entirely when no IB, or just populate `holding_events` with watchlist news)
- `opportunities`
- `geopolitical_summary` (optional; from the Step 1 geo wrap — Tier-1 sourced, corroborated. Feeds the markdown "Geopolitical" section + the Market Updates digest.)
- `bottom_line` (one tight headline, even shorter than must-read; `config.style.bottom_line`)
- `filters` (mirror `config.filters` so the scripts apply the same suppression: `{drop_minor_econ, voters_only, include_tier3, max_earnings}`)
  - `include_tier3: false` (v2.3 default) folds Tier-3 macro (regional Fed surveys, MBA, bill auctions) out of the calendar; the notability override still keeps an all-minor day from blanking.
  - `max_earnings: 8` (v2.3 default) caps the earnings digest to the top N by importance. Set `market_cap` on earnings entries (FMP `marketCap`) so ranking uses `market_cap × max(1, implied_move%)`; without it, ranking falls back to implied move. Your positions always sort first. `0` disables the cap.
- `watchlist` (config.watchlist + mega_caps + holdings — bolded in must-read/bottom-line when `config.style.bold_tickers`)
- `key_levels` + `risk_regime` (from `technicals.py` — see Step 6)

**Noise filtering (config.filters):** minor econ (Low-impact, or denylisted: MBA
mortgage, Redbook, bills, regional Fed surveys) and non-voter / ceremonial Fed
speakers are suppressed — *unless notable* (the only data of the day is kept via the
override in `event_filters.filter_releases`). `event_filters.py` is the shared,
tested helper; render + compose both apply it. Set `impact` on every econ event so
tags/colors/sort work.

**Event budget (v2.3): aim for ≤ 12 calendar events/day** across all four
sub-calendars. The levers: `include_tier3: false` trims low-impact macro, and
`max_earnings: 8` caps the (single all-day) earnings digest's ranked list. A
typical day lands around: ~3–6 timed macro (Macro Events) + 1 earnings digest +
1 My Positions summary + 1 Market Updates digest. If you routinely exceed 12,
lower `max_earnings` or confirm `include_tier3` is off.

For each section that ends with a `so_what` field (rates, fx, sector rotation): write one sentence tying the data to the user's actual positions. This is the discipline that turns the brief from a data dump into actionable signal.

### Step 5 — Write the "must-read top 3" LAST

This is the most important synthesis step. After everything else is assembled, look at the entire brief_data and pick the 3 items that will materially affect today's P&L. Examples:

- "8:30 ET CPI — consensus 3.1%. Hot Core (>3.4%) tanks your TLT long and Jan26 LEAPS."
- "NVDA reports AMC, implied move 8.5%. Your short Jun20 145C has 0.42 delta — roll before close."
- "USD/JPY at 155.4 — BOJ intervention risk overnight. Could spike VIX into open."

In no-IB mode, replace position-specific references with watchlist references:
- "NVDA reports AMC, implied move 8.5%. If you trade NVDA earnings, IV at 95th percentile — consider a strangle or stay flat."

Tight, actionable, ties to holdings or watchlist tickers. If you can't write 3 items that meet this bar, write fewer — don't fluff.

### Step 6 — BI charts + sparklines, then render + emit events.json

**Trend data (when `style.charts` or `style.sparklines`):** in Step 1 also fetch
`style.chart_history_days` of daily closes (Yahoo `range=3mo`) for the index /
rates / commodity tickers. Put the per-metric value lists on brief_data `trends`
(oldest→newest) — these drive the inline sparklines (digest + Rates section).

**PNG charts (when `style.charts: true`)** — needs `matplotlib`/`pandas`
(`pip install -r skills/morning-trading-briefing/requirements.txt`). Build a series
JSON (`{date, series:{name:{group,points:[{date,close}]}}, sectors:{}}`) and run:

```bash
python3 skills/morning-trading-briefing/scripts/generate_charts.py \
  --data /tmp/series.json --out-dir briefings/charts/YYYY-MM-DD/
```

It writes one PNG per group + `charts_manifest.json`. After uploading the PNGs in
Step 8, set each manifest entry's `url` and put the manifest on brief_data `charts`
so the markdown links them. (Calendar entries are text-only — charts live in the
markdown/Drive; sparklines cover the calendar.)

**Technical levels + risk regime (`style.technical_levels` / `style.risk_regime`):**
run `technicals.py` on the same history (plus VIX + sector breadth %) to compute
per-index key levels (50/200 DMA, 20-day support/resistance, trend) and a risk-on/off
one-liner:

```bash
python3 skills/morning-trading-briefing/scripts/technicals.py --data /tmp/series.json
# series.json: {"series": {"SPY": [..closes..], ...}, "vix": 17.0, "breadth_pct": 70}
```

Put the result on brief_data `key_levels` + `risk_regime`. The renderer shows a Key
levels table and a "Regime:" line; the digest carries the regime one-liner.

**Render + events:**

```bash
python3 skills/morning-trading-briefing/scripts/compose_brief.py \
  --input /tmp/brief_data.json \
  --config skills/morning-trading-briefing/config.yaml \
  --out-dir briefings/
```

Produces:
- `briefings/YYYY-MM-DD-morning.md` — full markdown
- `briefings/YYYY-MM-DD-morning.events.json` — list of calendar events to create

### Step 7 + 8 — Push to Google Calendar + Drive (Python, v2.0+)

One command pushes both:

```bash
python3 skills/morning-trading-briefing/scripts/write_brief_outputs.py \
  --config skills/morning-trading-briefing/config.yaml \
  --date YYYY-MM-DD --mode morning \
  --briefings-dir briefings/
```

The script reads `briefings/YYYY-MM-DD-morning.{md,events.json}` (produced
in Step 6), then:

- **Calendar:** loops each event, calls `upsert_event(calendar_id, mtb_key,
  payload, date_iso)` via `google_calendar_client.py`. The function lists
  existing events for the day, matches the `<!-- mtb-key: ... -->` marker
  embedded in the description, and patches in place if found — otherwise
  creates. Same input → same calendar state, every time.
- **Drive:** uploads the markdown via `upsert_markdown(folder_id, filename,
  content)` in `google_drive_client.py`. Looks the file up by name in the
  configured `briefings_folder_id` and overwrites in place if it exists
  (file ID stable across re-runs). Filename: `YYYY-MM-DD-morning.md`,
  MIME `text/markdown`.

**Flags:**

- `--dry-run` — print the plan; don't authenticate; don't call Google APIs.
  Use to smoke-test the wiring before pointing at real calendars.
- `--skip-calendar`, `--skip-drive` — turn off one writer.
- `--credentials PATH`, `--token PATH` — override `config.google.*` paths.

**First-run setup.** Once per Google account (see
`references/GOOGLE_API_SETUP.md`):

```bash
python3 skills/morning-trading-briefing/scripts/google_calendar_client.py \
  --authenticate \
  --credentials ~/.config/morning-briefing/credentials.json \
  --token       ~/.config/morning-briefing/token.json
```

That mints a token.json valid for both Calendar + Drive scopes. Subsequent
runs auto-refresh.

**Failure isolation.** A single bad event (invalid calendar ID, network
blip) is logged with `FAIL calendar:<lane> <mtb-key> — <error>` and the
loop continues with the rest. The briefing as a whole never aborts on a
single-event failure.

**Calendar routing** (each calendar is optional — a missing
`config.calendars.*` key skips that lane):

- **Macro Events** — timed econ events (minor filtered, sorted by impact,
  `[HIGH/MED/LOW]` tag + color: red/banana/graphite) + voter Fed speakers
- **Earnings** — ONE all-day **ranked digest** ("Earnings — N reporting"),
  your positions first then by implied move
- **My Positions** — all-day summary carrying the full rendered brief
- **Market Updates** — all-day **digest**: snapshot + must-reads +
  overnight + energy catalysts + pre-market movers + geopolitical wrap
  (the "soft / narrative context" lane; emitted only when
  `market_updates` is set)

**Chart PNGs (when `style.charts`):** v2.0 covers the markdown upload
only. PNG upload via the Python Drive client lands in a follow-up slice
— for now, the markdown's chart links point at the local
`briefings/charts/YYYY-MM-DD/` directory.

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

In no-IB mode the "Action items" line is omitted.

## No-IB mode: what changes

When `integration.ib_integration: false`:

| Step | Behavior |
|---|---|
| Step 1 — `ib-portfolio` | **Skipped.** Watchlist + mega_caps becomes the universe. |
| Step 3 — `check_alerts.py` | **Skipped entirely.** No stop alerts or short-leg alerts. |
| Step 4 — `my_positions` section | Omit entirely OR populate only `holding_events` (news on watchlist). No `pnl_rows`, no alerts. |
| Step 4 — `earnings_today.my_positions` | Empty list. All earnings go in `megacaps` cut. |
| Step 5 — must-read | Reference watchlist tickers instead of holdings. |
| Step 7 — Calendar events | Macro Events + Earnings calendars get fully populated. My Positions calendar gets only the all-day summary event (no stop/roll alerts). |
| Step 9 — summary | Omit "Action items" line. |

## Afternoon mode procedure

Same overall structure with these differences:

- **Step 1 data**: close prices instead of pre-market; today's P&L (BOD vs. current portfolio value) — **skip if no IB**; end-of-day news/headlines for "what moved & why"; AMC earnings on holdings; tomorrow's econ calendar (next-day filter)
- **Step 4 sections**: `snapshot` (close), `market_moves` (today's drivers), `pnl_recap` (skip if no IB), `my_top_movers` (skip if no IB), `closing_bell_actions` (skip if no IB), `asia_releases`, `amc_earnings`, `geopolitical_summary`, `tomorrow_econ`, `tomorrow_fed_speakers`, `tomorrow_earnings`, `key_levels`
- **Step 7**: only writes the all-day "Afternoon Brief" event to My Positions (no macro/earnings events — those were created in morning)

## First-run checklist

### Phase 1 — No-IB (works on Claude Code Web)

1. ☐ Create the 3 Google Calendars manually (see `references/CALENDAR_SETUP.md`)
2. ☐ Create the Drive folder `Trading Briefings`, grab its ID
3. ☐ Set `FMP_API_KEY` in your Claude Code Web environment config (web UI)
4. ☐ `cp config.example.yaml config.yaml`; set `ib_integration: false`; paste calendar + Drive IDs; edit watchlist
5. ☐ Run `/morning-brief --dry-run` — verify markdown looks right, no events written
6. ☐ Run `/morning-brief --skip-calendar` — verify Drive upload
7. ☐ Run `/morning-brief` — full flow, calendar + Drive (no IB sections)
8. ☐ Run for ~10 sessions; keep the noise log; refine config weekly

### Phase 2 — Add IB (when you have TWS/IB Gateway reachable)

9. ☐ Launch TWS or IB Gateway on the machine that runs Claude Code
10. ☐ Flip `ib_integration: true` in `config.yaml`
11. ☐ Run `/morning-brief --dry-run` again — confirm position sections populate
12. ☐ Run `/morning-brief` — full flow with IB integration

## Status

- ✅ Step C: scaffolding, config, templates, calendar setup, skills inventory
- ✅ Step A: econ-indicator-explainer with 31 indicator cards + lookup script
- ✅ Step B: render/alerts/compose scripts + tests + JSON schema + sample data
- ✅ No-IB mode toggle added — ready for Phase 1 dry-run on Claude Code Web
- ✅ v2.0: Python-direct Calendar + Drive writes (`write_brief_outputs.py`,
  `google_calendar_client.py`, `google_drive_client.py`). Replaces the
  LLM/MCP write path that produced the 2026-05-27 dupe storm. v2.1 adds the
  back-to-back idempotency test + multi-match cleanup.
