# DuckDB version floor for the loader

**Date:** 2026-09-16

## Question

`requirements.txt` pinned `duckdb>=1.1,<2` while the machine ran
`2.0.0.dev2609121639`. After the loader moved off the deprecated `->` lambda arrow
onto `lambda x:` syntax, what is the real minimum DuckDB the loader works on?

The first guess was 1.3 — the release that introduced `lambda x:`. That guess was
wrong, and the pin was briefly committed at `>=1.3,<3` before this check ran.

## Method

Throwaway venv, Python 3.13.14 (the machine's Python is 3.14.6, which has no
DuckDB wheels below 1.4; 3.13 has a `cp313` wheel for every version tested, so the
floor could be probed at all). Full `requirements.txt` installed, then DuckDB
swapped version by version.

Selection: the 20 test files matching `grep -ln duckdb tests/*.py`. A control run
on 1.5.5 — newest in the pin range — established that a failure is attributable to
the DuckDB version and not to running on 3.13 instead of 3.14.

Reproduce (Git Bash, from repository root; `V` is any scratch path):

```
V=/c/Users/mckel/AppData/Local/Temp/duckdb-floor-venv
py -3.13 -m venv "$V"
"$V/Scripts/python.exe" -m pip install -r requirements.txt
"$V/Scripts/python.exe" -m pip install "duckdb==1.4.5"   # or 1.3.0, 1.5.0, ...
CFB_DATA_ROOT=C:/Users/mckel/dev/cfb/data "$V/Scripts/python.exe"   -m pytest $(grep -ln duckdb tests/*.py) -q
```

## Result

| DuckDB | Self-contained loader tests (106) | Full selection (20 files) |
| --- | --- | --- |
| 1.3.0 | 15 failed, 91 passed | 19 failed, 190 passed, 26 errors |
| 1.4.0 | 15 failed, 91 passed | not run |
| 1.4.2 | 15 failed, 91 passed | not run |
| 1.4.5 | 15 failed, 91 passed | not run |
| 1.5.0 | 106 passed | 235 passed, 2 deselected |
| 1.5.5 (control) | not run | 235 passed, 2 deselected |

**Floor is 1.5.0.** Every 1.3.x and 1.4.x release tested fails the same 15 tests.
Pin corrected to `duckdb>=1.5,<3`.

Two distinct breakages below 1.5, neither of them the lambda syntax:

- `BinderException: UNNEST() only supports a single additional argument` on the
  REST flatten path.
- `explode_stg_lists` silently stops after the first nesting level: for a
  `teams -> cats` payload it creates `stg.stats__teams` and never
  `stg.stats__teams__teams_cats`. No error is raised — the table is simply absent.

The 26 errors at 1.3.0 in the full selection are a separate, environmental cause:
`InternalException: Failed to load metadata pointer`, i.e. 1.3.0 cannot open the
live `cfb.duckdb`, which 2.0.0.dev wrote. Those errors say nothing about the
loader code and would appear for any storage-version mismatch.

## What this does not support

- It does not establish an upper bound. `<3` is inherited convention, not a
  tested claim; the only 2.x actually exercised is `2.0.0.dev2609121639`, via the
  main 3.14 environment.
- It does not test 1.5.1–1.5.4, only 1.5.0 and 1.5.5. The floor is verified at
  1.5.0; the versions between are assumed good by interpolation.
- It says nothing about non-loader units. The selection is the 20 files that
  mention `duckdb`; `models/`, `research/`, and the Flask app were not run against
  the older versions.
- It was run on Python 3.13, not the 3.14 the repo actually uses. The control run
  makes the DuckDB attribution sound, but a 3.14-specific interaction with an
  older DuckDB would not have been visible.
