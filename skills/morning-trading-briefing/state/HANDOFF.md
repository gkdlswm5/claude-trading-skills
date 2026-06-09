# Session Handoff — Morning Trading Briefing v2

Paste the **Prompt to start the next session** block below into a fresh
**Claude Code session on Hostinger** to begin v2. Everything else here
is reference.

> **Deployment target: Hostinger VPS.** Development happens on PC/laptop
> for fast iteration, but the production daily run lives on the VPS.
> Both clones share code via GitHub; configs and secrets live separately
> on each machine. See `references/HOSTINGER_DEPLOY.md`.

---

## Prompt to start the next session

> Continue the morning-trading-briefing v2 upgrade. Goal: replace the
> Claude-driven MCP write path with deterministic Python so the daily
> brief is idempotent, cheap, and reliable enough to run unattended from
> Hostinger cron.
>
> Context:
> - Repo `gkdlswm5/claude-trading-skills`, branch `claude/eager-bardeen-VysCZ`.
>   Branch is current with main. Work locally; commit + push when each
>   slice is ready.
> - Skill at `skills/morning-trading-briefing/`. The pipeline produced
>   the right *content* on 2026-05-27 but generated 37 calendar events
>   across three runs (target ~12). Failure modes: no dedup, no snapshot
>   timestamps.
> - Mode: no-IB / manual-holdings (`integration.ib_integration: false`).
>   `FMP_API_KEY` is in the env.
> - Deployment target: Hostinger VPS, scheduled cron. See
>   `references/HOSTINGER_DEPLOY.md` and `references/GOOGLE_API_SETUP.md`.
>
> **Architecture change — Claude does synthesis, Python does writes.**
> Today the LLM calls Google Calendar/Drive via MCP to write events and
> markdown. This is what broke (creative model doing mechanical
> bookkeeping). v2.0 moves the writes into Python: one Anthropic API
> call produces `brief_data.json`; Python reads that JSON and calls
> Google Calendar + Drive APIs directly via `google-api-python-client`.
> Idempotency becomes free — a `upsert_event(calendar_id, mtb_key,
> payload)` helper is deterministic by construction.
>
> Six work slices, in order. Each ships as its own PR.
>
> 1. **v2.0 — Google API direct writes (prerequisite for everything).**
>    Implement `scripts/google_calendar_client.py` and
>    `scripts/google_drive_client.py` (scaffolds already in repo). One-time
>    Google OAuth setup per `references/GOOGLE_API_SETUP.md`. Add deps
>    to `requirements.txt`. Test against a throwaway test calendar
>    before touching real ones.
>
> 2. **v2.1 — Idempotency.** Calendar writer upserts by `mtb-key`
>    extracted from event description. Drive writer overwrites canonical
>    `briefings/YYYY-MM-DD-{morning|afternoon}.md`. Test: run brief
>    twice back-to-back, verify event/file counts unchanged.
>
> 3. **v2.2 — Snapshot consistency.** Capture `as_of_utc` once at start
>    of `compose_brief.py`. Thread through quote-fetch helpers. Render
>    "Snapshot as of HH:MM ET" in header. Include timestamp in all-day
>    event titles.
>
> 4. **v2.3 — Noise reduction.** Config switch `macro.include_tier3:
>    false` (default). Earnings cap to top N by `max(market_cap,
>    implied_move × market_cap)`, default N=8. Target ≤ 12 events/day
>    total across calendars.
>
> 5. **v2.4 — Manual holdings schema [DEFERRED until 2.0–2.3 ship].**
>    Design `holdings:` config block covering IB + Robinhood combined.
>    Discuss schema before writing code.
>
> 6. **v2.5 — Hostinger cron deployment.** Per
>    `references/HOSTINGER_DEPLOY.md`. SSH to VPS, clone, set up env,
>    configure cron, validate against a quiet test calendar for 3 days
>    before pointing at real calendars.
>
> **First step right now:** read this file end-to-end, then read
> `scripts/compose_brief.py` and the existing MCP-driven calendar/Drive
> write path. Confirm with me that you understand (a) the LLM/Python
> boundary in v2.0 and (b) which existing functions get refactored vs
> deleted. Then ship v2.0 as the first PR.

---

## What today (2026-05-27) showed us

Three full brief regenerations between ~01:20 ET and ~07:00 ET produced:

- **3× duplicate "Morning Brief" all-day events** on My Positions
- **3× duplicate "Market Updates" all-day events** on Market Updates
- **Duplicate timed earnings events** for CRM (3×), MRVL (2×), SNPS (2×),
  PDD (2×) on Earnings
- **Duplicate macro events** for ECB Press Conference, Richmond Fed
  Manufacturing, Dallas Fed Services, Fed-Logan, Fed-Cook on Macro Events
  — same event scheduled twice with slightly different start times
- **Internal inconsistency:** brief #1 said "SPY +1.06%", brief #2 said
  "+0.09% pre-mkt", brief #3 said "-0.04%". Same price, three different
  framings, no timestamps.

All 37 events were hand-deleted at end of day. The skill produced the
right *content* — failure modes are dedup and snapshot timestamps,
both of which point at the same root cause: the LLM is doing mechanical
work it isn't reliable at. v2.0 fixes the root cause.

## Upgrade backlog

### v2.0 — Google API direct writes [SHIPPED]
- [x] Implement `scripts/google_calendar_client.py` — authenticate (+ CLI
      flow), list_events_for_day, upsert_event (list→match-by-mtb-key→
      patch-or-create), delete_events_by_key
- [x] Implement `scripts/google_drive_client.py` — authenticate (shared
      token.json), find_file_by_name, upsert_markdown (overwrite by name
      in folder)
- [x] Add `google-api-python-client`, `google-auth-httplib2`,
      `google-auth-oauthlib` to `requirements.txt`
- [x] Frame `brief_data.json` as the LLM/Python boundary in
      `compose_brief.py` docstring; SKILL.md Pipeline diagram updated
- [x] New `scripts/write_brief_outputs.py` — reads
      `briefings/YYYY-MM-DD-{mode}.{md,events.json}`, validates mtb-key
      markers, upserts each event + the markdown
- [x] SKILL.md Step 7 + Step 8 collapsed to one `write_brief_outputs.py`
      invocation; first-run OAuth setup documented inline
- [x] `config.example.yaml` extended with `google:` block (credentials_path,
      token_path)
- [x] 30 unit tests cover: extract_mtb_key edge cases, list pagination,
      upsert insert/patch/multi-match, delete-by-key, Drive find/upsert,
      config parsing, payload conversion (timed + all-day shape),
      validation gating, and a CLI smoke test that runs compose_brief →
      write_brief_outputs --dry-run end-to-end
- [ ] **User-side:** complete OAuth setup per `GOOGLE_API_SETUP.md`
      Steps 1–5 (Google Cloud project + Calendar/Drive APIs enabled +
      Desktop OAuth client + `credentials.json` in
      `~/.config/morning-briefing/`). Walkthrough delivered in the v2.0
      session.
- [ ] **User-side (Hostinger):** scp `credentials.json` + `token.json`
      to VPS once you have them. Lands in v2.5.
- [ ] **Deferred to v2.1:** the back-to-back idempotency proof test, the
      multi-match cleanup (delete extras when upsert finds >1 hit), and
      the first real-calendar smoke test against a throwaway calendar.

### v2.1 — Idempotency [code complete; live-calendar proof pending]
- [x] Calendar writer upserts by `mtb-key` (extract from description) —
      landed in v2.0's `google_calendar_client.upsert_event`
- [x] Drive writer overwrites canonical
      `briefings/YYYY-MM-DD-{morning|afternoon}.md` — landed in v2.0's
      `google_drive_client.upsert_markdown`
- [x] Multi-match cleanup: `upsert_event` now patches the first match and
      DELETEs the rest, so a rerun collapses leftover duplicates (the
      2026-05-27 incident) to one event per key. Self-healing, not just
      duplicate-avoiding.
- [x] Unit-level back-to-back idempotency proof: stateful fake-calendar
      test runs `upsert_event` twice → exactly one event, same ID; plus a
      "3 seeded dupes collapse to 1, then stay 1" test
      (`test_google_clients.py`).
- [ ] Real-calendar idempotency test: run brief 2× back-to-back against
      a throwaway test calendar; verify event count unchanged and event
      IDs stable. **Blocked on user-side OAuth + `config.yaml` calendar
      IDs** (see v2.0 user-side items above).
- [ ] Drive: same back-to-back idempotency proof (file ID stable, content
      replaced, no duplicate file in folder). Same live-calendar blocker.

### v2.2 — Snapshot consistency + readability signals [code complete]
- [x] Single snapshot moment: `signals.as_of_et()` derives one "HH:MM ET"
      from the `generated_at_et` the LLM already captures in brief_data.json.
      (In the v2.0+ architecture the LLM assembles all quotes into the JSON —
      there are no Python quote-fetch helpers to thread through; the single
      `generated_at_et` IS the captured-once snapshot moment. This is the
      faithful reading of the original "capture as_of_utc once" intent.)
- [x] Header renders "Snapshot as of HH:MM ET" (morning + afternoon),
      replacing the old "Generated …" label.
- [x] All-day event titles include the as-of stamp as "(as of HH:MM ET)".
      CRITICAL: the stamp is in PARENS and added AFTER the dedup key is
      computed, so `_slug()` strips it and v2.1 idempotency holds — verified
      live (run @07:00 then @09:30 → titles update in place, event count
      6→6, no duplicates).
- [x] Readability signals (folded in): `signals.signal()/tag()` add 🟢/🔴
      good-for-your-book markers (standard risk-on: indices/P&L up = 🟢;
      VIX/yields/DXY up = 🔴) on the snapshot change, P&L, and movers only.
      Emoji chosen because it's the ONLY formatting that survives all three
      surfaces (PDF, calendar body, calendar title) — verified empirically;
      Google strips inline color spans. Colored text reserved for the PDF.
- [ ] HTML "View full brief (PDF)" link in the My Positions event body —
      `<a href>` confirmed to survive in calendar descriptions, but BLOCKED
      on Drive archiving being enabled (needs `drive.briefings_folder_id`).
      Deferred until Drive is turned on.

### v2.3 — Noise reduction
- [ ] `macro.include_tier3: false` (default) drops Tier-3 macro events
- [ ] Earnings cap: top N by `max(mcap, implied_move × mcap)`, N=8
- [ ] SKILL.md documents expected event count per day (≤ 12)

### v2.4 — Manual holdings schema [DEFERRED]
- [ ] Design `holdings:` block covering IB + Robinhood combined
- [ ] Discuss schema with user before writing code

### v2.5 — Hostinger cron deployment
- [ ] Follow `references/HOSTINGER_DEPLOY.md`
- [ ] Validate against test calendar for 3 days
- [ ] Point at real calendars
- [ ] Log rotation + monitoring

## Open decisions

- **Afternoon brief.** SKILL.md mentions `/afternoon-brief` but only
  morning was run today. Confirm afternoon is in scope for v2.
- **Multi-machine config sync.** PC and Hostinger each have their own
  `config.yaml`. For now, edit each separately; revisit if drift
  becomes a problem.
- **Phase 2 (IB integration).** Still deferred. Same VPS will host it
  when the time comes; setting up v2 on the VPS now puts the env in
  place for free.

## See also

- `SKILL.md` — full pipeline overview
- `references/HOSTINGER_DEPLOY.md` — VPS setup + cron
- `references/GOOGLE_API_SETUP.md` — OAuth walkthrough
- `references/NETWORK_ALLOWLIST.md` — egress hosts (cloud env only)
- `references/BRIEF_DATA_SCHEMA.md` — `brief_data.json` schema
- `scripts/google_calendar_client.py` — scaffold (implement in v2.0)
- `scripts/google_drive_client.py` — scaffold (implement in v2.0)
