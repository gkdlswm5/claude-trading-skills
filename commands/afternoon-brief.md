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
- `--skip-calendar` — save to Drive only
- `--skip-drive` — calendar only
- (no args) — full run

## Execution

1. Load `skills/morning-trading-briefing/config.yaml`
2. Invoke the `morning-trading-briefing` skill with `mode=afternoon`
3. Skill assembles:
   - Today's recap: SPY/QQQ/DXY/10Y/oil close, your P&L per position, what moved & why
   - Overnight risks: Asia data on the docket, AMC earnings on your tickers, geopolitical headlines
   - Tomorrow's setup: econ releases, Fed speakers, earnings (your tickers + mega-caps), key levels
4. Render via `references/briefing-template.md` (afternoon variant)
5. Side effects: all-day "Afternoon Brief" event on My Positions calendar + `briefings/YYYY-MM-DD-afternoon.md` to Drive

## Status

SCAFFOLD ONLY. See `/morning-brief` for status notes.
