# Calendar Setup (one-time manual step)

The Google Calendar MCP can read calendars and write events to them, but it **cannot create new calendars**. You'll create the 3 sub-calendars yourself (~2 minutes), then paste the IDs into `config.yaml`.

## Step 1 — Create 3 calendars

1. Open https://calendar.google.com on desktop
2. Left sidebar → hover "Other calendars" → click `+` → "Create new calendar"
3. Create these three, one at a time:

   | Name | Color (suggested) | Description |
   |---|---|---|
   | `Trading — Macro Events` | Peacock (blue) | Econ releases, Fed speakers, central bank decisions |
   | `Trading — Earnings` | Tangerine (orange) | Company earnings reports BMO/AMC |
   | `Trading — My Positions` | Tomato (red) | Daily briefing summary + position alerts |

4. For each calendar, after creating, click "Settings and sharing" → scroll to **"Integrate calendar"** → copy the **Calendar ID** (long string ending in `@group.calendar.google.com`).

## Step 2 — Paste IDs into config.yaml

In `skills/morning-trading-briefing/config.yaml`:

```yaml
calendars:
  macro_events: "YOUR_MACRO_ID@group.calendar.google.com"
  earnings: "YOUR_EARNINGS_ID@group.calendar.google.com"
  my_positions: "YOUR_POSITIONS_ID@group.calendar.google.com"
```

## Step 3 — Verify

Ask Claude:
```
list all my calendars and confirm the 3 Trading sub-calendars are visible
```

Claude will call `list_calendars` and confirm the 3 IDs match your config.

## Step 4 — (optional) Set default reminders per calendar

For Macro Events: 30-minute popup reminder (so you're alerted before 8:30am CPI etc.)
For Earnings: 60-minute popup (before market open / after market close)
For My Positions: no reminder (all-day event, you check when you sit down)

Do this in each calendar's Settings → "Event notifications".

## Drive folder

Also create a Drive folder called `Trading Briefings` and copy its folder ID (from the URL: `drive.google.com/drive/folders/<FOLDER_ID>`) into:

```yaml
drive:
  briefings_folder_id: "YOUR_FOLDER_ID"
```

That's it for plumbing.
