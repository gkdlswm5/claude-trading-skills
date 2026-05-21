---
description: "Generate the 3:30pm ET afternoon briefing: today's recap + overnight risks + tomorrow's setup."
argument-hint: "[--dry-run | --skip-calendar | --skip-drive]"
---

# Afternoon Brief (3:30pm ET)

Generate the end-of-day briefing covering today's recap (what moved + your P&L), overnight risks (Asia/Europe/AMC earnings), and tomorrow's setup (econ calendar + earnings + key levels).

## Arguments

```
$ARGUMENTS
```

- `--dry-run` — generate brief only
- `--skip-calendar` — Drive + local only
- `--skip-drive` — Calendar + local only
- (no args) — full run

## Execution

Invoke `morning-trading-briefing` skill with `mode=afternoon`. Follow `skills/morning-trading-briefing/SKILL.md` (afternoon mode section):

1. Load `config.yaml`
2. Gather end-of-day data:
   - Close prices for SPY/QQQ/DXY/10Y/oil/VIX (`stock-quote`)
   - Today's P&L vs. BOD portfolio value (`ib-portfolio`)
   - What moved & why (`market-news-analyst` for today's drivers)
   - AMC earnings on holdings (`earnings-calendar` + `greeks` for implied move)
   - Asia data on docket (`economic-calendar-fetcher` filtered to next 24hr Asia)
   - Tomorrow's econ + Fed speakers + earnings
3. Run `check_alerts.py` (closing-bell stop check)
4. Assemble afternoon `brief_data.json`
5. Render via `compose_brief.py`
6. Write single all-day "Afternoon Brief" event to My Positions calendar (no macro/earnings events — those were created this morning)
7. Upload markdown to Drive
8. Print summary

## Dry-run example

```bash
python3 skills/morning-trading-briefing/scripts/compose_brief.py \
  --input skills/morning-trading-briefing/scripts/examples/sample_afternoon.json \
  --out-dir /tmp/test-brief --dry-run
```
