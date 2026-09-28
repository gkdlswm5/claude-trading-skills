# Sourced-News — Quality & Anti-Bias Contract

This contract covers every brief field sourced from live `WebSearch` rather than a
deterministic feed: `geopolitical_summary`, `rates_news` (bonds/Treasury supply/Fed
drivers), and `commodities_news` (energy/metals/ags). These are the highest
bias/clickbait risk and run on both automated and manual invocations. This document
is the runtime contract; `check_news_quality.py` enforces the mechanical parts and
is applied identically to all three fields.

## Goal

State **what happened** and **the observed cross-asset move** — attributed,
quantified, corroborated. Never punditry, never price predictions, never a thesis.

## The four bias controls

Bias enters a news summary through four doors; each gets a specific control.

### 1. Selection bias — *which stories get picked*
- **Fixed source allowlist** (see below). Do not open-search the web; query the
  allowlisted Tier-1 outlets and primary sources only.
- **Market-linkage scope filter:** an item qualifies only if it has an observable
  cross-asset effect (equities, rates, FX, commodities, crypto). Drama with no
  price linkage is dropped.

### 2. Framing bias — *how it's worded*
- **Fact / interpretation separation:** each item is two clauses — *what happened*
  (attributed) + *the observed move*. e.g.
  `Hormuz transit restriction confirmed (Reuters, AP) — Brent +2.1% to $X`.
- **Neutral lexicon:** direction + magnitude only. Banned emotive/judgment words:
  soared, plunged, plummeted, skyrocketed, tanked, crushed, slammed, cratered,
  collapsed, exploded, panic, fear(s), chaos, carnage, bloodbath, meltdown,
  rout(ed), devastating, stunning, shocking, massive, frenzy, turmoil.
- **No price predictions / no trade calls** in this section.

### 3. Source bias — *one outlet's slant*
- **≥2-source corroboration:** a claim ships only if two *independent* Tier-1
  outlets carry it. Primary sources outrank secondary reporting.
- **Confidence tags:** `CONFIRMED` (official/primary), `REPORTED` (≥2 wires),
  `UNCONFIRMED` (single source). Default ships only CONFIRMED + REPORTED;
  UNCONFIRMED is dropped or explicitly labeled.

### 4. Confirmation bias — *fitting news to a prior*
- State the **observed** move even when it contradicts the day's thesis. Include
  disconfirming data if present. The geo wrap reports reality, not the setup.

## Source allowlist

**Tier-1 (facts):** Reuters, Associated Press / AP, Bloomberg, Financial Times /
FT, Wall Street Journal / WSJ.
**Primary (outrank all):** central-bank statements (Federal Reserve / Fed, ECB,
BOJ, PBoC, Bank of England / BoE), SEC, EIA, OPEC, US Treasury, White House,
official government / company releases and filings.
**Excluded:** social media, aggregators, opinion/editorial pages, single-author
blogs, unattributed "sources say" pieces.

See `../market-news-analyst/references/trusted_news_sources.md` for the full tiering.

## Format (each item)

```
<CONFIDENCE> <what happened, attributed (Source, Source)> — <observed market move with number>
```

Examples (good):
- geo: `CONFIRMED ECB held the deposit rate at 3.00% (ECB statement) — EUR/USD +0.4% to 1.16, DXY -0.3%`
- geo: `REPORTED Hormuz transit restriction eased (Reuters, Bloomberg) — Brent -1.8% to $X`
- bonds: `CONFIRMED Treasury 7Y auction tailed 1.2bp (US Treasury, Bloomberg) — 10Y +3bps to 4.49%`
- commodities: `CONFIRMED EIA crude draw of 5.1M bbl (EIA, Reuters) — WTI +1.4%`

Examples (rejected):
- `Oil soared as fears gripped the market` → banned lexicon, no source, no number
- `Brent likely heads to $120 next` → price prediction
- `OPEC+ surprise cut sends crude +4%` → quantified move, no source attribution

## Validator

Run before publishing — on each sourced field (`geopolitical_summary`,
`rates_news`, `commodities_news`):

```bash
python3 scripts/check_news_quality.py --text "<field text>"
# or
python3 scripts/check_news_quality.py --file news.txt --json
```

**Hard fails (exit 1, hold that field):**
- banned-lexicon word present
- a quantified market claim (%/$/bps) with no allowlisted source attribution

**Warnings (exit 0, surfaced for review):**
- prediction language (will, likely, expect, poised to, target, forecast)
- `unconfirmed` / `reportedly` / `rumored` markers

On hard fail, omit that field rather than publish it — a missing wrap is
better than a biased or unsourced one.
