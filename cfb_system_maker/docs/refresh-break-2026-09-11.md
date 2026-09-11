# Daily refresh break, 2026-09-11 — `_merge_game_lines` hard-depends on an optional column

**Status: closed. Proximate cause fixed (`193939f`, `2acb598`, verified in production
2026-09-11 06:23). Upstream cause identified as an OOM; its fix and the warehouse repair
are tracked separately as `#rebuild-dropped-an-tables`.**

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

## The upstream cause: an out-of-memory allocation failure

Answered by the supervised 06:05 run, the first rebuild after `d03fb4c` and so the first
one able to print what the explode had been swallowing:

```
LOAD ERROR stg.an_scoreboard: OutOfMemoryException: Out of Memory Error: Allocation failure
LOAD ERROR stg.game_lines: stg.an_market absent: ActionNetwork lines not merged into
                           stg.game_lines, which leaves it without period/line_source
6 table(s) failed to load; core may be incomplete
```

Not a logic bug. `stg.an_scoreboard` dies on allocation; `an_market`, `an_team` and
`an_linescore` are its children and so are never built; the backfill then correctly
reports the absent tape; `game_lines` stays nine columns; the merge skips. **One
allocation failure produces the entire cascade.**

Measured at the time of the run: **15.4 GB physical, 2.9 GB free.** DuckDB defaults
`memory_limit` to ~80% of physical (≈12.3 GB) and `duckdb_load.py` sets it nowhere — only
`SET threads = 1`, in four places. So the loader plans against 12.3 GB while the OS has
2.9 GB to give.

**This is why the isolated reproductions below passed.** Both of us tested a two-table
database on an idle machine; neither went near the memory ceiling. "Specific to the full
115-source run" was the right read, but the mechanism is memory pressure, not source
count — the full run is simply the one that allocates enough to hit the wall.

Fixing the OOM (an explicit `memory_limit` and a `temp_directory` so the loader spills
instead of dying) and repairing the warehouse are tracked as `#rebuild-dropped-an-tables`
and are not this document's scope.

`_explode_an_scoreboard` returns `TableLoad(error=...)` rather than raising, so the loop
continued and the reason was discarded. `d03fb4c` added the diagnostic —
`refresh_cfbd.py:283-287` prints `LOAD ERROR <schema>.<name>` for every failed report —
but it landed *after* the 05:00 run, whose traceback line numbers (`refresh_cfbd.py:189`,
`:226`) match the older, shorter file. Nothing else surfaces it.

Two theories were raised along the way and both are dead. A fixed `.building` temp path
colliding with a concurrent rebuild does not explain it — the 05:00 run was alone, and
there was no 04:00 scheduled run for it to race. `5897917` closed that hazard on its own
merits (`build_duckdb` now takes an exclusive lock and raises `RebuildInProgress`), not as
this diagnosis.

## Fixes — both landed and verified in production 2026-09-11

Two defects, independent, both closed. Neither addresses the OOM; they make its blast
radius a degraded table instead of a dead build.

1. **`_merge_game_lines` degrades instead of dying** — `193939f`, done 2026-09-11.
   New `_has_columns` helper; the guard now checks `period` and `line_source`, not merely
   that the table exists. Skips with a `RuntimeWarning` naming the missing tape and
   returns `False`, like every other missing-input path in `build_core`. Warned rather
   than skipped quietly: a silent skip here is how the gap stayed invisible.
   `tests/test_core_guards.py` is fixture-built — the point is a state the live warehouse
   is never in — and one of its four cases pins that the merge *still runs* when
   `game_lines` is widened, so the guard cannot regress into never firing.
2. **`backfill_gamelines_from_actionnetwork` reports its skip** — `2acb598`, done
   2026-09-11. The guard is split: no `stg.games`/`game_lines` is an AN-free build and
   stays a silent `None`; the CFBD side present without the AN side is the anomaly and
   returns `TableLoad(..., error=...)`, which reaches the `LOAD ERROR` line. This is the
   specific hole that made 2026-09-11 silent — the skip was invisible even to the
   diagnostic built for it.

**Both worked on their first production run**, the supervised 06:05 rebuild:

```
duckdb_core.py:58: RuntimeWarning: stg.game_lines has no period/line_source column:
the ActionNetwork backfill did not run, so core.fact_game_line stays REST-only
```

and item 2's error string is `LOAD ERROR` line 2 verbatim. `build_core` finished with
**17 core tables and exit 0**, against 6 tables and exit 1 at 05:00 — same underlying OOM,
same missing tape, a degraded warehouse instead of a dead one.

That run also settles what these fixes are worth. The OOM was not transient: it recurred
on the very next rebuild. So item 1 is not a belt-and-braces addition — it is the only
thing standing between a recurring upstream gap and a warehouse that loses 14 `core`
tables until a human notices.

## The failure would have stood for 23 hours

`CFB-CFBD-Daily` is a **daily** trigger, not hourly — `MSFT_TaskDailyTrigger
@2026-08-31T05:00:00`, `rep:(none)`, next run 2026-09-12T05:00. So nothing scheduled was
going to rebuild the warehouse before the following morning, and nothing scheduled was
going to produce the `LOAD ERROR` line either: the 05:00 run predates `d03fb4c`, and the
next one is a day away. A supervised `refresh_cfbd.py` at ~06:05 is what actually
produced the first post-`d03fb4c` run.

Worth stating because of what that exposure would have cost. The OOM turned out to recur
on the next rebuild rather than being a one-off, so without the supervised run the
warehouse would have sat 14 `core` tables short until 2026-09-12T05:00 — and that run
would have failed the same way.

## Also noticed

`C:` was at **98% (27 GB free)**, with two stale 5 GB warehouse copies beside the live
one — `cfb.duckdb.bak-2026-09-01` and `cfb.duckdb.premigrate` (2026-09-02). A rebuild
writes a ~5 GB `.building` file before the atomic replace, so the headroom mattered.
Never implicated in this failure; flagged because it was close to being implicated in
one. **Resolved the same morning** — the user authorized deleting both, leaving
`data/cfb.duckdb` as the only copy and 37 GB free.

That headroom stopped being incidental once the cause turned out to be memory: the
standard fix for a DuckDB OOM is a `temp_directory` to spill into, and spilling needs
free disk. The 10 GB reclaimed here is what that fix will spend.

---
Investigated 2026-09-11, closed the same day. Evidence: `data/logs/cfbd_refresh.log`
(the 05:00 failure and the supervised 06:05 run that named the OOM),
`data/logs/task_runs.csv`, `meta.load_report`, the live `cfb.duckdb` catalog, and an
isolated explode reproduction under the session scratchpad. The OOM fix and the warehouse
repair are `#rebuild-dropped-an-tables`, owned separately.
