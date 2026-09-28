---
layout: default
title: "Morning Trading Briefing"
grand_parent: English
parent: Skill Guides
nav_order: 11
lang_peer: /ja/skills/morning-trading-briefing/
permalink: /en/skills/morning-trading-briefing/
generated: true
---

# Morning Trading Briefing
{: .no_toc }

Two-times-daily trading briefing (7am pre-open + 3:30pm afternoon). Personalized to IB portfolio + market-wide. Covers macro events with full "why it matters" context, earnings with implied moves, position action items, and fresh setups. Writes timed events to Google Calendar sub-calendars (Macro Events / Earnings / My Positions) and archives markdown to Google Drive. Invoked by /morning-brief or /afternoon-brief commands.
{: .fs-6 .fw-300 }

<span class="badge badge-free">No API</span>

[View Source on GitHub](https://github.com/tradermonty/claude-trading-skills/tree/main/skills/morning-trading-briefing){: .btn .fs-5 .mb-4 .mb-md-0 }

<details open markdown="block">
  <summary>Table of Contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## 1. Overview

The skill is hybrid with a strict boundary at `brief_data.json`: the LLM
handles synthesis (assembling sub-skill outputs into `brief_data.json`,
writing the "must-read top 3"); from there Python takes over for all
deterministic work — alert math, template rendering, event-JSON
generation, **and the Google Calendar + Drive writes** (`v2.0+`, via
`google_calendar_client.py` / `google_drive_client.py`). The LLM no
longer touches MCP for calendar/Drive — that path produced the
2026-05-27 dupe storm (see `state/HANDOFF.md`).

```
┌──────────────┐      ┌─────────────────┐      ┌───────────────┐
│  Sub-skills  │─────▶│  LLM assembles  │─────▶│ compose_brief │
│ (ib-*, econ- │      │ brief_data.json │      │ render +      │
│  calendar,   │      └────────┬────────┘      │ events.json   │
│  scanner, …) │               │               └───────┬───────┘
└──────────────┘               │                       │
                               ▼                       ▼
                        check_alerts.py        ┌───────────────┐
                        lookup_indicator.py    │write_brief_   │
                                               │ outputs.py    │
                                               │ → Calendar API│
                                               │ → Drive API   │
                                               └───────────────┘
```

---

## 2. Prerequisites

- **API Key:** None required
- **Python 3.9+** recommended

---

## 3. Quick Start

Invoke this skill by describing your analysis needs to Claude.

---

## 4. Workflow

See the skill's SKILL.md for the complete workflow.

---

## 5. Resources

**References:**

- `skills/morning-trading-briefing/references/BEST_PRACTICES.md`
- `skills/morning-trading-briefing/references/BRIEFING_TEMPLATE.md`
- `skills/morning-trading-briefing/references/BRIEF_DATA_SCHEMA.md`
- `skills/morning-trading-briefing/references/CALENDAR_SETUP.md`
- `skills/morning-trading-briefing/references/GOOGLE_API_SETUP.md`
- `skills/morning-trading-briefing/references/HOSTINGER_DEPLOY.md`
- `skills/morning-trading-briefing/references/NETWORK_ALLOWLIST.md`
- `skills/morning-trading-briefing/references/NEWS_QUALITY.md`
- `skills/morning-trading-briefing/references/ROADMAP.md`
- `skills/morning-trading-briefing/references/SKILLS_INVENTORY.md`

**Scripts:**

- `skills/morning-trading-briefing/scripts/check_alerts.py`
- `skills/morning-trading-briefing/scripts/check_news_quality.py`
- `skills/morning-trading-briefing/scripts/compose_brief.py`
- `skills/morning-trading-briefing/scripts/event_filters.py`
- `skills/morning-trading-briefing/scripts/generate_charts.py`
- `skills/morning-trading-briefing/scripts/google_calendar_client.py`
- `skills/morning-trading-briefing/scripts/google_drive_client.py`
- `skills/morning-trading-briefing/scripts/render_brief.py`
- `skills/morning-trading-briefing/scripts/signals.py`
- `skills/morning-trading-briefing/scripts/sparkline.py`
- `skills/morning-trading-briefing/scripts/technicals.py`
- `skills/morning-trading-briefing/scripts/write_brief_outputs.py`
