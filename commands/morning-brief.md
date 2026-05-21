---
description: "Generate the 7:00am ET pre-open trading briefing and write it to Google Calendar + Drive."
argument-hint: "[--dry-run | --skip-calendar | --skip-drive]"
---

# Morning Brief (7:00am ET)

Generate the pre-open trading briefing covering macro day-ahead, earnings, my IB positions, and fresh opportunities. Push timed events to the Macro Events / Earnings sub-calendars, a summary all-day event to My Positions, and archive the full markdown to Google Drive.

## Arguments

```
$ARGUMENTS
```

- `--dry-run` — generate the brief only; do NOT write calendar events or Drive file
- `--skip-calendar` — write Drive + local markdown; skip calendar events
- `--skip-drive` — write calendar events + local markdown; skip Drive
- (no args) — full run

## Execution

Invoke the `morning-trading-briefing` skill with `mode=morning`. Follow the full procedure in `skills/morning-trading-briefing/SKILL.md`:

1. Load `config.yaml` (halt if missing)
2. Gather raw data via sub-skills (parallel where possible):
   - `economic-calendar-fetcher`, `earnings-calendar`, `ib-portfolio`
   - `stock-quote` for indices/rates/commodities/FX
   - `market-news-analyst` for overnight Asia/Europe
   - `sector-analyst`, `news-sentiment`, `whale-hunting`, `insider-trading`
   - `scanner-bullish`, `scanner-pmcc`
3. For each econ event, enrich with `lookup_indicator.py --json`
4. Run `check_alerts.py` against IB positions
5. Assemble `brief_data.json` per `references/BRIEF_DATA_SCHEMA.md`
6. Write the "must-read top 3" synthesis LAST (ties to actual holdings)
7. Run `compose_brief.py` to render markdown + emit `events.json`
8. Iterate events.json → Calendar MCP `create_event` (unless `--skip-calendar` or `--dry-run`)
9. Upload markdown → Drive MCP `create_file` (unless `--skip-drive` or `--dry-run`)
10. Print summary

## Dry-run example

```bash
python3 skills/morning-trading-briefing/scripts/compose_brief.py \
  --input skills/morning-trading-briefing/scripts/examples/sample_morning.json \
  --out-dir /tmp/test-brief --dry-run
```

Outputs `/tmp/test-brief/2026-05-21-morning.md` — use this to validate the format before running for real.

## First time?

Run `--dry-run` 2-3 times and review the markdown. Iterate `config.yaml` (watchlist, alert thresholds, sections to show) until the brief feels right, then drop the `--dry-run`.
