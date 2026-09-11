# Daily refresh break, 2026-09-11 — `_merge_game_lines` hard-depends on an optional column

**Status: proximate cause identified and reproduced. Upstream cause still open.**

The `cfbd_daily` scheduled task failed at 05:00 (`task_runs.csv`, exit 1), leaving
the warehouse with **6 of ~20 `core` tables** and no `stg.an_scoreboard` family.
`tests/test_catalog_resolution.py::test_every_schema_table_literal_resolves` fails
with 14 unresolved references, and 26 tests that need those tables now skip.

## What actually happened

```
_duckdb.BinderException: Binder Error: Table "l" does not have a column named "period"
  cfb_system_maker/duckdb_core.py:562   WHERE l.period = 'game'
```

The chain, confirmed at each step:

1. `stg.an_scoreboard` was not produced by the rebuild's explode. `raw.an_scoreboard`
   loaded fine (175 payload rows, `meta.load_report` 2026-09-11T09:08:54Z), and
   `stg.an_history` built normally from the same pass — only the scoreboard family
   (`an_scoreboard`, `an_market`, `an_team`, `an_linescore`) is absent.
2. `backfill_gamelines_from_actionnetwork` (`duckdb_load.py:643`) guards on
   `"an_market" in stg_tables` and **returns `None`** when it is missing. No error, no
   report row, no log line. `stg.game_lines` keeps its base CFBD shape.
3. That base shape has 9 columns and carries **neither `period` nor `line_source`** —
   both are added by the backfill.
4. `_merge_game_lines` (`duckdb_core.py:520`) guards on *table* existence only:

   ```python
   if not (_has(con, "stg", "game_lines") and _has(con, "stg", "lines_provider")):
       return False
   ```

   then its SQL reads `l.period` and `l.line_source` unconditionally. Binder error,
   uncaught, `build_core` aborts at step 7 of ~14.

**The guard checks the wrong thing.** It asks whether the table exists; the query needs
a column the table only has when an optional upstream step ran. The merge landed
2026-09-10 in `a9d2cb9`, written and measured against an already-backfilled
`game_lines` (its docstring quotes `line_source` counts), so it has never before met
the un-backfilled shape.

## What is not the cause

Ruled out by direct test, not by reading:

- **The AN explode code.** Copying `raw.an_scoreboard` (+ `raw.an_history`) into a fresh
  database and running the full `explode_payloads` path builds
  `stg.an_scoreboard` 10,868 / `an_market` 88,426 / `an_team` 21,736 /
  `an_linescore` 39,802, no errors, and they survive `explode_stg_lists`,
  `promote_timestamp_columns` and `drop_dead_columns`. The code works.
- **A truncated explode loop.** 179 `stg` tables exist, including ones alphabetically
  after `an_scoreboard`, so the loop ran past it rather than dying at it.
- **Missing source data.** `data/raw/actionnetwork/scoreboard_*.json` are present and
  `raw.an_scoreboard` loaded from them today.
- **`meta.load_report`.** It structurally cannot hold the answer: `_write_meta` runs
  *before* the explode (`duckdb_load.py:476-478`), so no explode result reaches it.

## What is still open

**Why `_explode_an_scoreboard` failed inside the full 115-source run when it succeeds in
isolation.** It returns `TableLoad(error=...)` rather than raising, so the loop continued
and the reason was discarded.

`d03fb4c` already added the diagnostic for exactly this — `refresh_cfbd.py:283-287`
prints `LOAD ERROR <schema>.<name>` for every failed report — but it landed *after* the
05:00 run, whose traceback line numbers (`refresh_cfbd.py:189`, `:226`) match the older,
shorter file. **The next rebuild is the one that will print the reason.** Nothing else
surfaces it.

## Fix shape

Two defects, independent, both worth closing:

1. **`_merge_game_lines` should degrade, not die.** Extend the guard from table
   existence to column existence — if `stg.game_lines` has no `period`, the AN backfill
   did not run, there is nothing to union, and the honest behaviour is `return False`
   like every other missing-input path in `build_core`. A warning belongs with it: a
   silent skip here is how the gap stayed invisible in the first place.
2. **`backfill_gamelines_from_actionnetwork` should not skip silently.** Returning
   `None` when `an_market` is absent produces no report row at all, so even the new
   `LOAD ERROR` printing cannot see it. A `TableLoad(..., error="an_market absent")`
   would surface it through the path that now exists.

Neither addresses why the explode failed — that needs the rebuild's output.

## Also noticed

`C:` is at **98% (27 GB free)** with two stale 5 GB warehouse copies next to the live
one — `cfb.duckdb.bak-2026-09-01` and `cfb.duckdb.premigrate` (2026-09-02). A rebuild
writes a ~5 GB `.building` file before the atomic replace, so headroom matters here.
Not implicated in this failure; flagged because it is close to being implicated in one.

---
Investigated 2026-09-11. Evidence: `data/logs/cfbd_refresh.log` (05:00 block),
`data/logs/task_runs.csv`, `meta.load_report`, live `cfb.duckdb` catalog, and an
isolated explode reproduction under the session scratchpad.
