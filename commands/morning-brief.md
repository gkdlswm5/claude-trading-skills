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

- `--dry-run` — generate brief only, do NOT write calendar events or Drive file
- `--skip-calendar` — generate brief + save to Drive, skip calendar events
- `--skip-drive` — generate brief + create calendar events, skip Drive archive
- (no args) — full run

## Execution

1. Load `skills/morning-trading-briefing/config.yaml` (watchlist, calendar IDs, thresholds, Drive folder)
2. Invoke the `morning-trading-briefing` skill with `mode=morning`
3. Skill assembles each section (macro / earnings / positions / opportunities)
4. Render via `references/briefing-template.md`
5. Side effects (unless suppressed by flags):
   - Create timed events on Macro Events calendar for each release
   - Create timed events on Earnings calendar for each BMO/AMC report
   - Create all-day "Morning Brief" event on My Positions calendar with summary in description
   - Save `briefings/YYYY-MM-DD-morning.md` to Drive

## Status

SCAFFOLD ONLY. Step C complete (plumbing). Steps A (indicator explainer) and B (orchestration) wire this up.
