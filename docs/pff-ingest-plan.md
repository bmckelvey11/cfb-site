# PFF ingest plan — from scraped files to warehouse tables

**Living document.** Every pass through the scraped files appends here: a step's row moves
to `done` with a date, and the worklog at the bottom gets an entry saying what was
actually found. Nothing is deleted — a step that turns out to be wrong is struck with the
reason, so the next pass does not re-open it.

**Status 2026-09-08: S1 done. 2025 is audited and clean; nothing is loaded yet.**

**Scope: `data/raw/pff/` only.** The other scrapers (CFBD, Action Network, Massey) already
land in the warehouse through `refresh_cfbd.py` and are not in this plan. Widen it only if
PFF's shape turns out to be the general case.

**Design is not in scope here.** [`pff-warehouse-schema.md`](pff-warehouse-schema.md) owns
the 19-table target, the DDL, and the open design questions. This file owns the *order* of
the work and its state. Where the two disagree, the schema doc wins on shape and this one
wins on what is finished.

## Status board

| # | Step | Blocks | State | Date |
|---|---|---|---|---|
| S1 | Audit the pull — every file verified, gaps named | everything | **done** | 2026-09-08 |
| S2 | Settle point-in-time: per-week pulls vs dated snapshots | S3 | open | — |
| S3 | `scripts/pff_flatten.py` — raw → `data/processed/pff/` | S5 | open | — |
| S4 | `pff_franchise` map — PFF slug → `cfbd_team_id` (~35 by hand) | S5 | open | — |
| S5 | `_PFF_TABLES` loader entries → `stg` | S6 | open | — |
| S6 | Backfill 2014–2024, finish 2026 | — | open | — |
| S7 | Trim the pull plan — the two calls that buy nothing | — | open | — |
| S8 | Decide the player tier: finish it or delete the smoke test | — | open | — |

## S1 — Audit the pull ✅ 2026-09-08

`python scripts/audit_pff_pull.py --season 2025`. Reusable, read-only, re-run after any
pull. Checks the three ways a PFF export fails while `restish` exits 0 (empty, error
envelope in the body, header-only), plus five cross-file conditions: duplicate bodies,
column-set drift, column-order drift, declared-type drift, and missing (op, week) cells.
Expected coverage is read off disk — ops from `pff-endpoint-reference.md`, weeks from
`team/leagues.json`, franchises from that season's `team_directory` — so it does not go
stale when the plan changes.

**2025: 4,657 files, zero unusable, zero gaps.** 639 leaderboards, 3,998 team-tier, 20
player. All 21 non-all-star weeks, all 136 FBS franchises complete. Findings and their
load-time consequences are written up in
[`pff-warehouse-schema.md` §5b](pff-warehouse-schema.md); the five that survive into the
flattener are carried as S3's acceptance criteria below.

**Done when:** the script exists, is tested, and reports 2025 clean. ✅

## S2 — Settle point-in-time

The one decision that changes the flattener's grain, so it comes first. A facet *season*
file is season-to-date at pull time and a re-pull overwrites it — build a pre-game feature
from it and the whole season leaks backwards. Two options, stated in
[`pff-warehouse-schema.md` §6](pff-warehouse-schema.md): (a) pull per week and treat
season-to-date as a windowed `SUM`, (b) keep season pulls and date the filename.

2025 already holds every week 0–20 for every op, so (a) is available today with no
re-pull. That is the recommendation; it needs a yes before S3 starts.

**Done when:** the choice is recorded here with its date, and §6 of the schema doc is
amended to match.

## S3 — `scripts/pff_flatten.py`

Reads `data/raw/pff/`, writes one CSV per target table to `data/processed/pff/`. The split
unpivot regex and filename regex are given in
[`pff-warehouse-schema.md` §5.1](pff-warehouse-schema.md). Five audit findings are the
acceptance criteria — a flattener that does not handle all five is not done:

1. **Glob `.csv` *and* `.json`.** `facet-offense-summary`, `facet-rushing-direction` and
   `facet-passing-detail` exist for 2025 only as JSON (the puller's fallback). A
   `facet_*.csv` glob drops two facets silently.
2. **Pin the schema to the season-to-date file, union weeks by name.** Weekly column sets
   are *disjoint*, not nested: passing-concept wk11 and wk18 are both 183 wide and each
   holds four the other lacks. The union across 2025 is 199 — exactly the season file's
   width. Never stack positionally; never pin to week 1.
3. **Load one rushing-direction view, not two.** PFF ignores `team-rushing-direction`'s
   `table` parameter: `_rows.json` and `_totals.json` are byte-identical for all 136
   franchises.
4. **Pin column types; do not infer per file.** 320 team-report columns declare two types
   across responses (`draftSeason` integer/string, percentages integer/number/string).
   Normalize blanks to NULL first, then numerics → `DOUBLE`, ids and years → `VARCHAR`.
   Same failure class as `stg.an_history_tick` (f0c729b).
5. **Read columns by name.** Order varies between teams on 7 ops with identical membership.

**Done when:** `data/processed/pff/` holds every table in §3 of the schema doc for 2025,
a test asserts each of the five above on a fixture, and `audit_pff_pull.py` still reports
2025 clean afterwards (the flattener must not write into `data/raw/`).

## S4 — `pff_franchise` map

~35 names that do not match on their own. Same shape as `massey_teams.match`; check
`stg.teams.alternateNames` before hand-typing anything.

**Done when:** every FBS franchise in the 2025 `team_directory` resolves to a
`cfbd_team_id`, and the join is asserted at 100% in a test.

## S5 — Loader entries

A `_PFF_TABLES` tuple beside `_MASSEY_TABLES` in `duckdb_load.py`, straight to `stg`, no
`raw` twin. The warehouse glob is not recursive and does not see `data/raw/pff/`, so
nothing else in the loader changes. Pin the column list the way `_AN_TICK_COLUMNS` is
pinned (f0c729b) — that is what finding 4 above buys.

**Done when:** a rebuild lands the PFF tables, `scripts/check_an_tick_pin.py`'s sibling
check passes for PFF, and row counts match the processed CSVs.

## S6 — Backfill and 2026

2014–2024 has not been pulled. 2026 is mid-season: 207 files, one zero-byte, 780 open
cells that fill in as weeks are played. Backfill is cheap in reads but not in exports —
size it against the measured rate limits in [`pff-cli.md`](pff-cli.md) before starting.

**Done when:** `audit_pff_pull.py` reports every backfilled season clean, and the 2026
weekly pull is on the same schedule as the Action Network history job.

## S7 — Trim the pull plan

Two calls that buy nothing, both found by the audit:

- `team-rushing-direction` is pulled twice per team (`table=rows`, `table=totals`) for one
  distinct body. Drop one, or find the parameter that actually splits the views.
- `facet-passing-detail` is already in `SKIP_FACETS` — it is the union of the other four
  passing facets and it hangs. Confirm nothing re-adds it.

**Done when:** a season pull makes 136 fewer calls and the audit still reports it clean.

## S8 — The player tier

`data/raw/pff/player/` holds 22 files for a single id (198077, Keelon Russell) — a smoke
test someone stopped after. Every graded FBS player is ~12k a season at 20 reads each, so
the full tier is not a casual pull. Either scope it to a real id list (QBs? starters?) or
delete the stub so it stops reading as partial coverage.

**Done when:** the directory holds either a deliberate cohort or nothing.

## Worklog

Append-only. One entry per pass, newest last.

### 2026-09-08 — S1 done

Wrote `scripts/audit_pff_pull.py` and `tests/test_pff_audit.py`; 2025 comes back with
4,657 files and zero defects. Three of the audit's own checks were too narrow on the first
pass and were widened before the result was trusted: `columns` was being counted as
payload (so a team report with a full header and no rows read as usable — 3,998 files were
unverified), duplicate detection skipped every file without a week (the whole per-team
tier, which is where the 136 `team-rushing-direction` duplicates were hiding), and a
leaderboard that only ever landed as JSON was not named. Findings written to
`pff-warehouse-schema.md` §5b. Commits `f522775` (script) and `c5122a8` (widened checks,
findings doc).
