# Briefing Template

The morning-trading-briefing skill renders into this template. `{{var}}` are filled at runtime; sections wrapped in `<!-- if:foo -->` are toggled by `config.yaml`.

---

## Morning Template

```markdown
# Morning Brief — {{date_long}}
*Generated {{generated_at_et}} ET — SPY {{spy_premarket}} | DXY {{dxy}} | 10Y {{us10y}} | VIX {{vix}}*

## Must-read today
1. {{must_read_1}}
2. {{must_read_2}}
3. {{must_read_3}}

---

## Macro day-ahead

### Economic releases
{{#each econ_release}}
**{{time_et}} ET — {{name}}** *(consensus {{consensus}} | prior {{prior}})*

*What:* {{what}}
*How measured:* {{how_measured}}
*Why it matters:* {{why_matters}}
*Reaction history:* {{reaction_history}}
→ *Watch:* {{watch_for_today}}

{{/each}}

### Fed speakers
{{#each fed_speaker}}
- **{{time_et}} ET** — {{name}} ({{voter_status}}, recent lean: {{lean}}) — {{topic}}
{{/each}}

### Overnight
- Asia close: Nikkei {{nikkei}} | HSI {{hsi}} | KOSPI {{kospi}}
- Europe open: DAX {{dax}} | FTSE {{ftse}} | STOXX {{stoxx}}
- Top overnight headline: {{top_overnight_headline}}

### Rates
- 2Y {{us2y}} | 10Y {{us10y}} | 30Y {{us30y}}
- 2s10s: {{curve_2s10s}} bps ({{curve_direction}})
- Real 10Y: {{real_10y}}%
- Fed funds futures imply {{ff_implied_path}} cuts/hikes through {{ff_horizon}}
→ *So what:* {{rates_so_what}}

### Commodities
| Ticker | Last | 1d% | Catalyst |
|---|---|---|---|
| WTI | {{wti}} | {{wti_chg}} | {{wti_catalyst}} |
| Brent | {{brent}} | {{brent_chg}} | |
| Gold | {{gold}} | {{gold_chg}} | |
| Copper | {{copper}} | {{copper_chg}} | |
| Nat gas | {{natgas}} | {{natgas_chg}} | |

*EIA/OPEC days flagged: {{eia_opec_today}}*

### FX / crypto
- DXY {{dxy}} ({{dxy_chg}}) | EUR/USD {{eurusd}} | USD/JPY {{usdjpy}}
- BTC {{btc}} ({{btc_chg}}) | ETH {{eth}} ({{eth_chg}})
→ *So what:* {{fx_so_what}}

### Sector ETF pre-market
{{sector_etf_table}}
→ *Rotation read:* {{rotation_read}}

### Pre-market movers
{{#each premarket_mover}}
- **{{ticker}}** {{change}} — {{catalyst}}
{{/each}}

---

## Earnings today

### Mega-caps reporting
{{#each megacap_earning}}
**{{ticker}} — {{timing}} | EPS est {{eps_est}} | Rev est {{rev_est}}** — implied move {{implied_move}}%
{{/each}}

### Your positions reporting
{{#each my_earning}}
**{{ticker}} — {{timing}}**
- EPS est: {{eps_est}} | Rev est: {{rev_est}}
- Implied move from IV: {{implied_move}}%
- Your exposure: {{position_summary}} (delta {{delta}})
- Recommendation: {{hedge_recommendation}}
{{/each}}

---

## My positions

### Overnight P&L
{{pnl_table}}

### Stop-loss alerts
{{#each stop_alert}}
- **{{ticker}}** — closed {{last}} vs. stop {{stop_price}} ({{distance_pct}}% away) — {{action}}
{{/each}}

### Short legs needing attention
{{#each short_leg_alert}}
- **{{symbol}}** — delta {{delta}} | DTE {{dte}} | {{reason}} — roll candidates: {{roll_top_3}}
{{/each}}

### News + unusual options flow on holdings
{{#each holding_event}}
- **{{ticker}}** — {{event_type}} — {{summary}}
{{/each}}

### Earnings within 7 days on holdings
{{#each upcoming_my_earning}}
- **{{ticker}}** — {{date}} {{timing}} — implied move {{implied_move}}% — consider: {{prep_action}}
{{/each}}

---

## Opportunities

### Scanner-bullish top 3
{{scanner_bullish_table}}

### Scanner-PMCC top 3
{{scanner_pmcc_table}}

### Notable insider buying
{{#each insider_buy}}
- **{{ticker}}** — {{insider_name}} ({{title}}) bought ${{value}} on {{date}}
{{/each}}

---
*Noise log: {{noise_log_path}} — jot one line after market close on what was missing or unused.*
```

---

## Afternoon Template

```markdown
# Afternoon Brief — {{date_long}}
*Generated {{generated_at_et}} ET — SPY {{spy_close}} ({{spy_chg}}) | DXY {{dxy_close}} | 10Y {{us10y_close}} | VIX {{vix_close}}*

## Today's recap

### What moved & why
{{#each market_move}}
- **{{topic}}**: {{summary}}
{{/each}}

### Your P&L
{{pnl_recap_table}}
*Day P&L: {{day_pnl}} | Week P&L: {{week_pnl}} | YTD: {{ytd_pnl}}*

### Biggest position movers
{{#each my_top_mover}}
- **{{ticker}}** {{change}} — {{driver}}
{{/each}}

---

## Closing-bell positioning ({{minutes_to_close}} min to close)
{{closing_bell_actions}}

---

## Overnight risks

### Asia data on the docket
{{#each asia_release}}
- **{{time_et}} ET — {{name}}** (consensus {{consensus}}) — {{impact}}
{{/each}}

### AMC earnings on your tickers
{{#each amc_earning}}
- **{{ticker}}** — EPS est {{eps_est}} | implied move {{implied_move}}% — exposure: {{position_summary}}
{{/each}}

### Geopolitical / policy headlines
{{geopolitical_summary}}

---

## Tomorrow's setup

### Econ calendar
{{tomorrow_econ_table}}

### Fed speakers tomorrow
{{tomorrow_fed_speakers}}

### Earnings tomorrow (mega-caps + your tickers)
{{tomorrow_earnings_table}}

### Key levels to watch
- SPY: support {{spy_support}} / resistance {{spy_resistance}}
- {{custom_levels}}
```
