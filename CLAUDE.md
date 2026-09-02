# Shared repository instructions

This file owns rules shared by every unit. Closer nested `CLAUDE.md` files add
unit-specific commands and conventions. `AGENTS.md` points here; `.claude/CLAUDE.md`
owns only GSD workflow; `CONTEXT.md` owns current terminology; `PRODUCT.md` owns
human-facing product intent. None should duplicate another file's rules.

## Standing Rules

- After finishing tasks/findings tracked in a doc (review docs, plans, TODO lists), update that doc marking each  item done + the completion date — don't leave it stale once the work lands.

- Any modelling, backtesting, or analysis that might be reproduced gets a reusable script, not a one-off. Write the script as part of the task.

## Units

| Unit | Home | Instructions |
| --- | --- | --- |
| System maker, Flask app, scrapers, warehouse | `cfb_system_maker/` | `cfb_system_maker/CLAUDE.md` |
| Totals model | `models/totals/` | `models/totals/CLAUDE.md` |
| Over-zero models and floor-bias research | `models/over_zero/` | `models/over_zero/CLAUDE.md` |
| Spread forecast research | `research/spread/` | `research/spread/CLAUDE.md` |

## Shared rules

- `CFB_DATA_ROOT` is required and resolves through root `cfb_paths.py`. Working data is
  `C:\Users\mckel\dev\cfb\data`; local `cfb.duckdb` is source of truth. MotherDuck
  `md:cfb` is a manual mirror.
- Data is never committed. It lives in `data/`, which `.gitignore` excludes. Keep only
  explicit fixtures, examples, research records, and documentation artifacts in git.
- Do not edit `cfbd-python/`; it is vendored upstream.
- No lookahead: pre-game features use only information available before kickoff. Any
  result-informed feature must be tagged `result_lookahead` and quarantined in UI.
- Run commands from repository root unless a nested instruction says otherwise.
- Default verification: `python -m pytest`. `pytest.ini` excludes slow tests by default.
- Preserve unrelated dirty work. Keep moves and content edits in separate commits when
  practical.

## Archive rule

`archive/` contains documents superseded by later answers. Retain them for audit history,
but never cite them as current. Historical `.planning/` records remain in place and may
contain old paths; do not rewrite them merely to modernize history.
