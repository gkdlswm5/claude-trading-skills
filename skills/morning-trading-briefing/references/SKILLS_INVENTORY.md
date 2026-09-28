# Skills Inventory — what feeds each section

Maps every brief section to the existing skill (or external data source) that supplies it. Use this when debugging "why is section X empty" or planning new sections.

## Section → Skill mapping

### Morning brief

| Section | Skills used | Status |
|---|---|---|
| Must-read top 3 | (synthesized from other sections) | needs orchestration logic |
| Macro — econ releases | `economic-calendar-fetcher` + `econ-indicator-explainer` (NEW in A) | partial |
| Macro — Fed speakers | `economic-calendar-fetcher` (verify it covers speakers) | verify |
| Macro — overnight Asia/Europe | `market-news-analyst` + WebFetch | exists |
| Macro — rates snapshot | NEW skill `rates-snapshot` OR FRED API via Bash | gap |
| Macro — commodities | `stock-quote` on commodity ETFs (USO/BNO/GLD/CPER/UNG) | workable |
| Macro — FX / crypto | `stock-quote` on UUP/FXE/FXY + crypto tickers | workable |
| Macro — sector ETFs | `sector-analyst` | exists |
| Macro — pre-market movers | `finviz-screener` or NEW skill | gap |
| Earnings — mega-caps + holdings | `earnings-calendar` + `earnings-trade-analyzer` + `greeks` | exists |
| Positions — P&L | `ib-portfolio` | exists |
| Positions — stop alerts | `ib-stop-loss` | exists |
| Positions — short legs / rolls | `ib-find-short-roll` + `ib-pmcc-advisor` | exists |
| Positions — news on holdings | `news-sentiment` | exists |
| Positions — unusual flow | `whale-hunting` | exists |
| Opportunities — bullish setups | `scanner-bullish` | exists |
| Opportunities — PMCC candidates | `scanner-pmcc` | exists |
| Opportunities — insider buying | `insider-trading` | exists |
| Output — calendar events | Google Calendar MCP | exists |
| Output — Drive archive | Google Drive MCP | exists |

### Afternoon brief

| Section | Skills used |
|---|---|
| Today's recap — indices/P&L | `stock-quote` + `ib-portfolio` |
| What moved & why | `market-news-analyst` + `news-sentiment` |
| Closing-bell positioning | `ib-portfolio-action-report` + `ib-stop-loss` |
| Overnight risks — Asia | `economic-calendar-fetcher` (Asia filter) |
| Overnight risks — AMC earnings | `earnings-calendar` + `greeks` |
| Tomorrow's setup | `economic-calendar-fetcher` + `earnings-calendar` |

## Gaps to address

**Step A (build now):**
1. **`econ-indicator-explainer`** — static knowledge base mapping indicator name → {what, how measured, why matters, reaction history}. No API calls. ~30 indicators.

**Step B (orchestration):** glue the above skills together, render template, push to Calendar + Drive.

**Future skills (not blocking initial launch):**
- `rates-snapshot` — dedicated Treasury yield curve fetcher (FRED API)
- `commodities-snapshot` — with EIA inventory schedule
- `fx-snapshot` — DXY components, major pairs
- `premarket-movers` — top gappers + catalysts
- `global-econ-calendar` — ECB/BOJ/China/OPEC focus
- `fed-speakers-tracker` — voter status + recent hawkish/dovish lean

Workarounds in the meantime: use `stock-quote` / `market-news-analyst` / WebFetch.

## Convention reminder

When this briefing skill needs data, **always prefer the dedicated skill** over re-implementing the data fetch. Skills are the unit of reuse — if `sector-analyst` is wrong about XLE, fix it in `sector-analyst`, not here.
