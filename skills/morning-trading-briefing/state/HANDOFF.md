# Session Handoff — Morning Trading Briefing v2

Paste the **Prompt to start the next session** block below into a fresh
**local** Claude Code session to resume. Everything else here is reference.

> **Develop locally.** The cloud container is ephemeral and the egress
> policy has been a recurring drag (see `references/NETWORK_ALLOWLIST.md`).
> Run scripts on your laptop, iterate fast, commit + push to GitHub when
> each slice is ready. Cloud env is for the eventual scheduled run, not
> for development.

---

## Prompt to start the next session

> Upgrade the morning-trading-briefing skill to v2. Goal: a brief that is
> **idempotent** across reruns, **internally consistent** in its snapshot
> data, and **quiet enough** to read in 60 seconds.
>
> Context:
> - Repo `gkdlswm5/claude-trading-skills`, branch `claude/eager-bardeen-VysCZ`.
>   Branch is current with main. Work locally; commit + push when each
>   slice is ready.
> - Skill at `skills/morning-trading-briefing/`. Pipeline works end-to-end
>   (today, 2026-05-27, produced 37 calendar events across 3 morning runs
>   + a markdown brief each time). The bug is duplication and snapshot
>   drift, not plumbing.
> - Running in no-IB / manual-holdings mode
>   (`integration.ib_integration: false`). `FMP_API_KEY` is in the env.
>   Network allowlist documented at `references/NETWORK_ALLOWLIST.md`.
>
> Four upgrade vectors, in priority order:
>
> 1. **Idempotency / upsert-by-key (v2.1).** Today's three reruns created
>    three "Morning Brief" all-day events on My Positions, three "Market
>    Updates" all-day events, and duplicate timed events for CRM, MRVL,
>    SNPS, PDD, ECB, Richmond Fed, Dallas Fed, Fed-Logan, Fed-Cook.
>    Descriptions already carry `<!-- mtb-key: mtb:YYYY-MM-DD:cal:slug -->`
>    markers — the *intent* was upsert, but the calendar writer is
>    insert-only. Fix: before writing an event, `list_events` on the
>    target calendar for that day, scan descriptions for matching
>    `mtb-key`, and `update_event` in place if found; otherwise
>    `create_event`. Same key rule for Drive markdown: one file per
>    (date, mode), overwritten on rerun.
>
> 2. **Snapshot consistency (v2.2).** Today's three runs reported the
>    same SPY price (750.59) with three different intraday % changes
>    (+1.06%, +0.09%, -0.04%) — each run pulled quotes at a different
>    moment without recording the as-of timestamp. Fix: capture
>    `as_of_utc` once at the start of `compose_brief.py`, thread it
>    through quote fetches, and render `Snapshot as of HH:MM ET` in the
>    header so a reader picking up an older brief can see it's stale.
>
> 3. **Noise reduction (v2.3).** 37 events for one day is too many to
>    read. Target ≤ 12 events per day total across the four calendars.
>    Concrete cuts: (a) drop Tier-3 macro events (Dallas Fed Texas Retail
>    Outlook, Richmond Fed Survey of Manufacturing Activity-as-separate-
>    -from-the-headline-index, etc.) unless explicitly opted in; (b) cap
>    earnings to top 8 by `max(market_cap, implied_move × market_cap)`;
>    (c) collapse the multiple all-day "Morning Brief" / "Market Updates"
>    events — falls out of the v2.1 upsert fix.
>
> 4. **Manual holdings schema (v2.4, deferred).** Design the `holdings:`
>    config block covering IB + Robinhood combined. Discuss schema with
>    me before writing code. Don't start until v2.1-v2.3 ship.
>
> **First step:** read this file end-to-end, then read
> `scripts/compose_brief.py` and the calendar-writing code path.
> Confirm your understanding of the upsert gap with me before changing
> code. Then ship slice 1 (idempotency) as its own PR.

---

## What today (2026-05-27) showed us

Three full brief regenerations between ~01:20 ET and ~07:00 ET produced:

- **3× duplicate "Morning Brief" all-day events** on My Positions calendar
- **3× duplicate "Market Updates" all-day events** on Market Updates calendar
- **Duplicate timed earnings events** for CRM (3×), MRVL (2×), SNPS (2×),
  PDD (2×) on Earnings calendar
- **Duplicate macro events** for ECB Press Conference, Richmond Fed
  Manufacturing, Dallas Fed Services, Fed-Logan, Fed-Cook on Macro Events
  — same underlying event scheduled twice with slightly different start
  times across runs
- **Internal inconsistency:** brief #1 said "SPY +1.06%", brief #2 said
  "+0.09% pre-mkt", brief #3 said "-0.04%". Same underlying price, three
  different framings, no timestamps. A reader picking up an older brief
  has no way to know it's stale.

All 37 events were hand-deleted at end of day. The skill produced the
*right content* — the failure modes are dedup and snapshot timestamps.

## Upgrade backlog

### v2.1 — Idempotency [PRIORITY]
- [ ] Calendar writer reads existing events for the day, matches on
      `mtb-key` in description, upserts (`update_event` or `create_event`).
- [ ] Markdown writer overwrites canonical Drive path
      `briefings/YYYY-MM-DD-{morning|afternoon}.md` instead of appending.
- [ ] Idempotency test: run the brief twice back-to-back; verify event
      count + Drive file count unchanged after the second run.

### v2.2 — Snapshot consistency
- [ ] Capture `as_of_utc` once at start of `compose_brief.py`.
- [ ] Quote-fetch helpers take `as_of` and use it for any %-change math.
- [ ] Rendered header includes "Snapshot as of HH:MM ET".
- [ ] Calendar all-day event titles include the as-of timestamp so any
      duplicates that slip through are visibly distinguishable.

### v2.3 — Noise reduction
- [ ] Config switch `macro.include_tier3: false` (default) drops Dallas
      Fed Texas Retail Outlook, Richmond Fed Survey of Manufacturing
      Activity (the separate "survey" entry from the headline index), etc.
- [ ] Earnings cap: top N by `max(market_cap, implied_move × market_cap)`,
      default N=8.
- [ ] Document expected event count per day in SKILL.md (target ≤ 12).

### v2.4 — Manual holdings schema [DEFERRED]
- [ ] Design `holdings:` config block covering IB + Robinhood combined.
- [ ] Discuss schema with user before writing code.

## Open decisions

- **Scheduled cloud daily run?** Once v2.1 lands and dedup is reliable,
  decide whether to set up a scheduled cloud run (cron / launchd in the
  cloud env) calling `/morning-brief` automatically. Currently triggered
  manually.
- **Afternoon brief.** SKILL.md mentions `/afternoon-brief` but today
  only morning was run. Confirm afternoon is in scope for v2.
- **Phase 2 (IB integration on VPS).** Still deferred per prior plan.
  Don't start until v2.1-v2.3 have been validated for 2-3 weeks of
  daily use.

## See also

- `SKILL.md` — full pipeline overview
- `references/NETWORK_ALLOWLIST.md` — egress hosts for cloud env
- `references/BRIEF_DATA_SCHEMA.md` — `brief_data.json` schema
- Today's calendar cleanup — see git log; no code changed, just deletions
