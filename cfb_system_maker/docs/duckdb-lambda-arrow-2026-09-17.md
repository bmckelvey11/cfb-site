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

## Numbers

Full suite, worktree at `2f19602`:

| | before | after |
| --- | --- | --- |
| `python -m pytest` (duckdb 2.0.0.dev) | 2 failed, 1005 passed, 1 skipped, 6 deselected | 1 failed, 1006 passed |
| `tests/test_duckdb_load.py` alone, duckdb 2.0.0.dev | 1 failed, 40 passed | 41 passed |
| `tests/test_duckdb_load.py` alone, duckdb 1.5.5 | 41 passed | 42 passed (new guard) |

## What this does *not* support

- It does not show the test suite is isolation-clean. It shows this *particular* failure
  was not an isolation problem. No bisect was run, so nothing was proven either way about
  cross-file state elsewhere in the suite.
- It does not make the codebase duckdb-2.0-ready. Only the lambda arrow was audited. Other
  2.0 removals may still be latent — `tests/test_sql_course.py` is the obvious next place
  to look, and the remaining full-suite failure below is unrelated to it.
- It says nothing about which interpreter the project *should* run on. `.venv` (duckdb
  1.5.5) remains the project environment; `C:\Python314` happening to be first on `PATH`
  with a 2.0 nightly is the reason the two runs disagreed, and that skew is still there.

## Loose ends, not addressed here

None of these were touched; all are independent of this finding, and all were confirmed
present before the change (the files involved are unmodified).

1. **`test_sql_course.py::test_every_solution_runs[B5]`** fails in a worktree only.
   `learning/sql_course/solutions/B5.sql` does `COPY ... TO 'data/games_2024.parquet'`, a
   *relative* path, and a worktree has no `data/` directory. `mkdir data` and it passes.
   Not a bug, a worktree artifact.
2. **`test_sql_course.py::test_every_solution_runs[C2]`** fails under duckdb **1.5.5**
   with `Parser Error: syntax error at or near "WHERE"` on `C2-3`, and passes under 2.0.
3. **`test_warehouse_catalog.py`**, two tests, fail under duckdb **1.5.5** with
   `Parser Error: unterminated quoted string`, and pass under 2.0.
   `scripts/build_warehouse_catalog.py:552` builds a grain key by joining columns with
   literal `0x01` and `0x00` control characters embedded directly in the SQL string;
   1.5.5 treats the NUL as terminating the literal.

(2) and (3) are the *same class of problem as this one* pointing the other way: SQL that
one duckdb version accepts and the other does not, with the disagreement showing up as an
apparently random test failure. Worth a pass of its own.

## Reproduce

```
python -m pytest tests/test_duckdb_load.py -q                       # duckdb 2.0.0.dev
.venv/Scripts/python.exe -m pytest tests/test_duckdb_load.py -q     # duckdb 1.5.5
```

Both must pass. The regression guard runs as part of either.
