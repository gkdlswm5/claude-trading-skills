# Google API Setup — Calendar + Drive

One-time setup to give the briefing scripts direct access to your
Google Calendar and Drive, replacing the LLM-driven MCP write path.

This needs to be done **once per Google account** that will own the
briefing's calendars and Drive folder. The resulting `credentials.json`
+ `token.json` files are then copied to whichever machine runs the
brief (your PC for testing, Hostinger VPS for production).

> **Do this on your PC first**, get it working, then copy credentials
> to the VPS. Don't try to do the OAuth flow on the VPS directly — it
> requires a browser and you don't want to deal with X11 forwarding.

## What you'll end up with

- A Google Cloud project (free)
- Calendar API + Drive API enabled on that project
- An OAuth client (Desktop app type) with a `credentials.json`
- A `token.json` (generated on first auth, refreshes automatically)

## Step 1 — Create a Google Cloud project

1. Go to https://console.cloud.google.com/
2. Top bar → project dropdown → **New Project**
3. Name: `morning-trading-briefing` (or anything you'll recognize)
4. Org: leave as "No organization" if it's a personal account
5. Create. Wait ~30 seconds for it to appear.
6. Select the new project from the dropdown.

## Step 2 — Enable the APIs

In the search bar at the top, search for and enable each:

1. **Google Calendar API** → click → Enable
2. **Google Drive API** → click → Enable

(If you see a "must configure consent screen first" prompt, do Step 3
then come back to enable the APIs.)

## Step 3 — Configure the OAuth consent screen

Left sidebar → **APIs & Services** → **OAuth consent screen**.

1. User type: **External** (unless you have a Google Workspace org)
2. App name: `morning-trading-briefing`
3. User support email: your email
4. Developer contact: your email
5. Save and continue.

**Scopes screen:**

6. Click **Add or remove scopes**.
7. Add these by name or by checking the boxes:
   - `https://www.googleapis.com/auth/calendar` (Calendar read/write)
   - `https://www.googleapis.com/auth/drive.file` (Drive — write only
     the files this app creates; doesn't expose your full Drive)
8. Update → Save and continue.

**Test users screen:**

9. Add your own Google account as a test user.
10. Save and continue.

You can leave the app in "Testing" mode forever — you don't need to
publish it because you're the only user. Tokens issued in test mode
expire every 7 days; in production mode they don't. For a personal
tool either is fine; we'll handle re-auth in the deploy doc.

## Step 4 — Create the OAuth client

Left sidebar → **APIs & Services** → **Credentials**.

1. Top bar → **+ Create Credentials** → **OAuth client ID**.
2. Application type: **Desktop app**.
3. Name: `morning-briefing-desktop`.
4. Create.
5. A dialog shows your client ID and secret. Click **Download JSON**.
6. Rename the downloaded file to `credentials.json`.
7. **Save it somewhere outside the repo** — the repo is public. Suggested
   location: `~/.config/morning-briefing/credentials.json` on both your
   PC and VPS.

## Step 5 — First-run OAuth flow (on your PC)

The scaffolded clients in `scripts/google_calendar_client.py` will
include a CLI entrypoint for this. Until that's implemented, the flow is:

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.file",
]

flow = InstalledAppFlow.from_client_secrets_file(
    "~/.config/morning-briefing/credentials.json", SCOPES
)
creds = flow.run_local_server(port=0)

with open("~/.config/morning-briefing/token.json", "w") as f:
    f.write(creds.to_json())
```

Running that:
1. Opens your browser
2. Asks you to sign in to your Google account
3. Warns "Google hasn't verified this app" — click **Advanced** → **Go
   to morning-trading-briefing (unsafe)**. Safe because you wrote it.
4. Asks for the Calendar + Drive permissions you configured. Allow.
5. Browser shows "Authentication flow has completed."
6. `token.json` is written to disk.

From here on, the script auto-refreshes the token. You don't need to
re-do this unless:
- The refresh token expires (7 days in test mode, indefinite in
  production mode — re-run the flow when you see auth errors)
- You revoke access in your Google Account settings
- You add/remove scopes (need to re-consent)

## Step 6 — Copy credentials to the VPS

Once OAuth is working locally:

```bash
# On your PC:
scp ~/.config/morning-briefing/credentials.json briefing@vps-ip:~/.config/morning-briefing/
scp ~/.config/morning-briefing/token.json briefing@vps-ip:~/.config/morning-briefing/

# On the VPS:
chmod 600 ~/.config/morning-briefing/credentials.json
chmod 600 ~/.config/morning-briefing/token.json
```

The VPS will use the same refresh token your PC just got. Both machines
can use it concurrently — Google doesn't care which IP makes the call.

## Step 7 — Find your calendar IDs

The briefing writes to four sub-calendars. To get each one's ID:

1. Open https://calendar.google.com
2. Left sidebar → hover over each calendar → ⋮ → **Settings and sharing**
3. Scroll to **Integrate calendar** → copy the **Calendar ID** (long string
   ending in `@group.calendar.google.com`)

Paste each into `config.yaml`:

```yaml
calendars:
  macro_events: "abc123...@group.calendar.google.com"
  earnings: "def456...@group.calendar.google.com"
  my_positions: "ghi789...@group.calendar.google.com"
  market_updates: "jkl012...@group.calendar.google.com"
```

## Step 8 — Find your Drive folder ID

1. Create a folder in Drive named `briefings` (or whatever).
2. Open the folder. URL is `https://drive.google.com/drive/folders/XXX`.
3. The `XXX` is your folder ID. Paste into `config.yaml`:

```yaml
drive:
  briefings_folder_id: "XXX"
```

## Security notes

- `credentials.json` and `token.json` are **NEVER committed to git**.
  `.gitignore` already excludes the `~/.config/morning-briefing/` path
  via being outside the repo entirely.
- The `drive.file` scope (not `drive`) limits the app to only files it
  creates. It cannot read your existing Drive contents.
- If you ever suspect compromise, revoke in
  https://myaccount.google.com/permissions and re-run Step 5.

## Quotas

Both APIs are generously free:

- Calendar API: 1M requests/day default quota. Brief uses ~20/run.
- Drive API: 10K requests/100sec default. Brief uses ~2/run.

You will not hit limits.
