# Data folder and warehouse audit — 2026-09-11

**Reproduce:** `python scripts/audit_data_hygiene.py --out <report.md> --json <findings.json>`
(read-only; `--checks folder` skips the warehouse, `--strict` exits 1 on any FAIL). Tests:
`tests/test_audit_data_hygiene.py`, `tests/test_null_nan_values.py`, and the scoreboard
cases in `tests/test_duckdb_load.py`.

## The question

Is `C:\Users\mckel\dev\cfb\data` clean, and is `data/cfb.duckdb` a trustworthy, lookahead-free
input for the totals, over-zero and spread work and the system-maker app? Concretely: what
is on disk that nothing reads, what does the warehouse load that it should not, which tables
a consumer reads today are missing, duplicated, NULL- or NaN-ridden, or stale, and which of
those can be fixed by code and a rebuild rather than by deleting someone's data.

## Method and data

- Data root as of 2026-09-11 08:00–09:00 local: `raw/` 18,653 files / 6.3 GB, `graphql/`
  50 dumps / 2.6 GB, `processed/` 638 MB, `ingest/` 102 MB, `backups/` 9.6 GB,
  `cfb.duckdb` 4.8 GB (313 tables: raw 116, stg 179, core 17, meta 1; ~46.5M rows).
- Warehouse builds examined: the 05:00 scheduled refresh (failed, exit 1), the 07:39 hand
  run, and two supervised `refresh_cfbd.py` runs made for this audit (08:13 and 08:32).
  `meta.load_report`, `data/logs/cfbd_refresh.log` and `data/logs/task_runs.csv` are the
  run evidence.
- The script inventories the folder (sizes, ages, strays, duplicates by SHA-1, raw stems
  vs the scraper registry, empty payloads vs the documented floors in `docs/data-coverage.md`,
  GraphQL dump age and whole-corpus shadow files, inputs newer than the load) and checks the
  warehouse (expected tables and columns, row counts, season coverage, duplicate keys on 20
  declared grains, NULL rates on 24 key columns, NaN across every DOUBLE column in `stg`
  and `core`, JSON-typed `stg` columns, 14 join-integrity rules, `games.csv` vs
  `core.fact_game`, and a schema snapshot diffed against the previous run's snapshot in
  `data/audit/`).
- Prior work this builds on, not repeats: `archive/docs/duckdb-audit-2026-09-02.md` (S1–S9 and the
  remediation plan), `cfb_system_maker/docs/refresh-break-2026-09-11.md` (the 05:00 failure),
  `docs/graphql-dump-staleness-2026-09-11.md`.

## Findings, worst first

### 1. Every rebuild since 2026-09-11 05:00 lost the Action Network scoreboard family — FIXED

The live warehouse at the start of this audit had no `stg.an_scoreboard`, `an_market`,
`an_team` or `an_linescore`; `stg.game_lines` was the bare 9-column GraphQL shape (no
`period`, no `line_source`), `core.fact_game_line` was REST-only (38,793 rows, `_source =
'rest'` on every row — the AN merge that adds ~8,600 rows and five books never ran), and
`tests/test_catalog_resolution.py` plus two `tests/test_core_merges.py` cases failed against
the live file.

The uncommitted `_MEMORY_LIMIT = 4GB` change in `duckdb_load.py` (another session's,
present in the working tree since 07:37) made the failure deterministic and named rather
than a machine-level OOM, and the 08:13 refresh printed it:

```
LOAD ERROR stg.an_scoreboard: OutOfMemoryException: Out of Memory Error:
  could not allocate block of size 4.2 MiB (3.7 GiB/3.7 GiB used)
```

Reproduced in isolation on a copy of `raw.an_scoreboard` (175 payloads, 132 MB of JSON)
under `memory_limit = '4GB'`: the old whole-corpus `CREATE TABLE AS ... UNNEST(...)` dies in
2.3 s. The query re-extracts ~45 fields from each game's blob, and the `markets` blobs carry
the full tick history, so with every weekly payload in one vector the working set is ~30×
the input.

**Fix (`duckdb_load._explode_an_scoreboard`):** one `INSERT ... WHERE t.source_file = ?`
per weekly file (a file is at most 4.5 MB). Same reproduction, same limit: 46 s,
`an_scoreboard` 10,868 rows, children `an_market` 88,426 / `an_team` 21,736 /
`an_linescore` 39,802 — the counts the incident writeup recorded from a healthy build. It
also passes under a 1 GB limit. The 08:32 refresh below is the end-to-end proof. This closes
`#rebuild-dropped-an-tables` (TODO.md) with the error message in hand.

### 2. GraphQL spells a missing number as the string `"NaN"`, and it reached `stg` as JSON — FIXED

`raw.gql_game_lines` carries `spread = "NaN"` on 65 rows and `overUnder = "NaN"` on 3,414;
`stg.ratings.spOffense`/`spOverall` have 2 each. `json_group_structure` sees DOUBLE on most
rows and VARCHAR on those and types the key JSON, so `stg.game_lines.spread` and
`overUnder` were **JSON-typed columns** — not numeric, not NULL, and `TRY_CAST(... AS
DOUBLE)` turns the string into a real NaN, which `coalesce` treats as populated. The AN
backfill's `COALESCE(c.spread, a.spread)` therefore never filled those rows from the tape,
and the 19 code sites reading `stg.game_lines` directly compare against a JSON value.
`core._merge_game_lines` already guarded its own reads with `isnan`; nothing upstream did.

**Fix (`duckdb_load.null_nan_values`):** a post-pass in `explode_payloads`, run before the
backfill, that retypes any `stg` JSON column whose non-null values are all numbers or
`"NaN"` to DOUBLE with the NaNs nulled, and nulls NaN in any existing DOUBLE column.
Fail-closed (a column holding anything else is untouched) and idempotent. Six tests,
including a `gameLines.json` dump end to end. Side effect: the four `LOAD ERROR
stg.game_lines__spread ... scalar JSON; nothing to explode` lines disappear from the
refresh log, since the list-explode no longer meets a scalar JSON column.

### 3. Hygiene findings the script reports — proposed actions, applied 2026-09-11 09:41

**Applied after owner sign-off (09:41 local):** `backups/` (9.6 GB), `processed/feature_backups/`
(122 MB), the five data-root scratch files, `graphql/gamePlayerStat.json` and
`processed/cfb.db` deleted; `raw/lines_2026_week1_20260903.json` and
`raw/lines_2026_week2_20260908.json` moved to `ingest/snapshots/`. Folder audit afterwards:
**0 FAIL, 5 WARN, 4 INFO** (was 16 WARN) — the five left are the two `latest` pointer
duplicates (expected) and the three empty payloads, which still want a floor entry in
`docs/data-coverage.md`. The four `lines_2026_week*` orphan tables and the 998 season-less
`stg.game_player_stat` rows stay in the live warehouse until the next `refresh_cfbd.py`
rebuild, which no longer sees their inputs. Logs in `raw/` and `raw/actionnetwork_odds.csv`
were left where they are.

The 08:29 baseline run: **6 FAIL, 21 WARN, 10 INFO**; the 6 FAILs are finding 1.
Everything below is a WARN or INFO and is a decision for the owner, because each is a
deletion or a move inside the data root.

| What | Evidence | Proposed action |
|---|---|---|
| `backups/` 9.6 GB | `cfb.duckdb.2026-09-08T1431.bak`, `cfb.duckdb.2026-09-09T0419.bak`; both predate every fix since | Delete both once the 08:32 rebuild is accepted; a rebuild from raw is ~26 min and there are 57 GB free |
| Migration leftovers in the data root | `drop_cols.sql`, `move_gql.sql` (Aug 27, reference `stg."actionnetwork_history"` — names that no longer exist), `schema_columns.csv`, `schema_columns_clean.csv`, `tmp_schema_columns.csv` (Sep 1; the last two are byte-identical) | Delete all five; they are one-off scratch from the Aug 27 / Sep 1 schema moves |
| `processed/cfb.db` (8.9 MB, Aug 26) | SQLite mirror with `games`, `upcoming`, `load_meta`; no reader outside `scripts/mirror_duckdb_to_sqlite.py`; stale by two weeks | Delete, or regenerate only if something still needs it |
| Weekly line snapshots loaded as their own tables | `raw/lines_2026_week1_20260903.json`, `raw/lines_2026_week2_20260908.json` mint `raw.lines_2026_week1_20260903` / `stg.lines_2026_week1_20260903__lines` etc. — four orphan tables; their siblings already live in `ingest/snapshots/` | Move both files to `ingest/snapshots/` |
| `graphql/gamePlayerStat.json` (Jun 13, 98 KB) | Whole-corpus file beside 14 per-season dumps; its 998 rows carry no season (`stg.game_player_stat` audit S6, still open) | Delete |
| `raw/actionnetwork_odds.csv` (Jul 31, 200,560 rows → `raw.an_odds`) | Seasons 2018, 2019, 2023–2025 only; no reader in `cfb_system_maker/`, `models/`, `research/` or `scripts/` | Move to `ingest/` (the loader only picks it up from `raw/`) |
| `processed/feature_backups/` 122 MB | Two snapshots two minutes apart on Sep 10 | Delete; `enrich` regenerates |
| `raw/_abs_backfill.log`, `raw/actionnetwork/_run.log` | Scrape logs inside the input tree (outside the loader's `*.json` glob, so harmless) | Move to `logs/` |
| Empty payloads outside the documented floors | `elo_2026.json`, `talent_2026.json` (season not yet published upstream), `srs_expanded_2020.json` (COVID season) | Add the three to the floor list in `docs/data-coverage.md`, or re-scrape `elo`/`talent` 2026 later in the season |
| `processed/weekly_slate_latest*.csv` | Byte-identical to the newest timestamped copy | Expected — `latest` is a pointer; no action |

### 4. Warehouse quality — measured clean

- **Duplicate keys:** 0 on all 20 declared grains checked (`stg.games`, `stg.game`,
  `stg.lines`, `stg.game_lines (gameId, linesProviderId[, period])`, `stg.teams`,
  `stg.venues`, `stg.calendar`, `stg.drives`, `stg.plays`, `stg.weather`, `stg.an_history`,
  `stg.an_history_tick`, `stg.oa_odds_tick`, `stg.massey_ranks`, and the `core` PKs).
- **NULL rates on key columns:** every id/date column is 0% NULL. `stg.games.venueId` is
  NULL on 7,471 rows (older seasons; not a key). `stg.lines` has 1,570 games with an empty
  `lines` list (games with no line; expected).
- **NaN:** after the rebuild the only NaN in any DOUBLE column of `stg`/`core` is gone
  (before: `stg.ratings.spDefense`, 4 rows).
- **Join integrity, must-be-zero rules:** `fact_game → stg.games`, `fact_game_line →
  fact_game`, `fact_game_line → dim_lines_provider`, `fact_game_team → fact_game`,
  `fact_game_odds → fact_game`, `fact_coach_season → dim_coach`, `fact_game.venue_id →
  dim_venue`, `fact_game.home_conference_id → dim_conference`, `an_history_tick →
  an_history` (282,876/282,876) — all 0 orphans.
- **Join integrity, documented gaps (INFO):** `fact_game.home_team_id → dim_team` 96,
  `away_team_id` 407, `fact_game_team.team_id` 503 — name-derived ids for opponents outside
  CFBD's team table (Roanoke College, New England College, Lackawanna, Chicago State 2026 …;
  `awayClassification` NULL on 401 of the 407). `fact_game → dim_week` 154, all postseason
  (the calendar carries one `postseason` row per season; documented in the remediation plan).
  `fact_team_talent.team_id` NULL on 25 rows: 17 REST-only schools GraphQL lacks
  (Jacksonville, St. Francis PA) plus 8 GraphQL rows with no team relation.
- **Coverage:** `stg.games` 1992–2026 (35 seasons, 3,679 games in 2026, 459 completed at
  audit time); `stg.lines` 2012–2026; `stg.plays`/`drives`/`game_team_stats` 2012–2025;
  `stg.win_probability` 2014–2025; `stg.massey_ranks` 1996–2025; PFF 2025–2026;
  `core.fact_game` 2012–2026 (34,645). `processed/games.csv` (13,840 rows) agrees with
  `core.fact_game.has_line` on every season.
- **Inputs vs load:** no raw, GraphQL, Action Network or processed input is newer than the
  warehouse; `meta.load_report` file counts match the files on disk for every group.

### 5. What is missing or needed (not fixed here)

- **2026 in-season per-week endpoints are not refreshed.** `plays`, `drives`,
  `game_team_stats`, `game_player_stats`, `play_stats`, `ppa_players_games`,
  `player_success_game` (and their `_ngt` twins) stop at 2025; `refresh_cfbd.py` only
  re-scrapes `games lines calendar conferences venues`. Anything computing tempo or
  season-to-date stats from `stg.drives`/`stg.plays` for 2026 games has no rows. Shape: add
  a weekly companion run of `scrape --season 2026 --only drives plays game_team_stats
  ppa_games` (season_week resume is safe — a finished week's file is skipped).
- **GraphQL dumps other than `game`/`gameLines`** are still hand-pulled: 46 of the 50 are
  the Aug 28 pull (14 days old), `linesProvider` is 52 days old, `gamePlayerStat.json` 90.
  Cadence half of `#graphql-dumps-never-refreshed` stays open.
- **`core.fact_game_odds`** covers 2026-09-09 onward only (the-odds-api started then); the
  Action Network tape (`stg.an_history_tick`, Apr–Sep 2026, 199 events) is the only line
  movement before that. Historical closing lines for backtests remain `stg.lines` /
  `core.fact_game_line`.
- **`stg.game_player_stat`** keeps 998 season-less rows until the shadow dump above is
  deleted; **`athleteId` typed VARCHAR** in 17 tables (S5) still waits on a first player join.

## What was changed

| Change | Where | Verified by |
|---|---|---|
| Scoreboard explode batched per source file | `cfb_system_maker/duckdb_load.py::_explode_an_scoreboard` | Isolated reproduction under 4 GB and 1 GB limits (counts above); the 08:32 refresh; existing scoreboard tests in `tests/test_duckdb_load.py` |
| `null_nan_values` post-pass before the AN backfill | `cfb_system_maker/duckdb_load.py`, wired in `explode_payloads` | `tests/test_null_nan_values.py` (6 cases); `stg.game_lines.spread`/`overUnder` DOUBLE after the rebuild |
| Reusable audit script | `scripts/audit_data_hygiene.py` | `tests/test_audit_data_hygiene.py` (13 cases); baseline and post-rebuild runs |

Not changed: nothing in `data/` was deleted or moved, no warehouse table was dropped by
hand, MotherDuck was not touched. The two refreshes used the normal `refresh_cfbd.py`
path (scrape → GraphQL pull → flattens → rebuild → `build_core`).

## Post-rebuild verification (08:32 refresh)

The 08:32 `refresh_cfbd.py` run swapped a new `cfb.duckdb` into place at 08:49 local
(5.2 GB, 318 tables). Read against that file at 09:12–09:13 local:

- `meta.load_report`: 144 rows, all stamped 12:40:39 UTC, **0 with an error**.
- `stg.an_scoreboard` 10,868 / `an_market` 88,426 / `an_team` 21,736 / `an_linescore`
  39,802 — the healthy counts from the incident writeup, produced by the per-file explode
  inside the normal refresh path under the 4 GB limit.
- `stg.game_lines`: 11 columns including `period` and `line_source`; `spread` and
  `overUnder` are `DOUBLE` (were JSON); 0 NaN in either, 438 NULL spreads out of 64,123
  rows. `stg.ratings.spOffense`/`spOverall` are `DOUBLE`, 0 NaN.
- `core.fact_game_line`: 38,793 rows `_source = 'both'` plus 8,587 `'gql'` — the Action
  Network merge that every rebuild since 05:00 had skipped ran.
- `scripts/audit_data_hygiene.py` against the rebuilt file: **0 FAIL, 16 WARN, 10 INFO**
  (baseline before the fixes: 6 FAIL, 21 WARN, 10 INFO). Schema drift against the
  08:50 snapshot: 0 changes. The remaining WARNs are the proposed deletions and moves in
  finding 3 plus the six genuinely mixed-type `an_scoreboard` payload columns.
- Full default test suite (`python -m pytest`) against the rebuilt file: **945 passed,
  2 skipped, 5 deselected**. Two tests in `tests/test_core_merges.py` had pinned
  2026-09-10 data rather than the property: `_source = 'rest'` > 0 (the 278 REST-only
  offers) and a non-empty `core.fact_game_line_conflicts` (~700 rows). Both numbers came
  from the Aug 28 `gameLines.json`; the refresh re-pulled it at 08:35 and the fresh dump
  covers every REST offer and agrees with REST on every value (recounted directly with
  the merge's own dedupe rule: 0 spread, 0 total, 0 moneyline disagreements across 47,380
  keys). The tests now assert the properties -- every REST offer key survives the merge,
  and every conflicts row is a genuine disagreement.

## What the results do not support

- The audit checks **presence and shape**, not correctness of values: a spread that exists
  and is numeric can still be wrong. The only value-level cross-checks are the
  `games.csv`/`fact_game` agreement and the tick-to-offer join.
- **No lookahead check is made.** Nothing here inspects whether a `pre-game` feature reads
  a result column; that is `features.py` territory and the `result_lookahead` tag, not the
  warehouse.
- The team-id orphan counts are **not** a defect in `dim_team`; they are the price of
  keeping every opponent in `fact_game`. They mean a join to `dim_team` must be a LEFT JOIN.
- The scoreboard fix removes one OOM. It does not prove the rebuild fits in 4 GB on every
  future table — `raw.plays` at 2.6M rows is the next largest explode and was not
  re-measured under the limit beyond the full run passing.
- The 1 GB reproduction is evidence of headroom on this table only; `_MEMORY_LIMIT` itself
  is another session's uncommitted change and is not committed here.
- Age-based staleness flags (`gql-dumps-stale`, `newest` columns) say a file is old, not
  that it is behind; `scripts/audit_graphql_dump_age.py` is the measurement for that.
