# Best practices for iterating on the briefing

The briefing is only as good as the feedback loop you build around it. Tips below in priority order.

## 1. Keep a noise log

After each briefing, jot **one line** in `briefings/noise_log.md`:
```
2026-05-21 morning: didn't need OPEC section. wished I had FOMC minutes preview earlier.
2026-05-22 morning: NVDA implied move call was useful. "sector rotation" felt generic.
```
Once a week, prune `config.yaml` based on the log. This is the single highest-leverage habit.

## 2. Score the briefing weekly

Sunday — 5-minute review:
- Did the brief flag what actually moved my P&L last week?
- What surprised me that should have been in the brief?
- Anything I skipped reading? Why?

Write down 1–2 changes for next week. Commit them.

## 3. Edit config, not code

All personalization lives in `config.yaml`. If you find yourself wanting to edit `SKILL.md` to change a threshold, add the threshold to config first.

## 4. Three sections deep, no deeper

Every section ends with a "→ So what" line that ties to your book. If a section can't end with a "so what", it's a data dump — cut it or move it to context.

## 5. Build the indicator explainer once, freeze it

The "what is Core CPI" content doesn't change. Write it once in `econ-indicator-explainer/references/indicators.md`, version it, freeze it. Don't have the LLM regenerate explanations daily — that's where hallucinations creep in.

## 6. Cache slow stuff

Earnings calendar, econ calendar, Fed speakers — fetch once per day, cache to `state/cache/`. Don't re-hit APIs each briefing.

## 7. Track implied vs. realized reactions

Over time, log: when CPI surprised hot/cold, what did SPY/TLT/DXY actually do in the next 60 min? This builds **your** reaction-history dataset — beats generic textbook explanations within a few months.

Store as `state/reaction_history/{indicator}.csv` with columns: date, surprise, spy_60m, tlt_60m, dxy_60m, vix_60m.

## 8. Top-of-brief discipline

If the must-read top 3 ever has more than 3 items, your brief is broken. Force the synthesis.

## 9. Version the template

Every template change goes through git on this branch. Tag major rewrites like `brief-v2`. When something regresses, `git diff` tells you what changed.

## 10. Manual first, automate second

Run `/morning-brief` manually for ~10 sessions. Then once it's stable, wire automation:
- **Option A** — `loop` skill: `/loop 1d /morning-brief` (Claude Code session must be open)
- **Option B** — SessionStart hook on a dedicated session that triggers at 6:45am / 3:15pm
- **Option C** — launchd / cron on your Mac that opens a Claude Code session with `/morning-brief` as the initial prompt

Don't automate a broken format. Automating amplifies whatever shape the brief is in.
