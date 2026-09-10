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
