# brief_data.json Schema

The orchestrator skill assembles a single JSON object and passes it through `compose_brief.py` for rendering + calendar-event generation. This is the contract — keep this schema stable; renderer/composer adapt to it.

`mode` switches between morning and afternoon shapes. See `scripts/examples/sample_morning.json` and `sample_afternoon.json` for full populated examples.

---

## Morning shape

```jsonc
{
  "mode": "morning",
  "date": "YYYY-MM-DD",
  "generated_at_et": "YYYY-MM-DD HH:MM ET",

  "snapshot": {
    "spy": "string",
    "spy_premarket": "+0.3%",
    "dxy": "string",
    "us10y": "string",
    "vix": "string"
  },

  "must_read": ["item 1", "item 2", "item 3"],

  "econ_releases": [
    {
      "time_et": "08:30",
      "name": "Consumer Price Index (CPI) YoY",
      "consensus": "3.1%",
      "prior": "3.0%",
      // Following 5 fields come from econ-indicator-explainer
      // lookup_indicator.py --json "<name>" → use sections.what_it_is etc.
      "what": "...",
      "how_measured": "...",
      "why_matters": "...",
      "reaction_history": "...",
      "watch_for_today": "..."
    }
  ],

  "fed_speakers": [
    {"time_et": "10:00", "name": "Powell", "voter_status": "voter|non-voter|chair",
     "lean": "hawkish|neutral|dovish", "topic": "..."}
  ],

  "overnight": {
    "nikkei": "...", "hsi": "...", "kospi": "...",
    "dax": "...", "ftse": "...", "stoxx": "...",
    "top_headline": "..."
  },

  "rates": {
    "us2y": "4.58", "us10y": "4.32", "us30y": "4.41",
    "curve_2s10s": "-26", "curve_direction": "flattening|steepening",
    "real_10y": "1.85",
    "ff_implied_path": "2 cuts", "ff_horizon": "year-end 2026",
    "so_what": "..."
  },

  // Optional. Sourced bonds/rates news (Treasury supply/auctions, Fed drivers,
  // credit). Same NEWS_QUALITY.md gate as geo — Tier-1 sources, corroborated,
  // neutral lexicon. Renders in the Rates section + Market Updates digest.
  "rates_news": "...",

  "commodities": [
    {"ticker": "WTI", "last": "72.45", "chg": "+0.5%", "catalyst": ""}
  ],
  "eia_opec_today": "OPEC+ JMMC tomorrow; EIA Wednesday 10:30 ET",
  // Optional. Sourced commodities news (OPEC+/EIA, supply disruptions, metals/ags).
  // Same NEWS_QUALITY.md gate. Renders in the Commodities section + digest.
  "commodities_news": "...",

  "fx": {
    "dxy": "...", "dxy_chg": "...",
    "eurusd": "...", "usdjpy": "...",
    "btc": "...", "btc_chg": "...", "eth": "...", "eth_chg": "...",
    "so_what": "..."
  },

  "sector_etfs": [{"ticker": "XLF", "chg": "+0.2%", "note": ""}],
  "rotation_read": "...",

  "premarket_movers": [
    {"ticker": "NVDA", "change": "+1.8%", "catalyst": "..."}
  ],

  "earnings_today": {
    "megacaps": [
      {"ticker": "NVDA", "timing": "BMO|AMC",
       "eps_est": "0.65", "rev_est": "32.5B", "implied_move": "8.5"}
    ],
    "my_positions": [
      {"ticker": "NVDA", "timing": "AMC",
       "eps_est": "0.65", "rev_est": "32.5B", "implied_move": "8.5",
       "position_summary": "...", "delta": "+0.42 net",
       "hedge_recommendation": "..."}
    ]
  },

  "my_positions": {
    "pnl_rows": [
      {"ticker": "NVDA", "qty": "...", "value": "$11,250", "pnl_overnight": "+$185"}
    ],
    // The next 3 lists are produced by check_alerts.py
    "stop_alerts": [...],
    "short_leg_alerts": [...],
    "upcoming_earnings": [...],
    // Free-form, assembled by orchestrator from news-sentiment + whale-hunting
    "holding_events": [
      {"ticker": "AAPL", "event_type": "news|unusual_flow|insider", "summary": "..."}
    ]
  },

  "opportunities": {
    "scanner_bullish": [{"ticker": "AVGO", "rationale": "..."}],
    "scanner_pmcc": [{"ticker": "XOM", "rationale": "..."}],
    "insider_buys": [
      {"ticker": "TSM", "insider_name": "...", "title": "...",
       "value": "2400000", "date": "2026-05-19"}
    ]
  },

  // Optional. WebSearch-synthesized geopolitical/headline wrap. Tier-1 sources
  // only (Reuters/AP/Bloomberg/FT/WSJ + primary), require >=2-source
  // corroboration, facts not punditry. Renders as a "Geopolitical" section in
  // the markdown and feeds the Market Updates digest. Omit if no IB/no search.
  "geopolitical_summary": "...",

  "noise_log_path": "briefings/noise_log.md"
}
```

### Calendar routing (morning)

`compose_brief.py build_calendar_events()` routes sections to calendars by the
keys present in `config.yaml calendars:`. Each is optional — a missing key
skips that calendar:

| Calendar key | Receives |
|---|---|
| `macro_events` | one timed event per `econ_releases` + `fed_speakers` |
| `earnings` | one timed event per `earnings_today` entry (deduped, my_positions wins) |
| `my_positions` | all-day summary event carrying the full rendered brief |
| `market_updates` | all-day **digest** event: snapshot + must-reads + overnight + energy catalysts + pre-market movers + `rates_news` + `commodities_news` + `geopolitical_summary` |

## Afternoon shape

```jsonc
{
  "mode": "afternoon",
  "date": "YYYY-MM-DD",
  "generated_at_et": "YYYY-MM-DD HH:MM ET",

  "snapshot": {
    "spy_close": "...", "spy_chg": "+0.13%",
    "dxy_close": "...", "us10y_close": "...", "vix_close": "..."
  },

  "market_moves": [
    {"topic": "CPI cooled", "summary": "..."}
  ],

  "pnl_recap": {
    "rows": [{"ticker": "NVDA", "day_pnl": "+$420", "day_pct": "+3.7%"}],
    "day_pnl": "+$680", "week_pnl": "+$1,240", "ytd_pnl": "+$18,420"
  },

  "my_top_movers": [
    {"ticker": "NVDA", "change": "+3.7%", "driver": "..."}
  ],

  "minutes_to_close": 30,
  "closing_bell_actions": "1. ...\n2. ...",

  "asia_releases": [
    {"time_et": "21:30", "name": "...", "consensus": "...", "impact": "..."}
  ],

  "amc_earnings": [
    {"ticker": "NVDA", "eps_est": "...", "implied_move": "...",
     "position_summary": "..."}
  ],

  "geopolitical_summary": "...",

  "tomorrow_econ": [
    {"time_et": "08:30", "name": "...", "consensus": "...", "prior": "..."}
  ],
  "tomorrow_fed_speakers": [
    {"time_et": "13:00", "name": "Waller", "voter_status": "voter"}
  ],
  "tomorrow_earnings": [
    {"ticker": "TGT", "timing": "BMO", "eps_est": "1.62", "implied_move": "6.2"}
  ],

  "key_levels": {
    "spy_support": "...", "spy_resistance": "...",
    "custom": "10Y: 4.25 support / 4.35 resistance..."
  }
}
```

## Position schema (input to check_alerts.py)

```jsonc
[
  // Stock position
  {"ticker": "TLT", "asset_type": "stock", "qty": 200,
   "last_price": 89.00, "stop_price": 87.50},

  // Long option (typically not flagged)
  {"ticker": "NVDA Jan26 110C", "asset_type": "option_long",
   "underlying": "NVDA",   // optional override; else first token of ticker
   "qty": 1, "delta": 0.78, "dte": 240},

  // Short option (flagged by delta breach or DTE threshold)
  {"ticker": "NVDA Jun20 145C", "asset_type": "option_short",
   "qty": -1, "delta": 0.42, "dte": 30,
   "roll_candidates": ["Jul18 150C @ $4.20", "..."]},

  // Synonyms accepted for short options: "short_call", "short_put"
]
```

## Earnings calendar entry (input to check_alerts.py --earnings)

```jsonc
[
  {"ticker": "NVDA", "date": "2026-05-21", "timing": "AMC",
   "eps_est": "0.65", "implied_move": "8.5"}
]
```
