---
task: graphql-orderby-and-aggregate-check
date: 2026-08-28
mode: quick
status: complete
---

# Quick Task 260828-w5n — Summary

Two findings from the CFBD GraphQL docs, both fixed.

## 1. `orderBy` had never been applied

`_paginate` emitted `order_by: {id: asc}` behind `"order_by" in table.args`. The live arg is
`orderBy` and its enum is uppercase — probing shows `asc` is rejected outright — so the gate
was always false and **every paginated pull ran `limit`/`offset` unsorted**, which the docs
warn against because there is then no stable row order between pages.

The fixture in `tests/test_graphql.py` advertised `order_by` as well, which is exactly why
no test caught it. It now mirrors the live schema, and both the existing assertion and a new
test check the emitted arg.

Fix verified against the source's own counts: `teamTalent` 2,413/2,413, `coach` 1,842/1,842,
`coachSeason` 12,564/12,564, `recruitingTeam` 4,578/4,578 — ordered pulls, exact matches.

## 2. Aggregates turn coverage into row counts

20 of the 35 defaulted tables expose `{table}Aggregate { aggregate { count } }`. The audit
now compares each dump to it. Counting avoids parsing — `game.json` is 103 MB — by counting
the `  {` lines `indent=2` puts at the head of every top-level row (verified equal to the
parsed length on `teamTalent`). The 15 tables without an aggregate variant are reported as
file-existence only rather than silently implied to be checked.

Drift never changes the exit code. A stale dump is a re-pull decision; only a
reached-but-unaccounted table is a wiring bug.

## What the check found — twelve tables behind the source

| Table | Disk | Source | Δ |
|---|---|---|---|
| `coachSeason` | 1,937 | 12,564 | −10,627 |
| `recruit` | 50,820 | 93,363 | −42,543 |
| `recruitingTeam` | 2,963 | 4,578 | −1,615 |
| `historicalTeam` | 2,148 | 3,448 | −1,300 |
| `gameLines` | 38,484 | 38,647 | −163 |
| `teamTalent` | 2,278 | 2,413 | −135 |
| `hometown`, `recruitSchool`, `coach`, `currentTeams` | | | −275, −85, −26, −1 |
| `athleteTeam`, `game` | 171,864 / 112,673 | 171,553 / 112,672 | +311, +1 |

Fresh ordered pulls of `coachSeason` and `recruitingTeam` match the source exactly, so the
shortfall lives in the dumps on disk (June/July pulls), not in the client. Magnitudes like
85% of `coachSeason` are too large to be four weeks of new rows — those files were most
likely pulled under a season filter or before a source backfill. **Re-pull was explicitly
deferred by the user**; the audit now reports the gap on every run.

Suite: 566 passed, 1 skipped.

## Also checked, no action

The docs' query-root list matches introspection exactly — 37 real tables, all accounted for.
`distinctOn` and subscriptions exist but neither helps a bulk dump. `CLAUDE.md`'s claim that
`conference` is a non-paginated view lacking `limit`/`offset` is stale (it advertises all
five args); the sentence was rewritten while correcting the `orderBy` note beside it.
