# Morning Trading Briefing — Roadmap & Idea Backlog

Running backlog so nothing requested is lost. Shipped items move to "Done"; new
ideas land in "Future ideas" and get promoted into a phase when greenlit.

## Done

- No-IB mode; Market Updates digest calendar; idempotent (upsert) calendar writes.
- News quality gate (`check_news_quality.py`) on geo + bonds + commodities news.
- BI charts (matplotlib PNG) + unicode sparklines; ELI5 plain-English layer (light/medium/heavy).
- **Phase 1 — smart calendar:** earnings → one ranked digest; impact tags + color
  + sort; bottom-line headline; quiet-day honesty; minor-news filter w/ notability override.
- **Phase 2 (partial):** key technical levels (`technicals.py` — 50/200 DMA, 20d
  support/resistance, trend); risk-regime one-liner (SPY vs MAs + VIX + breadth);
  bold-your-tickers in must-read + bottom line.

## Phase 2 — remaining

- **What-changed-since-yesterday** — diff today's brief_data vs the prior day's
  archived JSON; 2-3 line delta block near the top. (Needs a small state read.)
- **Number-format polish** — consistent decimals / % / thousands separators helper.
- **Risk-regime upgrade** — optionally swap the inline read for the repo's
  `macro-regime-detector` skill (adds credit/cross-asset inputs).

## Phase 3 — needs external data

- **Econ-surprise tracking** — actual vs consensus + running tally (mainly the
  afternoon recap, since morning is pre-release).
- **Credit & vol stress** — MOVE index, HY/IG OAS via FRED as a stress gauge line.

## Future ideas (unscheduled — capture, don't lose)

- Options positioning: put/call ratio, gamma / max-pain, straddle-implied move (needs options feed).
- Fund-flow / COT positioning context.
- Sector heatmap PNG (in addition to the bar chart).
- Financial Conditions Index one-liner.
- Per-event reminders only on HIGH-impact calendar entries.
- "Trade idea" lines with conviction + R:R (tie into position-sizer).
- Link each econ event to its explainer card in the markdown.
