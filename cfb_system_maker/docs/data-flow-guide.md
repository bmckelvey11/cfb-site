# Data flow guide — sources, warehouse, consumers

Living reference. Last verified 2026-09-16 against the code and the
[data audit](data-audit-2026-09-11.md). When a step here stops matching the code, fix
the code or this page in the same commit.

**Read this first if you are asking:** where does a number in the app or a model come
from, what runs on a schedule, what is hand-run, and which files under `data/` matter.

```
CFBD REST ──┐                                        ┌─ Flask system maker (games.csv, features.json)
CFBD GraphQL ├─► data/raw, data/graphql ─► cfb.duckdb ─┤─ models/totals (games.csv)
Action Net. ─┤   data/ingest ─► data/processed        ├─ models/over_zero (raw.an_*, ingest/oddsapi)
PFF, odds ───┘                     ▲                  └─ research/spread (stg.game, an_history_tick)
                                   │
                    scripts/refresh_cfbd.py (daily 05:00) ties it together
```

## 1. Where things live

| Path | What | Written by | Committed? |
|---|---|---|---|
| `data/raw/*.json` | One JSON payload per CFBD REST endpoint × season (or × week, × game) | `python -m cfb_system_maker scrape` | no |
| `data/raw/actionnetwork/` | Action Network scoreboard and history payloads (scrape retired 2026-09-11; tape still loaded) | `collect_line_timing.py` (Mondays) | no |
| `data/raw/pff/` | PFF facet, modeling, scoreboard pulls | `scripts/pull_pff_*.py`, hand-run | no |
| `data/graphql/*.json` | One dump per CFBD GraphQL table (50) | `python -m cfb_system_maker graphql`; `game` and `gameLines` re-pulled daily | no |
| `data/ingest/oddsapi/`, `ingest/oddspapi/` | the-odds-api snapshots (every 6 h), Pinnacle snapshots (daily 06:15) | `scripts/pull_odds.py`, `scripts/pull_oddspapi.py` | no |
| `data/ingest/snapshots/` | Point-in-time REST line snapshots. Not globbed by the loader on purpose | hand | no |
| `data/ingest/massey/`, `ingest/prediction_tracker/` | Massey ranks, Prediction Tracker captures | `CFB-Massey-Weekly` task (`scripts/pull_massey.cmd`); `CFB-PT-Snapshot` task | no |
| `data/processed/games.csv` | The flat game table the app and the totals model read | `refresh_cfbd.py` → `cli.rebuild_processed_games` | no |
| `data/processed/features.json` | Registry-driven features for the app | `python -m cfb_system_maker enrich` | no |
| `data/processed/{actionnetwork,pff,oddsapi,massey}/*.csv` | Flattened vendor tables the loader picks up | `scripts/*_flatten.py`, run by the refresh | no |
| `data/cfb.duckdb` | The warehouse. Local file is the source of truth | `refresh_cfbd.py` → `build_duckdb` + `build_core` | no |
| `data/cfb.duckdb.lock` | Cross-process rebuild lock (a tiny DuckDB file, held open for the rebuild) | loader | no |
| `data/audit/schema_*.json` | Schema snapshots the hygiene audit diffs against | `scripts/audit_data_hygiene.py` | no |
| `data/logs/cfbd_refresh.log`, `logs/task_runs.csv` | Refresh transcript; one row per scheduled-task run | `refresh_cfbd.cmd`, `task_ledger.cmd` | no |
| `md:cfb` (MotherDuck) | Manual mirror of `raw`/`stg`/`core`/`meta` | `scripts/promote_to_motherduck.py`, hand-run | n/a |

`CFB_DATA_ROOT` points at `data/` and resolves through root `cfb_paths.py`. Nothing under
`data/` is committed.

## 2. Sources

**CFBD REST** (`cfb_system_maker/scrapers.py`). The `ENDPOINTS` registry names every
vendored-client method worth keeping plus the `_ngt` (no garbage time) twins, which are a
second source because `excludeGarbageTime` changes the aggregates. Shapes: `once`
(`name.json`), `season` (`name_2024.json`), `season_week`, `grid`, `per_game`/`per_player`
(fan out over ids already on disk, opt-in), `on_demand` (registered, skipped in bulk). A full
sweep is hand-run; the daily refresh force-rescrapes only `games lines calendar conferences
venues` for the current season. Empty `[]` files for early seasons are documented floors,
not failures ([data-coverage.md](../../docs/data-coverage.md)). Re-check registry vs disk
with `scripts/audit_coverage.py`, registry vs live spec with `scripts/audit_endpoints.py`.

**CFBD GraphQL** (`cfb_system_maker/graphql_client.py`). Hasura introspection, paginated by
`orderBy`, one dump per table. Only `game` and `gameLines` are on the refresh path, staged
and swapped with a ≥95 %-retained short-read guard. The other dumps are hand-pulled and age
until someone re-pulls them; `scripts/audit_graphql_dump_age.py` measures which of those
reach `core` ([graphql-dump-staleness-2026-09-11.md](../../docs/graphql-dump-staleness-2026-09-11.md)).
GraphQL spells a missing number as the string `"NaN"`; the loader nulls it (§4).

**Action Network.** Two paths, easy to conflate. The bulk scoreboard/history scrape
(`python -m cfb_system_maker actionnetwork`) is retired as of 2026-09-11
([odds-sources-an-vs-apis-2026-09-11.md](../../docs/odds-sources-an-vs-apis-2026-09-11.md)).
The line-timing collector (`research/spread/scripts/collect_line_timing.py`, task
`CFB-AN-History`, Mondays 09:00) still runs through the 2026 season and lands under
`raw/actionnetwork/`. `scripts/actionnetwork_flatten.py` turns the tape into
`processed/actionnetwork/an_history_tick.csv` on every refresh.

**PFF.** Hand-pulled through the Restish CLI ([pff-cli.md](../../docs/pff-cli.md)) into
`raw/pff/`; `scripts/pff_flatten.py` folds ~30 report shapes into 19 tables under
`processed/pff/` ([pff-warehouse-schema.md](../../docs/pff-warehouse-schema.md)). Schema
pinned by `scripts/check_pff_pin.py`.

**the-odds-api and Pinnacle.** `scripts/pull_odds.py` (`CFB-Odds-Snapshot`, every 6 h) and
`scripts/pull_oddspapi.py` (`CFB-Pinnacle-Snapshot`, daily 06:15) write snapshots to
`ingest/`; `scripts/oddsapi_flatten.py` makes `processed/oddsapi/oa_odds_tick.csv` and
`oa_snapshot.csv`. History starts 2026-09-09; before that the only line movement is the
Action Network tape ([oddsapi-ingest.md](../../docs/oddsapi-ingest.md)).

**Massey and Prediction Tracker.** Massey is pulled weekly by `CFB-Massey-Weekly`
(`scripts/pull_massey.cmd`: `massey_ranks.py update` fetches the current season's missing
editions, then `massey_flatten.py` rewrites `processed/massey/`; Tuesday 04:30, ahead of
the 05:00 rebuild). Prediction Tracker is a hand-run scrape into `ingest/`, flattened by
`research/spread/scripts/build_prediction_tracker.py`.

**Scheduled tasks** (Windows Task Scheduler, every wrapper appends to `logs/task_runs.csv`
via `scripts/task_ledger.cmd`):

| Task | Wrapper | When |
|---|---|---|
| `cfbd_daily` | `scripts/refresh_cfbd.cmd` | 05:00 daily |
| `CFB-Odds-Snapshot` | `scripts/pull_odds.cmd` | every 6 h |
| `CFB-Pinnacle-Snapshot` | `scripts/pull_oddspapi.cmd` | 06:15 daily |
| `CFB-AN-History` | `research/spread/scripts/collect_line_timing.cmd` | Mon 09:00 |
| `CFB-OverZero-Slate` | `models/over_zero/scripts/over_zero_slate.cmd` | 09:00 and 18:00 Mon–Fri |
| `CFB-PT-Snapshot` | see `research/spread/docs/session-guide-2026-09-02.md` | every 6 h |

## 3. The daily refresh — `scripts/refresh_cfbd.py`

In order. A step marked non-fatal prints its failure and the run continues.

1. **Scrape** the current season's `games lines calendar conferences venues`, overwriting.
   Fatal: a dead REST pull stops the run before anything else is spent.
2. **Pull GraphQL** `game` and `gameLines`, staged, swapped only if ≥95 % of the previous
   row count came back. Non-fatal.
3. **Flatten** Action Network ticks, PFF, the-odds-api. Non-fatal each.
4. **Rebuild `processed/games.csv`** for the scraped season, keeping other seasons. Non-fatal.
5. **Rebuild `cfb.duckdb`**: `build_duckdb(explode=True)` then `build_core`. A second
   concurrent rebuild is refused with `RebuildInProgress` (exit 1). Per-table load and
   explode failures print as `LOAD ERROR schema.name: ...` and `build_core` still runs.
6. **Pin check** `stg.an_history_tick` against `_AN_TICK_COLUMNS`. A drift is exit 1.

Not touched: Massey, the PFF and odds pulls themselves, the 48 hand-pulled GraphQL dumps,
in-season per-week REST endpoints (`plays`, `drives`, `game_team_stats`, … stop at 2025 until
someone runs `scrape --season 2026 --only …`), MotherDuck.

Run it by hand with the repo `.venv` python and `CFBD_API_KEY` in the environment:

```bash
scripts\refresh_cfbd.cmd
```

A full run is roughly 25 minutes; the rebuild alone about 15. Never call `build_duckdb`
directly for a refresh: it skips the flattens, so the warehouse loads a stale tick CSV.

## 4. Inside the warehouse — `duckdb_load.py`, then `duckdb_core.py`

Four schemas:

| Schema | Holds | Rule |
|---|---|---|
| `raw` | One table per dump, one row per source file, payload as JSON. REST under the endpoint name, GraphQL as `gql_<table>` | Never read for analysis; it is the replay log |
| `stg` | Typed, exploded tables. REST keeps endpoint names; GraphQL lands under its bare snake_case name, `_gql` suffix only on the three colliders (`calendar_gql`, `draft_picks_gql`, `predicted_points_gql`) | The default place to query. One collapsed schema since ADR-0003; there is no `stg_gql` |
| `core` | Kimball dims and facts | What models should join to |
| `meta` | `load_report` (schema, name, files, rows, error, loaded_at) | Where a rebuild says what it did |

**Load** (`build_duckdb`). Takes the exclusive lock, stages at `cfb.duckdb.building`, sets
`threads = 1`, `preserve_insertion_order = false`, `memory_limit` (default 4 GB, override
`CFB_DUCKDB_MEMORY_LIMIT`; deliberately below DuckDB's 80 %-of-RAM default after the
2026-09-11 OOM that silently dropped the Action Network tables), loads every planned job,
writes `meta.load_report`, explodes, then atomically replaces `cfb.duckdb`. A crash leaves
the old file intact.

**Explode** (`explode_payloads`), in order:

1. Generic: each `raw` payload is typed with `json_group_structure` and unnested into `stg`.
2. Action Network children, hand-written not generic: `an_scoreboard` → `an_market`,
   `an_team`, `an_linescore`; `an_history` and `an_history_tick` from the flattened CSV.
   `an_scoreboard` is exploded one weekly file per statement to stay under the memory limit.
3. `null_nan_values`: any `stg` JSON column whose values are all numbers or `"NaN"` becomes
   `DOUBLE` with NaN nulled; existing `DOUBLE` columns get NaN nulled. Runs before the
   backfill because `COALESCE` treats NaN as populated.
4. `backfill_gamelines_from_actionnetwork`: widens `stg.game_lines` with `period` and
   `line_source` and merges the Action Network 1H/1Q and extra-book lines in; CFBD values
   win. If the tape is missing this reports an error instead of skipping quietly.
5. `explode_stg_lists`: nested lists to `stg.<table>__<column>` with an `_idx`.
6. Timestamp promotion, dead-column drop.

**Core** (`build_core`), fixed order, each merge skipped with a warning if its `stg` source is
absent:

| Table | Built from | Notes |
|---|---|---|
| `dim_week` | `raw.calendar` | one `postseason` row per season, so postseason games do not join |
| `dim_conference` | `stg.conferences` + `stg.conference` | |
| `dim_team` | `raw.teams` + `raw.fbs_teams` | opponents outside CFBD's team table get name-derived ids; LEFT JOIN to `dim_team` |
| `dim_venue` | `stg.venues` | |
| `fact_game` | REST games 2012+, selected close per provider | `has_line`, `selected_spread`, `selected_total` are REST-defined; the pred-tracker-model reads them |
| `fact_game_line` | unnest of `stg.lines.lines` at `(game_id, provider_key)` | then `_merge_game_lines` full-outer-joins the `stg.game_lines` tape (`period='game'`); REST wins conflicts, `_source` ∈ {`rest`, `gql`, `both`}, disagreements kept in `fact_game_line_conflicts` |
| `dim_lines_provider` | distinct books on the merged tape | DraftKings aliases collapse to one key |
| `fact_game_team` | running stats over `fact_game` | same code path as the app's `running_stats` |
| `fact_game_odds` | `stg.oa_odds_tick` | 2026-09-09 onward only |
| `dim_coach`, `fact_coach_season`, `dim_draft_pick`, `dim_recruit`, `fact_team_talent` | GraphQL `stg` tables | unmatched coaches land in `coach_season_unmatched` |
| `fact_game_historical` | GraphQL `stg.game` pre-2012 | |

Conventions that bite: `stg.games` is REST and regular season; `stg.game` is GraphQL with
postseason, and is the source of record for season-type completeness. Betting lines floor at
2013. Pre-game features may only use information available before kickoff; anything
result-informed carries the `result_lookahead` tag.

## 5. Who reads what

| Consumer | Entry point | Reads | Does not read |
|---|---|---|---|
| Flask system maker (filters, systems, dashboard) | `cfb_system_maker/web.py`, `features.py`, `enrich.py`, `prior_game_stats.py` | `processed/games.csv`, `processed/features.json`, raw JSON indexed in-process | the warehouse, at all |
| Totals model | `models/totals/data.py` | `processed/games.csv` | the warehouse |
| Over-zero board | `models/over_zero/scripts/build_1h_games.py`, `build_1h_lines.py` | `raw.an_scoreboard`, `raw.an_history` (read-only, the only consumer on `raw`) | |
| Over-zero slate (scheduled) | `models/over_zero/scripts/best_line_slate.py` | `processed/over_zero/`, `ingest/oddsapi/` → `site/lib/board.json` | the warehouse |
| Spread line-movement model | `research/spread/scripts/weekly_slate.py` | upstream processed files → `weekly_slate_<stamp>.csv` + `latest` pointer | |
| Prediction Tracker build | `research/spread/scripts/build_prediction_tracker.py` | `stg.game` (needs postseason) | `stg.games` |
| Timing decay eval | `research/spread/scripts/eval_timing_decay.py` | `stg.an_history_tick`, `stg.an_scoreboard` | |
| Spread version-B eval | `research/spread/scripts/eval_version_b.py` | `core.fact_game` (finals), read-only | |
| Greenline grading | `research/totals/scripts/grade_greenline.py`; `greenline_season_review.py` imports its `warehouse_final(s)` | `core.fact_game` where PFF posts no score, read-only | |
| SQLite mirror | `scripts/mirror_duckdb_to_sqlite.py` | `raw`, `stg`, `meta` → `cfb_mirror.sqlite` | nothing reads its output; deleted 2026-09-11 |
| MotherDuck promote | `scripts/promote_to_motherduck.py` | all four schemas → `md:cfb` | hand-run only |

The consequence: a bug in `build_core` cannot reach the app or the totals model today. It can
reach research — `core.fact_game` supplies finals to the version-B spread eval and to
Greenline grading, so `build_core` is not a dead end. `fact_game_line`, `fact_game_team`,
`fact_game_odds` and `fact_game_historical` have no reader as of 2026-09-16; they are kept,
not retired. A bug in `games.csv` or `features.json` reaches the app and the totals model
both.

Every warehouse reader above opens `read_only=True` and exits. Keep it that way: a
process holding `cfb.duckdb` open makes the rebuild's final `tmp_path.replace(db_path)` fail
on Windows, which breaks refresh step 5. Check with `scripts/check_duckdb_swap_lock.py`; the
reasoning is in [app-vs-warehouse-read-path-2026-09-16.md](app-vs-warehouse-read-path-2026-09-16.md).

## 6. Checking the pipe

| Question | Run |
|---|---|
| What tables and columns exist, and what does the data look like? | Open [cfb-warehouse-catalog.html](../../docs/cfb-warehouse-catalog.html). Every table with its columns, types and first 3 rows — click a row to expand. Regenerate with `python scripts/build_warehouse_catalog.py` (`--check` tests for staleness without writing; ~18s either way) |
| Is the folder and warehouse clean? | `python scripts/audit_data_hygiene.py` (read-only; `--checks folder` skips the warehouse) |
| What did the last rebuild load, and what failed? | `SELECT * FROM meta.load_report WHERE error IS NOT NULL`; `data/logs/cfbd_refresh.log` |
| Did every scheduled task run? | `data/logs/task_runs.csv` |
| Registry vs files on disk / vs live CFBD spec | `scripts/audit_coverage.py`, `scripts/audit_endpoints.py` |
| Which GraphQL dumps are stale and reach `core`? | `scripts/audit_graphql_dump_age.py` |
| Layer completeness, dupes, orphans | `scripts/audit_duckdb.py`; what each GraphQL merge adds: `scripts/audit_core_merges.py` |
| Did the tick or PFF schema drift? | `scripts/check_an_tick_pin.py`, `scripts/check_pff_pin.py` |
| Vendor name maps, odds-api joins | `scripts/audit_team_name_maps.py`, `audit_oddsapi_game_join.py`, `audit_oddsapi_team_names.py` |
| Spread sign convention | `scripts/audit_line_sign_convention.py` |

Default verification for code changes is `python -m pytest` from the repo root.

## 7. Known gotchas

- `python -m cfb_system_maker duckdb --only <table>` **drops every table you did not name**.
  It rebuilds, it does not add. Recovery is a full rebuild.
- Rebuild through `refresh_cfbd.py`, not `build_duckdb`, or the tick CSV goes stale.
- Two rebuilds cannot overlap; the second exits 1. Wait for `cfb.duckdb.building` to vanish.
- `coalesce` treats NaN as a value. The loader nulls GraphQL `"NaN"` at the source; if you see
  a NaN in `stg` or `core`, the `null_nan_values` pass did not run.
- Point-in-time snapshots go in `ingest/snapshots/`, never `raw/`: the loader globs `raw/*.json`
  and would mint a table per snapshot.
- `dim_team` is not complete for opponents outside CFBD's team list. LEFT JOIN.
- Empty `[]` payloads are floors, listed in `docs/data-coverage.md` and mirrored in the
  audit's `KNOWN_FLOORS`. `elo_2026` and `talent_2026` are pending, not broken.

## 8. Where the detail lives

Current: [cfb-warehouse-catalog.html](../../docs/cfb-warehouse-catalog.html) (every table,
its columns and sample rows; generated, see
[the regeneration note](warehouse-catalog-regeneration-2026-09-16.md)),
[data-audit-2026-09-11.md](data-audit-2026-09-11.md) (inventory and numbers),
[data-coverage.md](../../docs/data-coverage.md) (endpoints, floors),
[duckdb-warehouse-plan.md](../../docs/duckdb-warehouse-plan.md) (design and promote runbook),
[duckdb-rebuild-spec.md](../../docs/duckdb-rebuild-spec.md), [duckdb-core-ddl.md](../../docs/duckdb-core-ddl.md),
[stg-gql-collapse-2026-09-10.md](../../docs/stg-gql-collapse-2026-09-10.md),
[core-merge-bucket-c-2026-09-10.md](../../docs/core-merge-bucket-c-2026-09-10.md),
[refresh-break-2026-09-11.md](refresh-break-2026-09-11.md) (the OOM incident),
[pff-ingest-plan.md](../../docs/pff-ingest-plan.md), [oddsapi-ingest.md](../../docs/oddsapi-ingest.md).

Superseded, kept for history under `archive/docs/`: the 2026-09-02 warehouse audit, the
schema recommendation it produced (executed by the stg collapse), the 2026-09-09 plan review
(closed by the round-5 re-review), and the spec-vs-warehouse audit (replaced by data-coverage).
