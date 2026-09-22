# Scratch

Low-friction inbox: half-formed ideas, reminders, one-line tasks, session notes.
No format police — write the fragment, move on.

**Not** the queue. [`TODO.md`](TODO.md) is the tracked queue (contract:
[`docs/methodology/todo-system.md`](docs/methodology/todo-system.md)); `docs/*.md`
carry `todo:` blocks that `scripts/todo_sweep.py` sweeps into it. This file is
swept by nobody — promote by hand when an item earns it.

Promotion path: scratch line → expand (intent / gaps / done-when) → either a
`todo:` block on the relevant doc, or a `TODO.md` item under its section.
Delete from here once promoted.

-

---

## Projects

*One bucket per project — jot under the one it belongs to. The blurb is
orientation and goes stale; the tracked queue is [`TODO.md`](TODO.md).*

### System maker

*`cfb_system_maker/` — CLI + Flask backtester. Open: delete saved systems from the web UI (`#system-maker-delete-saved-systems`).*

- add the general betting stats and figures page
-

### Warehouse

*`cfb_system_maker/`, `scripts/` — DuckDB from CFBD REST+GraphQL, Action Network, odds, PFF. Rationalization step 1 gated on a CFBD re-scrape (`coach_season`, `team_talent`).*

-

### PFF ingest

*`scripts/pull_pff_*.py`, `docs/pff-*.md` — schedule + bet splits public; Greenline needs a web session (Clerk JWT, 60s). Forward-only, 2025 absent upstream.*

-

### Totals model

*`models/totals/` — opening-total edge model. Cite `ou_open`, 2022-25 prior-season folds; never the leaked-era 57% / +8.82%.*

-

### Greenline reverse-engineering

*`research/totals/` — pricing layer solved (`greenline_pricing.py`); the underlying projection model is still unknown.*

-

### Over-zero

*`models/over_zero/` — Arscott / saturation / first-half floor-bias + weekly slate and monitor. No pytest suite; verify end-to-end.*

-

### Over-zero site

*`models/over_zero/site/` — nested repo, deploys via `git push sites` (user's auth, so Claude commits and they push).*

-

### Spread research

*`research/spread/` — closing-spread prediction off the Prediction Tracker panel. ~15% of open→close anticipated at the opener. Prereg order binding.*

-

### Ops / scheduling

*`scripts/schedule_cfb_tasks.ps1`, `scripts/task_ledger.cmd` — S4U conversion + run ledger. Written, not applied (needs task-modify permission).*

-

---

## Ideas

- data website
- stat manipulations
  - adj for opponent pff stats
  - above or below average pff grade (by conference, P4?)
  - add in time left or time in game to epa/ppa
  - measuring luck
  - 

## Reminders

- Refresh warehouse via `scripts/refresh_cfbd.py`, never `build_duckdb` directly
  (direct call skips the AN tick flatten, leaves the CSV stale).
- Run from the **main checkout** `.venv` python with `CFBD_API_KEY` exported —
  system python has the wrong pydantic.
- Held run: `gamePlayerStat` GraphQL pull — see [`docs/reminders.md`](docs/reminders.md).

## Tasks (quick, un-triaged)

- ship system builder
- start on spread and totals orginal model
- finish warehouse
- coach report
  - if they drift from year to year
- calculate pro fair line
- historical betting lines
- middle calc and bot

## Notes / open questions

- test cfb depth's model?

---

## Session log

*Newest first. One line per session: what changed, what's left dangling.*

### 2026-09-10

- Created this file.

---

## Quick reference

| Thing | Command / value |
| --- | --- |
| Tests | `python -m pytest` (slow excluded via `pytest.ini`) |
| Data root | `CFB_DATA_ROOT` → `C:\Users\mckel\dev\cfb\data`, resolved by `cfb_paths.py` |
| Source of truth | local `data/cfb.duckdb`; `md:cfb` is a manual mirror |
| Warehouse refresh | `python scripts/refresh_cfbd.py` |
| TODO index | `python scripts/todo_sweep.py refs` |
| TODO lint | `python scripts/todo_sweep.py check` |
| Doc → queue | `python scripts/todo_sweep.py sweep --apply` |

**Units:** `cfb_system_maker/` (app, scrapers, warehouse) · `models/totals/` ·
`models/over_zero/` · `research/spread/` — each has its own `CLAUDE.md`.

**Standing rules worth not re-learning:** no lookahead in pre-game features
(`result_lookahead` tag + UI quarantine); data never committed; don't touch
vendored `cfbd-python/`; anything reproducible gets a script, not a one-off.
