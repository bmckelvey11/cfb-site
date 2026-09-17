# `test_backfill_gamelines_fills_nulls_and_inserts_period_rows` is not a test-isolation bug

2026-09-17. Repo state: worktree at clean `master` = `2f19602`.

## The question

`tests/test_duckdb_load.py::test_backfill_gamelines_fills_nulls_and_inserts_period_rows`
was reported as failing only in the full suite (`python -m pytest`) and passing both alone
and as a whole file (`.venv/Scripts/python.exe -m pytest tests/test_duckdb_load.py`). That
shape — passes isolated, fails in the suite — reads as cross-file state leakage: a module
global, an un-undone monkeypatch, a stray `CFB_DATA_ROOT`, a cached connection. The task
was to bisect the preceding test files and fix the leak at its source.

## Method

1. Checked for an ordering source. There is no `conftest.py` anywhere in the project and
   `pytest-randomly` is not installed, so collection order is plain alphabetical and
   deterministic. Only the 18 files sorting before `test_duckdb_load.py` could pollute it.
2. Audited the plausible leak vectors before bisecting: `_AN_BOOK_PROVIDER` /
   `_AN_SCHOOL_ALIAS` / `_AN_ID_OFFSET` are never mutated anywhere; the only
   `importlib.reload(duckdb_load)` is in `tests/test_rebuild_lock.py`, which sorts *after*
   the target and so cannot be upstream of it; the only `monkeypatch.setattr` on
   `duckdb_load` is `_STRUCTURE_SAMPLE_ROWS` in `tests/test_structure_inference.py`, also
   downstream and undone by `monkeypatch` regardless.
3. Ran the full suite under `.venv` in the main checkout. **The target test passed** in
   full-suite order.
4. Ran the target test *alone* under the interpreter the failure was reported on. **It
   failed.**

That last step ends the isolation hypothesis: the two runs that passed were not
apples-to-apples with the run that failed.

## What is actually happening

The failing and passing runs used different interpreters, carrying different DuckDB wheels:

| invocation | python | pytest | duckdb |
| --- | --- | --- | --- |
| `python -m pytest` (failed) | `C:\Python314\python.exe` 3.14.6 | 9.1.1 | **2.0.0.dev2609121639** |
| `.venv/Scripts/python.exe -m pytest` (passed) | `.venv` 3.14.6 | 8.4.2 | **1.5.5** |

DuckDB 2.0 removed the deprecated lambda arrow. Any `list_transform(xs, x -> ...)` now
raises at bind time:

```
Binder Error: Deprecated lambda arrow (->) detected. Please transition to the new lambda
syntax, i.e.., lambda x, i: x + i, before DuckDB's next release.
```

`_backfill_gamelines` built its team-location lookup with that arrow, so under duckdb 2.0
`backfill_gamelines_from_actionnetwork` caught the `BinderException` in its own
`except Exception` handler and returned a `TableLoad` with `error` set instead of raising.
The test asserts `report.error is None`, so the only thing that surfaced was one assertion
failure with no traceback pointing at SQL — which is why it read as flakiness.

Three occurrences, all in `cfb_system_maker/duckdb_load.py`:

- `_backfill_gamelines`, the `home_loc` / `away_loc` lookup (two arrows, one string)
- `_path_populated_predicate`, the `[*]` wildcard branch (one arrow)

Nothing else in the repo uses a lambda arrow in SQL; every other `->` in the tree is a
Python type annotation or prose.

## The fix

Rewrote all three as `lambda x: ...`. That syntax is accepted by **both** duckdb 1.5.5 and
2.0.0.dev — verified directly against both wheels, including the exact nested
`list_first(list_transform(list_filter(...)))` expression — so this is a straight forward
port with no version gate.

`tests/test_duckdb_load.py::test_no_sql_here_uses_the_deprecated_lambda_arrow` reads the
module source and fails if an arrow comes back, in the same style as the existing
`test_the_backfill_never_emits_a_bare_actionnetwork_book_id` guard. The SQL here is built
by f-string across several helpers, so a source assertion is the cheap check.

It walks the AST and inspects **string literals**, skipping docstrings and `#` comments,
rather than grepping lines. A line-oriented grep does not work here: both offending arrows
sat on *continuation* lines of a triple-quoted block whose `list_filter(` opener is two
lines earlier, so anything anchored to the call site skips them. Several comments and
docstrings in the module legitimately write `a -> b` as prose, which is why the
literal/docstring split is needed rather than a bare substring test.

The guard was verified in both directions: run against `2f19602`'s `duckdb_load.py` it
fails with `[(773, 't ->'), (1500, 'x ->')]`; against the fixed file it passes.

## Numbers

Full suite, worktree at `2f19602`:

| run | before | after |
| --- | --- | --- |
| full suite, duckdb 2.0.0.dev, bare worktree | 2 failed, 1005 passed, 1 skipped, 6 deselected | 1 failed, 1007 passed, 1 skipped, 6 deselected |
| full suite, duckdb 2.0.0.dev, after `mkdir data` | — | **1008 passed, 1 skipped, 6 deselected** |
| `tests/test_duckdb_load.py`, duckdb 2.0.0.dev | 1 failed, 39 passed | 41 passed |
| `tests/test_duckdb_load.py`, duckdb 1.5.5 | 40 passed | 41 passed (incl. new guard) |

The bare-worktree row's one remaining failure is `test_sql_course.py::...[B5]`, the `data/`
artifact in loose end (1) below. Create that directory and the suite is green under duckdb
2.0.0.dev end to end.

Under duckdb **1.5.5** the full suite was `3 failed, 1005 passed, 2 skipped, 5 deselected`
at that point -- loose ends (2) and (3) below, in files the lambda-arrow change does not
touch. Both were fixed the same day (see below); the suite is now **1008 passed** on
duckdb 1.5.5 and on 2.0.0.dev alike.

## What this does *not* support

- It does not show the test suite is isolation-clean. It shows this *particular* failure
  was not an isolation problem. No bisect was run, so nothing was proven either way about
  cross-file state elsewhere in the suite.
- It does not make the codebase duckdb-2.0-ready, nor 1.5.5-safe. Three version-sensitive
  SQL sites were found and fixed (the lambda arrow, plus loose ends (2) and (3) below);
  nobody audited the rest of the SQL in the tree for either direction. What is established
  is only that the suite passes end to end on both wheels today.
- It says nothing about which interpreter the project *should* run on. `.venv` (duckdb
  1.5.5) remains the project environment; `C:\Python314` happening to be first on `PATH`
  with a 2.0 nightly is the reason the two runs disagreed, and that skew is still there.

## Loose ends

Three were found while diagnosing the above, all in files the lambda-arrow fix does not
touch. Two are now fixed; one is not a bug.

1. **`test_sql_course.py::test_every_solution_runs[B5]`** fails in a worktree only.
   `learning/sql_course/solutions/B5.sql` does `COPY ... TO 'data/games_2024.parquet'`, a
   *relative* path, and a worktree has no `data/` directory. `mkdir data` and it passes.
   Not a bug, a worktree artifact -- **no change made**.

2. **`test_sql_course.py::test_every_solution_runs[C2]`** -- `C2-3` wrote
   `FROM core.fact_game USING SAMPLE 10% WHERE season = 2024 ...`. duckdb 1.5.5 rejects a
   `WHERE` after `USING SAMPLE` (`Parser Error: syntax error at or near "WHERE"`); 2.0's
   parser accepts it. Moving `USING SAMPLE 10%` to the end of the statement parses on both
   **and** matches the exercise as written -- "draw a 10% sample of 2024 games" means
   sample the filtered rows, whereas the sample clause attached to the `FROM` applies
   before the filter. **Fixed 2026-09-17.**

3. **`test_warehouse_catalog.py`**, two tests -- `compute_grain` in
   `scripts/build_warehouse_catalog.py` built a uniqueness probe by joining the key columns
   with a literal `0x01` and mapping NULL to a literal `0x00`, both embedded raw in the SQL
   text. duckdb 1.5.5 reads the NUL as ending the string literal
   (`Parser Error: unterminated quoted string`); 2.0 tolerates it. Replaced with
   `select count(*) from (select distinct <keys> from ...)`, which needs no sentinel and no
   separator. **Fixed 2026-09-17.**

   `SELECT DISTINCT` was chosen over `count(DISTINCT (a, b))` deliberately: the struct form
   collapses to plain `count(DISTINCT a)` when there is a single key column, which *drops*
   NULLs and would have silently changed the grain verdict for single-key tables like
   `core.dim_team`. Measured on both wheels against `(1), (2), (NULL)`: sentinel 3,
   `SELECT DISTINCT` 3, struct 2.

(2) and (3) were the *same class of problem as the lambda arrow*: SQL that one duckdb
version accepts and the other rejects, surfacing as an apparently random test failure. All
three sites are now version-neutral.

## Reproduce

Run the whole suite under both wheels -- that is the check that matters here, since every
failure in this write-up was a disagreement between them:

```
python -m pytest -q                       # duckdb 2.0.0.dev  (C:\Python314 on PATH)
.venv/Scripts/python.exe -m pytest -q     # duckdb 1.5.5      (project environment)
```

Both are `1008 passed` as of 2026-09-17 (a worktree needs `mkdir data` first, per loose
end (1)). The narrower checks for the lambda arrow alone:

```
python -m pytest tests/test_duckdb_load.py -q
.venv/Scripts/python.exe -m pytest tests/test_duckdb_load.py -q
```

The source guard runs as part of either.
