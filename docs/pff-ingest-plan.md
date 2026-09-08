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
| S2 | Settle point-in-time: per-week pulls vs dated snapshots | S3 | **done** — per week | 2026-09-08 |
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

## S2 — Point-in-time: per week ✅ 2026-09-08

**Decided: (a) the weekly file is the grain.** A facet *season* file is season-to-date at
pull time and a re-pull overwrites it, so a pre-game feature built from one leaks the rest
of the season backwards. Every PFF fact is therefore keyed `(season, week, entity)`, and
season-to-date is a windowed `SUM` over weeks `< N` — never a stored row.

Three things checked while recording this, all of which make the decision cheaper than it
looked:

- **The puller already does it.** `pull_pff_modeling.py --player-facets` pulls per week
  only; it never asks for a season-level facet. The season files sitting in
  `data/raw/pff/` are legacy snapshots from the earlier `pull_pff_facet.py` run. No puller
  change is needed — the change is entirely downstream.
- **The weekly files reconstruct the season file exactly.** Union of the 21 weekly headers
  equals the season header, column for column: `facet-passing-concept` 199, and
  `facet-passing-pressure` 197. Nothing is lost by dropping the season file as a row
  source.
- **So the schema source is the union of weeks, not the season file.** That rule also
  covers the four signature ops, which have no season file at all (their union across 22
  weekly files is 105 columns). S3 criterion 2 is amended to match.

The legacy season files stay on disk — they are a free cross-check that the union is
complete, and `audit_pff_pull.py` expects them for the facet ops. They are not row
sources; the flattener must skip any leaderboard file without a `_wk` in its name.

**Done when:** the choice is recorded here with its date, and §6 of the schema doc is
amended to match. ✅

## S3 — `scripts/pff_flatten.py`

Reads `data/raw/pff/`, writes one CSV per target table to `data/processed/pff/`. The split
unpivot regex and filename regex are given in
[`pff-warehouse-schema.md` §5.1](pff-warehouse-schema.md). Five audit findings are the
acceptance criteria — a flattener that does not handle all five is not done:

1. **Glob `.csv` *and* `.json`.** `facet-offense-summary`, `facet-rushing-direction` and
   `facet-passing-detail` exist for 2025 only as JSON (the puller's fallback). A
   `facet_*.csv` glob drops two facets silently.
2. **Schema is the union of that season's weekly headers; union by name.** Weekly column
   sets are *disjoint*, not nested: passing-concept wk11 and wk18 are both 183 wide and
   each holds four the other lacks. Never stack positionally, never pin to one week. Per
   S2 the union is the rule rather than the season file, because the signature ops have no
   season file; where a season file does exist it is asserted equal to the union as a
   cross-check (holds for 2025: 199 and 197).
3. **Load one rushing-direction view, not two.** PFF ignores `team-rushing-direction`'s
   `table` parameter: `_rows.json` and `_totals.json` are byte-identical for all 136
   franchises.
4. **Pin column types; do not infer per file.** 320 team-report columns declare two types
   across responses (`draftSeason` integer/string, percentages integer/number/string).
   Normalize blanks to NULL first, then numerics → `DOUBLE`, ids and years → `VARCHAR`.
   Same failure class as `stg.an_history_tick` (f0c729b).
5. **Read columns by name.** Order varies between teams on 7 ops with identical membership.

6. **Weekly files only.** Per S2 the grain is `(season, week, entity)`; a leaderboard file
   with no `_wk` in its name is a legacy season-to-date snapshot and is not a row source.

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

### 2026-09-08 — S2 done: per-week grain

Signed off on (a). Verified rather than assumed: the union of a season's weekly headers
equals the season header exactly for both drifting facets (199, 197), the four signature
ops have no season file at all so the union is the only available schema source, and
`pull_pff_modeling.py --player-facets` was already pulling week-only — the season files on
disk are legacy `pull_pff_facet.py` output. Net effect: no puller change, S3's schema rule
becomes "union of that season's weekly headers" instead of "the season file", and the
flattener skips any leaderboard file without `_wk` in its name. Schema doc §6 amended.
