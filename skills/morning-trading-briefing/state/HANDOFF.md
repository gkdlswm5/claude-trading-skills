# Session Handoff — Morning Trading Briefing

Paste the "Prompt to start the next session" block below into a fresh cloud
session to resume. Everything else here is reference context.

---

## Prompt to start the next session

> Continue the morning trading briefing setup.
>
> Context:
> - Repo `gkdlswm5/claude-trading-skills`, branch `claude/morning-trading-briefing-1TfGL`
>   (all skill work is committed there; `git fetch` + fast-forward the local branch).
> - Skill at `skills/morning-trading-briefing/`. Render/alerts/compose scripts work
>   (verified by rendering `scripts/examples/sample_morning.json`).
> - Running in no-IB / manual-holdings mode (`integration.ib_integration: false`).
>   I use both Interactive Brokers and Robinhood; plan is a manual `holdings:` block
>   in config rather than any Robinhood API.
> - `FMP_API_KEY` is already set in the environment (don't ask me for it).
>
> The one blocker: network egress. Environment policy was switched from "Trusted"
> to "Custom" with these data hosts added (defaults box ticked):
> financialmodelingprep.com, *.financialmodelingprep.com, query1.finance.yahoo.com,
> query2.finance.yahoo.com, finance.yahoo.com, api.stlouisfed.org, finviz.com,
> elite.finviz.com, www.sec.gov, whalewisdom.com, www.dataroma.com, seekingalpha.com
>
> First thing: run a curl probe against those hosts. If anything other than 403,
> egress is open — proceed. If still 403, advise whether to troubleshoot the policy
> or start another fresh session.
>
> Once egress is open:
> 1. Fetch today's real econ calendar + earnings + quotes; generate a live /morning-brief.
> 2. Pending from me: 3 Google Calendar IDs (Trading — Macro Events / Earnings /
>    My Positions); delete leftover `[TEST] CPI` event on the "Market Updates" calendar.
> 3. Wire calendars + Drive archiving into the brief.

---

## Status checklist

- [x] Skill scaffolding, scripts, templates, config schema
- [x] econ-indicator-explainer (31 indicator cards + lookup)
- [x] no-IB / manual-holdings mode toggle + SKILL.md docs
- [x] Sample render verified end-to-end
- [x] `FMP_API_KEY` present in environment
- [ ] **Network egress open** (switched policy to Custom; needs verification in a fresh session)
- [ ] 3 Google Calendar IDs provided + pasted into config.yaml
- [ ] Drive `briefings_folder_id` set in config.yaml
- [ ] Delete `[TEST] CPI` event from "Market Updates" calendar (manual)
- [ ] First live `/morning-brief` generated
- [ ] Calendar + Drive writes wired in

## Network allowlist (data hosts the briefing needs)

```
financialmodelingprep.com        # econ calendar, earnings (FMP)
*.financialmodelingprep.com
query1.finance.yahoo.com          # quotes (yfinance)
query2.finance.yahoo.com
finance.yahoo.com
api.stlouisfed.org                # FRED real yields
finviz.com                        # pre-market movers, screener
elite.finviz.com
www.sec.gov                       # insider Form 4
whalewisdom.com                   # unusual options flow
www.dataroma.com                  # institutional holdings
seekingalpha.com                  # news / sentiment
```

Set via: claude.ai/code → cloud icon → gear on "Default Cloud Environment" →
Network access = Custom → paste hosts in Allowed domains → tick "include default
package managers" → Save → start a NEW session (policy is fixed at session start).

## Open decisions for later

- Manual `holdings:` block schema (covers IB + Robinhood) — not yet wired into
  config.example.yaml or check_alerts.py. Discuss before building.
- Phase 2: IB integration (live positions/P&L) requires TWS or IB Gateway on a
  machine — candidate is a Hostinger VPS (KVM 2), which also removes the egress
  limitation. Defer until the no-IB briefing is validated (~2 weeks + noise log).
