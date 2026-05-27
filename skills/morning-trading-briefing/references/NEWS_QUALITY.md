# Geopolitical Wrap — Quality & Anti-Bias Contract

The `geopolitical_summary` is the only brief section sourced from live `WebSearch`
rather than a deterministic feed. It is therefore the highest bias/clickbait risk
and runs on both automated and manual invocations. This document is the runtime
contract; `check_geo_quality.py` enforces the mechanical parts.

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
- `CONFIRMED ECB held the deposit rate at 3.00% (ECB statement) — EUR/USD +0.4% to 1.16, DXY -0.3%`
- `REPORTED Hormuz transit restriction eased (Reuters, Bloomberg) — Brent -1.8% to $X`

Examples (rejected):
- `Oil soared as fears gripped the market` → banned lexicon, no source, no number
- `Brent likely heads to $120 next` → price prediction
- `Tensions escalating dramatically` → no attribution, no market linkage, emotive

## Validator

Run before publishing:

```bash
python3 scripts/check_geo_quality.py --text "<geopolitical_summary>"
# or
python3 scripts/check_geo_quality.py --file geo.txt --json
```

**Hard fails (exit 1, hold the geo block):**
- banned-lexicon word present
- a quantified market claim (%/$/bps) with no allowlisted source attribution

**Warnings (exit 0, surfaced for review):**
- prediction language (will, likely, expect, poised to, target, forecast)
- `unconfirmed` / `reportedly` / `rumored` markers

On hard fail, omit the geo block rather than publish it — a missing wrap is
better than a biased or unsourced one.
