# Codex build handoff — warehouse naming rationalization

You are implementing a frozen, already-reviewed spec. You have write access to this repo.
You have no prior context on this work; everything you need is below or in the files it names.

---

## Why this change exists (read this before touching anything)

This repo's DuckDB warehouse has a `stg` schema fed by **two different sources**:

- The **CFBD REST API** — its endpoints land as snake_case, plural table names (`games`,
  `coaches`, `draft_picks`).
- The **CFBD GraphQL API** — its 34 root fields land under their **verbatim camelCase API field
  names** (`game`, `gameLines`, `adjustedPlayerMetrics`, `coachSeason`).

So `stg.game` and `stg.games` are not a typo and not duplicates. They are two different sources
of the same subject with different coverage.

**The defect:** when a GraphQL entity and a REST endpoint want the same destination name, the
helper `_stg_dest_name` (`cfb_system_maker/duckdb_load.py:1086`) resolves the clash by appending
`_gql` — but only if the name is already in a `taken` set that is **populated as loads proceed**.
Which source wins the unsuffixed name therefore depends on the order loads happen to run in.
`duckdb_load.py:494` already carries a comment acknowledging this and works around it by sorting
REST first. That is a workaround, not a fix. One clash has already fired in the live warehouse:
`stg.calendar` (258 rows) and `stg.calendar_gql` (424 rows), with nothing recording which is
which.

**The fix:** replace clash-detection with an explicit, total mapping. Every GraphQL entity gets a
destination name `gql_<snake_case>`, which is verified disjoint from all 173 existing `stg`
names, so a clash becomes impossible by construction rather than resolved after the fact.

---

## ⚠️ The one mistake that would ruin this change

**GraphQL field names are an upstream API contract. They MUST NOT be renamed.**

`GQL_DEFAULT_TABLES`, `GQL_RELATION_KEYS`, the GraphQL query text, and the
`data/graphql/*.json` filenames all use the API's camelCase names because that is what the API
answers to. Renaming them breaks every query.

Only the **`stg` destination table name** is ours to change. The entire design is a mapping layer
between the two:

```python
GQL_ENTITY_TO_STG = {"gameLines": "gql_game_lines", ...}
#                     ^ API contract  ^ ours
```

If you find yourself editing the string `"gameLines"` inside `GQL_DEFAULT_TABLES` or inside a
query, stop — that is the error this warning exists to prevent.

---

## Read these first

1. `docs/superpowers/plans/2026-08-31-warehouse-naming-rationalization.md` — **the spec.** It has
   per-task steps, the exact test code, and the exact implementation code. Follow it literally.
2. `docs/superpowers/specs/2026-08-31-warehouse-naming-rationalization.md` — the reasoning,
   evidence, and the verified rename map.
3. `CLAUDE.md` (repo root) — repository rules you must obey.

---

## Scope — implement ONLY these tasks from the spec

| Task | What | Files |
|---|---|---|
| 1 | `GQL_ENTITY_TO_STG` explicit mapping | `cfb_system_maker/graphql_client.py`, `tests/test_graphql.py` |
| 2 | Replace `_stg_dest_name` with pure `stg_dest_name`; update both call sites | `cfb_system_maker/duckdb_load.py`, `tests/test_duckdb_load.py` |
| 3 | Retarget the live `stg.gameLines` / `stg.linesProvider` references | `cfb_system_maker/duckdb_load.py`, `tests/test_duckdb_load.py` |
| 4 | Idempotent rename migration script | `scripts/migrate_gql_stg_names.py`, `tests/test_migrate_gql_stg_names.py` |
| 6 | Canonical-source audit script — **script and tests only, do not run it against the warehouse** | `scripts/audit_canonical_sources.py`, `tests/test_audit_canonical_sources.py` |

Work **test-first**, exactly as the spec's steps describe: write the failing test, run it, watch
it fail, then write the implementation.

### Useful line numbers (verify before editing — the file may have shifted)

- `cfb_system_maker/graphql_client.py` — `GQL_DEFAULT_TABLES` ends around line 38.
- `cfb_system_maker/duckdb_load.py` — `_stg_dest_name` ~1086; call sites ~493-503 and ~1487-1501;
  `gameLines` / `linesProvider` references at ~547, 562, 569, 580, 695, 720-721, 725, 734, 737, 741.

---

## NON-GOALS — do not do these

- **Task 5** (running the migration against the live warehouse) — a human runs it.
- **Task 7** (docs) and **Task 8** (MotherDuck mirror) — out of scope.
- Renaming any **column**, or changing column casing anywhere.
- Touching the `core` schema or `cfb_system_maker/duckdb_core.py`.
- Any change to `raw` schema naming — `raw` preserves source fidelity by design.

---

## Hard constraints

- **Do not read, modify, or connect to `data/cfb.duckdb` or anything under `data/`.** Every new
  test builds its own fixture with `duckdb.connect(":memory:")`. The warehouse is 4.9 GB and is
  not backed up for this run.
- **Do not make any network call.** No CFBD API, no MotherDuck, no `md:cfb`.
- **Do not edit `cfbd-python/`** — vendored upstream.
- **Do not commit, stage, push, or touch git in any way.** Leave all changes in the working tree.
  A human reviews the diff and commits.
- **Do not edit** `docs/db-summary.html` or `scripts/gen_db_summary.py`.
- Match the surrounding code's style: type hints, `from __future__ import annotations` where the
  module already uses it, and the existing comment voice — comments explain **why**, in full
  sentences.

---

## Proof

```
python -m pytest
```

**Baseline: 679 passed, 6 deselected, ~140 seconds.** The suite must still pass with your new
tests added to that count. It is slow — let it finish, do not interrupt it.

If the suite fails to import with a `RuntimeError` about `CFB_DATA_ROOT`, that env var is
required by `cfb_paths.py`. It should already be set to `C:\Users\mckel\dev\cfb\data`; if not,
set it and re-run. Do not edit `cfb_paths.py` to work around it.

If an existing test fails referencing `_stg_dest_name`, update it to `stg_dest_name` and drop the
`taken` argument — that rename is the point of Task 2, not an accident.

---

## Report back with

1. **Files changed** — one line each: path + what changed and why.
2. **Full `python -m pytest` output.**
3. **New test count vs the 679 baseline**, and which tasks contributed which tests.
4. **Any deviation from the spec, with the reason.** If a step was impossible as written,
   implement the closest faithful version and say so — do not redesign silently.
