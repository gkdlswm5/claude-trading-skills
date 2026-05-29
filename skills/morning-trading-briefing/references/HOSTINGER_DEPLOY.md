# Hostinger VPS Deployment

Deploy the morning-trading-briefing skill on a Hostinger VPS as a
scheduled cron job. This is the production target. Development happens
on PC/laptop; production runs on the VPS.

## Architecture recap

```
Developer machine (PC)         GitHub          Hostinger VPS
─────────────────────         ──────         ───────────────
edit code           ──push──▶  repo  ◀──pull── cron job runs
test manually                                  brief here daily

                              Google Calendar + Drive
                              (writes from whichever
                               machine is running)
```

## Prerequisites

- Hostinger VPS (KVM 1 minimum; KVM 2 recommended if you plan Phase 2 IB)
- SSH access to the VPS
- A working `claude/eager-bardeen-VysCZ` branch on GitHub
- Google OAuth credentials prepared per `GOOGLE_API_SETUP.md`
- `FMP_API_KEY` from financialmodelingprep.com

## One-time VPS setup

All commands run on the VPS via SSH unless noted.

### 1. Create a non-root user (skip if you already have one)

```bash
adduser briefing
usermod -aG sudo briefing
su - briefing
```

### 2. Install Python + git

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
python3 --version  # confirm 3.11+ ideally
```

### 3. Clone the repo

```bash
cd ~
git clone https://github.com/gkdlswm5/claude-trading-skills.git
cd claude-trading-skills
git checkout claude/eager-bardeen-VysCZ  # or main once merged
```

### 4. Set up Python venv + dependencies

```bash
cd ~/claude-trading-skills/skills/morning-trading-briefing
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Create your config

```bash
cp config.example.yaml config.yaml
# Edit with your calendar IDs, watchlist, etc.
nano config.yaml
```

### 6. Set environment variables

Add to `~/.profile` (or `~/.bashrc`):

```bash
export FMP_API_KEY="your_key_here"
export GOOGLE_CREDENTIALS_PATH="$HOME/.config/morning-briefing/credentials.json"
export GOOGLE_TOKEN_PATH="$HOME/.config/morning-briefing/token.json"
```

Re-source: `source ~/.profile`.

### 7. Place Google credentials

```bash
mkdir -p ~/.config/morning-briefing
# scp credentials.json from your laptop to the VPS:
# (run this on your laptop, not the VPS)
#   scp credentials.json briefing@vps-ip:~/.config/morning-briefing/
chmod 600 ~/.config/morning-briefing/credentials.json
```

Run the brief once manually to trigger the OAuth flow and generate
`token.json`:

```bash
cd ~/claude-trading-skills/skills/morning-trading-briefing
source .venv/bin/activate
python3 scripts/google_calendar_client.py --authenticate
# Follow URL, paste auth code. token.json is written to GOOGLE_TOKEN_PATH.
```

### 8. Verify with a dry run

```bash
python3 scripts/compose_brief.py --mode morning --dry-run
# Should print the rendered brief without writing to Calendar/Drive.
```

## Cron schedule

Edit crontab:

```bash
crontab -e
```

Add (adjust paths and times to taste — these are ET):

```cron
# Morning brief: 6:30am ET weekdays = 10:30 UTC (adjust for DST)
30 10 * * 1-5 cd /home/briefing/claude-trading-skills && /home/briefing/claude-trading-skills/skills/morning-trading-briefing/.venv/bin/python3 skills/morning-trading-briefing/scripts/compose_brief.py --mode morning >> /home/briefing/logs/morning-$(date +\%Y\%m\%d).log 2>&1

# Afternoon brief: 3:30pm ET weekdays = 19:30 UTC
30 19 * * 1-5 cd /home/briefing/claude-trading-skills && /home/briefing/claude-trading-skills/skills/morning-trading-briefing/.venv/bin/python3 skills/morning-trading-briefing/scripts/compose_brief.py --mode afternoon >> /home/briefing/logs/afternoon-$(date +\%Y\%m\%d).log 2>&1
```

Create the log dir:

```bash
mkdir -p ~/logs
```

**DST gotcha:** US trading hours are in ET, which shifts between EST (UTC-5)
and EDT (UTC-4). Running cron in UTC means your 6:30am ET cron has to be
edited twice a year. Alternatives: set the VPS timezone to `America/New_York`
(`sudo timedatectl set-timezone America/New_York`) and use ET times directly
in cron — simpler, recommended.

## Log rotation

Add to `/etc/logrotate.d/morning-briefing` (sudo):

```
/home/briefing/logs/*.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
}
```

This keeps 8 weeks of logs, compressed after the first week.

## Updating the code on the VPS

After pushing changes from your PC:

```bash
ssh briefing@vps-ip
cd ~/claude-trading-skills
git pull origin claude/eager-bardeen-VysCZ
# If requirements.txt changed:
source skills/morning-trading-briefing/.venv/bin/activate
pip install -r skills/morning-trading-briefing/requirements.txt
```

You can automate this — have cron `git pull` before each run — but it's
risky during the first weeks of v2 when code is changing fast. Pull
manually for now.

## Verifying it's actually running

```bash
# Check cron log
grep CRON /var/log/syslog | tail -20

# Check the brief's own logs
ls -la ~/logs/
tail -50 ~/logs/morning-$(date +%Y%m%d).log
```

After a run, your Google Calendar should have today's events on the
configured sub-calendars and Drive should have the markdown file.

## Troubleshooting

- **OAuth token expired** → SSH in, re-run
  `python3 scripts/google_calendar_client.py --authenticate`.
- **Cron didn't fire** → check `/var/log/syslog` for CRON entries.
  Common cause: forgot to `chmod +x` the script or wrong shebang.
- **Permission denied on token.json** → `chmod 600
  ~/.config/morning-briefing/token.json`.
- **FMP rate limit (429)** → free tier is 250 calls/day. The brief uses
  ~30 calls/run × 2 runs = 60/day, well under the limit. If you hit
  this, something is in a loop.
- **Brief runs but no calendar events appear** → check the
  `GOOGLE_CREDENTIALS_PATH` env var is set in the cron environment too,
  not just your interactive shell. Cron doesn't inherit `~/.profile`.
  Add env exports at the top of crontab itself.

## When to upgrade VPS plan

Stay on KVM 1 ($5/mo) for v2.0–v2.3. Upgrade to KVM 2 if/when:

- You add Phase 2 IB Gateway (needs ~1GB RAM minimum)
- You add other always-on workloads to the same VPS
- The brief's memory footprint grows past 256MB (unlikely with current scope)
