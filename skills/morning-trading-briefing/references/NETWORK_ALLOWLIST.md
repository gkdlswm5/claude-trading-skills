# Network Allowlist — Morning Trading Briefing

When running the briefing in the Claude Code **cloud** environment, egress
is gated by the environment's network policy. The skill needs egress to the
hosts below.

> **For local development, this file is irrelevant.** Claude Code on your
> laptop has no egress policy. Work locally; this file only matters when
> you wire up a scheduled cloud run.

## Required hosts

| Host | What it's for |
|---|---|
| `financialmodelingprep.com` | Econ calendar, earnings (FMP) |
| `*.financialmodelingprep.com` | FMP subdomains |
| `query1.finance.yahoo.com` | Quotes (yfinance) |
| `query2.finance.yahoo.com` | Quotes (yfinance fallback) |
| `finance.yahoo.com` | Quotes / overnight closes |
| `api.stlouisfed.org` | FRED real yields |
| `finviz.com` | Pre-market movers, screener |
| `elite.finviz.com` | Elite screener / API |
| `www.sec.gov` | Insider Form 4 |
| `whalewisdom.com` | Unusual options flow |
| `www.dataroma.com` | Institutional holdings |
| `seekingalpha.com` | News / sentiment |

Also tick **"include default package managers"** so pip can fetch
dependencies during setup.

## Setup steps

1. claude.ai/code → cloud icon (top right) → gear on "Default Cloud
   Environment".
2. Set Network access = **Custom**.
3. Paste hosts above into Allowed domains.
4. Tick "include default package managers".
5. Save.
6. **Start a NEW session.** The policy is fixed at session start, so
   existing sessions don't pick up the change.

## Verification

In a fresh cloud session, run:

```bash
for h in financialmodelingprep.com query1.finance.yahoo.com api.stlouisfed.org; do
  echo -n "$h: "
  curl -sS -o /dev/null -w "%{http_code}\n" "https://$h/" --max-time 5
done
```

Anything other than `403` means egress is open for that host. 200, 301, 404
are all fine — they prove the request reached the host.
