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

---

## Projects

*Orientation, not a queue — statuses go stale; the queue is [`TODO.md`](TODO.md).*

| Project | Home | What it is | Where it stands |
|---|---|---|---|
| System maker | `cfb_system_maker/` | Python CLI + Flask UI for backtesting filter-based betting systems over CFBD games/lines | Shipped, in use. Open: delete saved systems from the web UI (`#system-maker-delete-saved-systems`) |
| Warehouse | `cfb_system_maker/`, `scripts/` | DuckDB (`data/cfb.duckdb`) built from CFBD REST + GraphQL, Action Network, odds, PFF; `md:cfb` is a manual mirror | Live. Rationalization plan in flight — step 1 gated on a CFBD re-scrape (`coach_season`, `team_talent`) |
| PFF ingest | `scripts/pull_pff_*.py`, `docs/pff-*.md` | Scrapers for PFF schedule, bet splits, Greenline picks; 70-endpoint reference | Schedule + splits public and working. Greenline needs a web session (Clerk JWT, 60s) — no headless path. Forward-only, 2025 absent upstream |
| Totals model | `models/totals/` | Opening-total edge model + backtest harness | Clean-feature walk-forward graded; edge threshold frozen. Cite `ou_open`, 2022-25 prior-season folds — never the leaked-era 57% / +8.82% |
| Greenline reverse-engineering | `research/totals/` | Recovering PFF's totals model from captured picks | Pricing layer solved (`greenline_pricing.py`): value = prob − 110/210, prob = Φ((proj−line)/σ), σ ∝ line. Underlying projection model still unknown |
| Over-zero | `models/over_zero/` | Arscott / saturation / first-half floor-bias models + weekly slate and monitor | Running weekly. No pytest suite — verify scripts end-to-end against local data |
| Over-zero site | `models/over_zero/site/` | Public slate site (nested repo) | Deploys via `git push sites` — needs the user's auth, so Claude commits and they push |
| Spread research | `research/spread/` | Predicting where the closing spread goes from the Prediction Tracker panel; book fair + line shopping | Preregistered and decontaminated: the screened consensus anticipates ~15% of open→close at the opener. Prereg order is binding |
| Ops / scheduling | `scripts/schedule_cfb_tasks.ps1`, `scripts/task_ledger.cmd` | Windows scheduled tasks for the daily pulls; S4U conversion to stop console popups + a CSV run ledger | Scripts written, not applied — blocked on the user running them (needs task-modify permission) |

---

## Ideas

- 

## Reminders

- Refresh warehouse via `scripts/refresh_cfbd.py`, never `build_duckdb` directly
  (direct call skips the AN tick flatten, leaves the CSV stale).
- Run from the **main checkout** `.venv` python with `CFBD_API_KEY` exported —
  system python has the wrong pydantic.
- Held run: `gamePlayerStat` GraphQL pull — see [`docs/reminders.md`](docs/reminders.md).

## Tasks (quick, un-triaged)

- 

## Notes / open questions

- 

---

## Session log

*Newest first. One line per session: what changed, what's left dangling.*

### 2026-09-10
- Created this file.

---

## Quick reference

| Thing | Command / value |
|---|---|
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
