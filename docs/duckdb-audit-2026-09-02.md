# DuckDB warehouse audit — 2026-09-02

Full audit of `data/cfb.duckdb` (4.9 GB, 293 tables, ~39.9M rows). Read-only.
Re-run the checks with:

```bash
python scripts/audit_duckdb.py --out docs/duckdb-audit-rerun.md
```

(Write to a new path — the script emits the "Generated checks" half only; the findings
above it are hand-written. `--checks` runs a subset, e.g. `--checks layers,grains`.)

Findings below are empirical, from the live database, and cross-checked against
[`duckdb-warehouse-plan.md`](duckdb-warehouse-plan.md), [`duckdb-core-ddl.md`](duckdb-core-ddl.md),
[`duckdb-rebuild-spec.md`](duckdb-rebuild-spec.md), [`schema-audit.md`](schema-audit.md) and
[`graphql-schema-draft.md`](graphql-schema-draft.md). The generated sections 1–10 follow.
Remediation is planned in [`duckdb-audit-remediation-plan.md`](duckdb-audit-remediation-plan.md).

**Scope note.** No index or normalization recommendations are given. DuckDB is columnar with
automatic zone maps, and `raw`/`stg` are deliberate 1:1 JSON mirrors with no relational contract —
normal-form and B-tree analysis would produce hundreds of findings, all noise. The only layer with
a designed contract is `core`, and per S1 it is empty.

## Findings, worst first

| # | Severity | Finding |
|---|---|---|
| S1 | **Critical** | `core` empty; `build_core` fails daily and its test can't see it |
| S2 | **High** | `season_type` 100% NULL on 25 `stg` tables including `stg.games` |
| S3 | **High** | The REST week spine (`raw.calendar`) never reaches `stg` |
| S4 | Medium | Documented `game_lines` grain is wrong — 12,991 apparent dupes |
| S5 | Medium | `athleteId` is VARCHAR in 17 tables, integer in 4 |
| S6 | Low | 998 season-less rows in `stg.gamePlayerStat` from a stale source file |
| S7 | Low | REST/GraphQL game coverage diverges (542 + 3 games in the shared era) |
| S8 | Low | Dead columns, and 12 GB of `data/` across three database files |
| **S9** | **Critical** | **Sampled JSON structure inference silently discards whole fields — opening lines and moneylines are 100% NULL warehouse-wide** |

---

### S9 — Critical: the loader silently discards fields that are all-NULL in its 5000-row sample

**Found 2026-09-02, after the S1 fix.** Not visible to the original audit: the live-warehouse
agreement tests `pytest.skip` when `core` is missing, so they had never run. With `core` built
they run, and `test_live_warehouse_agreement_4_5_6` fails on **2,383 games**.

`_explode_table` infers each payload's shape with `json_group_structure` over
`_STRUCTURE_SAMPLE_ROWS = 5000` rows. **When every sampled value for a key is null,
`json_group_structure` types that key `"NULL"`** — and the resulting struct then discards the real
values in every row outside the sample. Measured on `raw.lines`:

```
sample=5000: "spreadOpen":"NULL",   "overUnderOpen":"NULL",   "awayMoneyline":"NULL",   "homeMoneyline":"NULL"
sample=ALL:  "spreadOpen":"DOUBLE", "overUnderOpen":"DOUBLE", "awayMoneyline":"HUGEINT","homeMoneyline":"HUGEINT"
```

The data is in the source files. `data/raw/lines_2021.json` for game 401287890 carries
`"spreadOpen": -38` and `"overUnderOpen": 55`; `stg.lines` has NULL for both. Five columns are
**100% NULL across all 38,689 staged line rows, every season 2013–2026** — and `core.fact_game_line`
inherits all five:

| column | non-null of 38,689 |
|---|---:|
| `spread_close` | 38,600 |
| `total_close` | 35,098 |
| `spread_open` | **0** |
| `total_open` | **0** |
| `moneyline_home` / `moneyline_away` | **0** |

**Why this one matters most.** Opening lines are the input to the line-movement and CLV work.
The Python path (`enrich._build_line_move_index`) reads the raw JSON directly and *does* see the
opens — it is correct, and its fail-closed contract holds. So the SQL warehouse and the Python
feature path disagree on 2,383 games, with the warehouse wrong.

**This is not specific to `lines`.** Any payload key that is null throughout the first 5000 rows
is zeroed table-wide. It means S8's "74 payload columns 100% NULL" cannot be read as "these
fields are empty upstream" — an unknown share are sampling casualties holding real data.

**Fixed 2026-09-02 (`b3e4eb9`).** `_payload_structure` now collects the JSONPaths that came back
`"NULL"`-typed and adds one targeted sample per path — rows where *that* path is populated — then
lets `json_group_structure` merge types across the union.

Two simpler alternatives were measured and rejected:

| Approach | Result |
|---|---|
| Re-scan the full column | **OOMs** on `raw.plays` — 12 GiB, 21.8s to fail. This is what the original `LIMIT` was guarding against. |
| Widen `_STRUCTURE_SAMPLE_ROWS` | Narrows the window without closing it: `plays.wallclock` is still `"NULL"`-typed at a 500,000-row sample. |
| **Targeted union (shipped)** | Bounded and exact for any key that appears at all. `lines` 0.7s, `plays` 3.0s; every lost field recovered. |

Recovered on the live warehouse after a re-explode: 8,413 opening spreads, 6,917 opening totals
and 7,899 moneylines in `stg.lines__lines`, all previously zero.

### S1 — Critical: `core` is empty, and `build_core` fails on every refresh

Live schemas are `raw` (120), `stg` (134), `stg_gql` (38), `meta` (1) and an **empty `core`** —
0 tables, plus no `mart` and zero views (§1). The warehouse is an unconformed staging mirror.

Root cause, confirmed by the refresh log — not inferred. `data/logs/cfbd_refresh.log`,
2026-09-01 05:00:

```
=== rebuild cfb.duckdb ===
  File "scripts/refresh_cfbd.py", line 69, in main
    built = build_core(db_path)
  File "cfb_system_maker/duckdb_core.py", line 43, in build_core
    _build_dim_week(con)
_duckdb.CatalogException: Catalog Error: Table with name calendar does not exist!
Did you mean "raw.calendar"?
LINE 18:           FROM stg.calendar
---- exited 1 ----
```

[`duckdb_core.py:87`](../cfb_system_maker/duckdb_core.py:87) builds `core.dim_week` with
`FROM stg.calendar`. That table does not exist: the GraphQL staging rename on 2026-09-01 moved
it to `stg_gql.calendar`, and the REST calendar was never exploded into `stg` at all (S3).
`_build_dim_week` is the first call in `build_core`'s body
([`duckdb_core.py:43`](../cfb_system_maker/duckdb_core.py:43)), so the run aborts before any
`core` table is created. The `CREATE SCHEMA IF NOT EXISTS core` on the line above committed —
which is why an empty `core` schema sits in the live file — and nothing after it did.

Why nobody noticed: [`tests/test_core_agreement.py:87`](../tests/test_core_agreement.py:87)
creates its own `stg.calendar` fixture, the pre-migration name. All 703 tests pass against a
schema the warehouse no longer has, so the agreement gates cannot see this class of break.

Blast radius is narrower than it first looks: **nothing in production reads `core`.** Every
reference outside the builder lives in `tests/test_core_agreement.py`, and its
live-warehouse tests `pytest.skip` when `core.fact_game` is missing
([line 605](../tests/test_core_agreement.py:605)) — so they skip silently rather than fail.
`cfb_system_maker`, `models/` and `research/` all still read the Python
`GameRecord` / `features.json` path. The accurate statement is: the layer three design docs
treat as the conformance target has never existed in a shipped build, and the daily refresh has
been failing to create it since the rename.

**Fix:** `_build_dim_week` needs a source carrying `(season, week, seasonType)`. Neither
surviving calendar table offers that — `stg_gql.calendar` has `season` 100% NULL with the value
in `year` (S3), so this is a re-source, not a repoint. `raw.calendar` is the right source: its
JSON payload has exactly `season` / `seasonType` / `week` / `startDate` / `endDate` across
2012–2026 (258 rows), readable via `json_extract` the way `_build_dim_team` already reads
`raw.teams`. Then change the test fixture to build whatever the loader actually produces, so the
gate can fail for real.

**Separately, the 2026-09-02 05:00 refresh never reached `build_core` — but it was interrupted,
not buggy.** The log records that run starting and nothing after it, and
`data/cfb.duckdb.building` was left at 2.2 GB holding 53 of 120 `raw` tables with a 30 MB
uncheckpointed WAL, stamped 05:07 (S8). No Python process is running, and the `.cmd` wrapper
always writes `---- exited N ----` on a non-zero exit — so this is a killed process (sleep or
shutdown), not a raw-load crash. The traceback is missing because Python block-buffers stdout
when redirected; see the remediation plan's step 2. The orphan `.building` is harmless:
`build_duckdb` unlinks it on entry, and a stale `.wal` beside a fresh file was tested to connect
clean with no replay.

### S2 — High: `season_type` is 100% NULL on `stg.games` and 24 other tables

The loader derives `season` / `week` / `season_type` from the **source filename**; the API
payload carries the twins `year` / `seasonType`. Where a dataset is scraped as one whole-corpus
file, the filename-derived column is NULL while the payload twin holds the truth. §10 lists all
36 collisions. The damaging one:

| table | `season_type` non-null | `seasonType` non-null |
|---|---:|---:|
| `stg.games` (54,267 rows) | **0** | 54,267 |

`stg.games.seasonType` splits regular 52,984 / postseason 751 / spring_regular 504 /
spring_postseason 28. A query filtering `season_type = 'postseason'` returns **zero rows,
silently** — the failure mode is an empty result set, not an error. No committed code reads
`season_type` off DuckDB today, so this is a latent trap rather than active breakage; it will
bite the first `core`/`mart` query or ad-hoc analysis that trusts the column name. Same shape on `stg.lines`,
`stg.weather`, `stg.media`, `stg.ppa_games`, `stg.rankings*`, `stg.advanced_game_stats`, and on
nine `stg_gql` tables where `season` is NULL and `year` is populated (`recruit` 93,363,
`ratings` 14,730, `draft_picks` 13,080, `coach_season` 12,564, …).

**Fix:** either coalesce the payload twin into the partition column at explode time, or drop the
partition column where it is unpopulated so a filter fails loudly instead of returning nothing.

### S3 — High: the REST week spine never reaches `stg`

`raw.calendar` (258 rows, seasons 2012–2026) is the **only** genuinely unstaged REST table — the
other 35 `raw`-only entries are `gql_*` tables that correctly land in `stg_gql` (§3). The sole
staged calendar is `stg_gql.calendar` (424 rows, 2002–2026), and its `season` column is 100% NULL
with `year` carrying the value.

That combination is what breaks S1: `build_core` wants a `(season, week, season_type)` spine and
neither surviving table offers one under those column names.

### S4 — Medium: documented `game_lines` grain is wrong

`graphql-schema-draft.md` declares the `game_lines` PK as `(gameId, linesProviderId)`. Against
live data that key has **12,991 duplicates** over 59,627 rows. Adding `period` makes it unique
(59,627 / 59,627, §5). The table also mixes two providers of record in `line_source`:
`cfbd` 38,647 and `actionnetwork` 20,980.

This is a documentation defect, not a loader bug — but any `core` fact built on the documented
key would fan out 22% of its rows. Update the doc before Phase 1b consumes it.

All other declared grains verify clean: `stg.games` (54,267 unique `gameId`), `stg_gql.game`,
`stg.teams` on `(teamId, season)`, `stg.venues`, `stg.conferences`, `stg_gql.current_teams`,
`stg.lines`.

### S5 — Medium: key columns carry inconsistent physical types

The REST-string vs GraphQL-int `athleteId` split documented in `schema-audit.md` is **still
live** (§4): VARCHAR in 17 tables (`stg.roster`, `stg.play_stats`, `stg.recruits`,
`stg.ppa_players_*`, `stg.player_success_*`, `stg.player_usage*`, `stg.adjusted_player_*`,
`stg.kicker_paar`), BIGINT in 2, UBIGINT in 2. Joining across those without an explicit cast
returns nothing.

Also mixed, lower risk because DuckDB casts implicitly: `season` INTEGER 233 / UBIGINT 56 /
BIGINT 1; `week` INTEGER 253 / UBIGINT 36 / BIGINT 1; `team_id` BIGINT 2 / UBIGINT 2.

### S6 — Low: 998 season-less rows from a stale source file

**The documented `_post_wk` season-loss bug does not reproduce.** Of 319 season/year columns
checked, exactly 2 are partially NULL (§6) — both the same dataset:

`stg.gamePlayerStat` / `raw.gamePlayerStat` — 5,541,660 rows, 998 with NULL `season` (0.02%).
Those 998 come from a single unpartitioned `data/graphql/gamePlayerStat.json`; the other
5,540,662 come from 14 per-season `gamePlayerStat_YYYY.json` files. Their other payload fields
(`gameTeam_gameId`, `gameTeam_teamId`, `athlete_name`, `category_name`) are NULL too, so these
are partial records from a superseded whole-corpus dump left in the source directory. Remove the
file or exclude it from the glob.

The other 102 fully-NULL season columns are the by-design partition-column case (S2), not loss.

### S7 — Low: REST/GraphQL game coverage diverges; REST internal integrity is clean

Referential integrity **within** REST is perfect: 0 orphan `gameId` across 27 fact tables and
~12.9M rows, including `stg.plays` (2.6M) and the 5.5M-row player-stat explosion (§9). One
exception: `stg.weather` has a single orphan row.

Across sources, `stg_gql.game` holds 112,672 games spanning 1869–2026 while `stg.games` holds
54,267 spanning 1992–2026. In the shared 1992+ era, **542 GraphQL games have no REST row** and
3 REST games have no GraphQL row. `schema-audit.md`'s note that coverage differs still holds;
its 2023 figures (3,595 REST vs 3,404 GQL) are stale but directionally right. The apparent
1871 "gap" in `stg_gql.game` is real history — no season was played.

Line coverage is the practical constraint: `stg.lines` covers 2012–2026 (15,384 games) against
54,267 games in `stg.games`.

### S8 — Low: dead columns and disk

§8, scanning 266 tables ≤200K rows (27 larger skipped): **74 payload columns 100% NULL** and
**148 single-valued**, concentrated in `stg.games__*LineScores`, `stg.games`,
`stg.actionnetwork_scoreboard__markets__*` and the one-off `stg.lines_2026_week*` snapshots.
This matches the known stale-column scraper issue. Partition columns are counted separately
(547 / 91) since they are NULL by design.

`data/` is 12 GB across three database files:

| file | size | mtime |
|---|---:|---|
| `cfb.duckdb` | 4.9 GB | 2026-09-02 07:10 |
| `cfb.duckdb.bak-2026-09-01` | 4.9 GB | 2026-09-01 10:08 |
| `cfb.duckdb.building` + `.wal` | 2.2 GB + 30 MB | 2026-09-02 05:07 |

`cfb.duckdb.building` holds only `raw` (53 tables) and carries a 30 MB uncheckpointed WAL — a
rebuild that stalled mid-transaction this morning. **Not deleted; that is your call.**

Separately, `meta.load_report` is internally clean — 120/120 tables present, 0 row-count
mismatches, 0 recorded errors (§2) — but it is stamped `2026-09-01 09:11:55` while `cfb.duckdb`
was last written `2026-09-02 07:10`. The only read-write opener of the live
file outside the loader is [`scripts/promote_to_motherduck.py:67`](../scripts/promote_to_motherduck.py:67),
whose `ATTACH '{src_path}' AS src` is **deliberately** not `READ_ONLY` — the script stamps
`src.meta.warehouse_version` on a real promote, and `--dry-run` correctly returns before that
write. Since no `warehouse_version` table exists in the live file, the most likely explanation
is a read-write attach that touched the header without changing content. Nothing to fix; the
practical takeaway stands either way — `load_report` is not a reliable freshness signal, because
writers other than the loader can open this file.

## Prior-doc status

| Doc | Claim | Status |
|---|---|---|
| `schema-audit.md` | `game_id` / `team_id` share an id space | **verified** — 0 orphans REST-internal |
| `schema-audit.md` | `athlete_id` REST-string vs GQL-int | **still open** (S5) |
| `schema-audit.md` | REST/GQL game coverage differs | **verified**, counts restated (S7) |
| `duckdb-rebuild-spec.md` | `_post_wk` files lose `season` | **does not reproduce** (S6) |
| `graphql-schema-draft.md` | `game_lines` PK `(game_id, lines_provider_id)` | **wrong** — needs `period` (S4) |
| `duckdb-warehouse-plan.md` | 97 `raw` tables | stale — now 120 |
| `duckdb-core-ddl.md` | Phase 1a–1c implemented | code yes, **build broken** (S1) |


### Lookahead constraint

The repo's no-lookahead rule is enforced in the Python feature registry
(`cfb_system_maker/features.py`, `result_lookahead` group), not in the warehouse.
`raw`/`stg` are verbatim source mirrors with no pre-game contract to violate, and the
layer that would carry one (`core`) does not exist (S1). Nothing to check at the DB
level until `core` builds.

---

## Generated checks

Everything below is emitted by `scripts/audit_duckdb.py`.

## 1. Layer completeness

| schema | tables | status |
|---|---:|---|
| `raw` | 120 | ok |
| `stg` | 134 | ok |
| `stg_gql` | 38 | ok |
| `core` | 0 | **MISSING** |
| `meta` | 1 | ok |

Views: 0. Total tables: 293.

## 2. Loader reconciliation (`meta.load_report` vs live tables)

- Report rows: 120; loaded_at range: 2026-09-01 09:11:55.961439 .. 2026-09-01 09:11:55.961439
- Reported tables missing from DB: **0**
- Row-count mismatches (report vs live): **0**
- Loader-recorded errors: **0**

## 3. raw to stg parity

- `raw` tables: 120; `stg` tables: 134
- stg with no same-named raw parent: **50**
- raw with no stg child: **36**
- same-named pairs with differing row counts: **2**

raw-only: `actionnetwork_odds`, `calendar`, `gql_adjusted_player_metrics`, `gql_adjusted_team_metrics`, `gql_athlete`, `gql_athlete_team`, `gql_calendar`, `gql_coach`, `gql_coach_season`, `gql_conference`, `gql_current_teams`, `gql_draft_picks`, `gql_draft_position`, `gql_draft_team`, `gql_game`, `gql_game_lines`, `gql_game_team`, `gql_game_weather`, `gql_historical_team`, `gql_hometown`, `gql_lines_provider`, `gql_player_stat_category`, `gql_player_stat_type`, `gql_poll`, `gql_poll_rank`, `gql_poll_type`, `gql_position`, `gql_predicted_points`, `gql_ratings`, `gql_recruit`, `gql_recruit_position`, `gql_recruit_school`, `gql_recruiting_team`, `gql_team_talent`, `gql_transfer`, `gql_weather_condition`

<details><summary>stg-only (50)</summary>

- `stg.actionnetwork_scoreboard__last_play` (6,445 rows)
- `stg.actionnetwork_scoreboard__latest_odds` (6,708 rows)
- `stg.actionnetwork_scoreboard__linescore` (39,802 rows)
- `stg.actionnetwork_scoreboard__markets` (9,953 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score` (31,370 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline` (17,680 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_spread` (19,697 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_total` (19,679 rows)
- `stg.actionnetwork_scoreboard__ranks` (874 rows)
- `stg.actionnetwork_scoreboard__teams` (21,736 rows)
- `stg.advanced_box_score__players_ppa` (191,566 rows)
- `stg.advanced_box_score__players_usage` (191,566 rows)
- `stg.advanced_box_score__teams_cumulativePpa` (22,982 rows)
- `stg.advanced_box_score__teams_explosiveness` (22,982 rows)
- `stg.advanced_box_score__teams_fieldPosition` (22,982 rows)
- `stg.advanced_box_score__teams_havoc` (22,982 rows)
- `stg.advanced_box_score__teams_ppa` (22,982 rows)
- `stg.advanced_box_score__teams_rushing` (22,982 rows)
- `stg.advanced_box_score__teams_scoringOpportunities` (22,982 rows)
- `stg.advanced_box_score__teams_successRates` (22,982 rows)
- `stg.cfp_games__slots` (104 rows)
- `stg.cfp_playoff__participants` (64 rows)
- `stg.cfp_playoff__rounds` (28 rows)
- `stg.cfp_playoff__rounds__rounds_matchups` (52 rows)
- `stg.cfp_playoff__rounds__rounds_matchups__rounds_matchups_slots` (104 rows)
- `stg.coaches__seasons` (1,937 rows)
- `stg.fbs_teams__alternateNames` (3,943 rows)
- `stg.fbs_teams__logos` (3,634 rows)
- `stg.game_player_stats__teams` (30,792 rows)
- `stg.game_player_stats__teams__teams_categories` (247,543 rows)
- `stg.game_player_stats__teams__teams_categories__teams_categories_types` (1,249,445 rows)
- `stg.game_player_stats__teams__teams_categories__teams_categories_types__teams_categories_types_athletes` (5,528,960 rows)
- `stg.game_team_stats__teams` (29,704 rows)
- `stg.game_team_stats__teams__teams_stats` (873,037 rows)
- `stg.games__awayLineScores` (179,947 rows)
- `stg.games__homeLineScores` (179,947 rows)
- `stg.lines_2026_week1_20260826__lines` (150 rows)
- `stg.lines_2026_week1_20260831__lines` (236 rows)
- `stg.lines_2026_week1__lines` (236 rows)
- `stg.lines_2026_week2_20260826__lines` (9 rows)
- `stg.lines_2026_week2__lines` (2 rows)
- `stg.lines__lines` (38,689 rows)
- `stg.pff_facet_offense_summary_21580__offense_summary` (43 rows)
- `stg.pff_facet_offense_summary_21580__restricted` (15 rows)
- `stg.rankings__polls` (913 rows)
- `stg.rankings__polls__polls_ranks` (22,846 rows)
- `stg.roster__recruitIds` (90,420 rows)
- `stg.team_stats__statValue_any_of_schemas` (224,484 rows)
- `stg.teams__alternateNames` (18,356 rows)
- `stg.teams__logos` (16,866 rows)

</details>

| table | raw rows | stg rows |
|---|---:|---:|
| `actionnetwork_history` | 10,974 | 149,997 |
| `actionnetwork_scoreboard` | 175 | 10,868 |

## 4. Key-column type consistency

Keys carrying more than one physical type: **4**

| key | type | tables |
|---|---|---:|
| `athleteid` | `VARCHAR` | 17 |
| `athleteid` | `UBIGINT` | 2 |
| `athleteid` | `BIGINT` | 2 |
| `season` | `INTEGER` | 233 |
| `season` | `UBIGINT` | 56 |
| `season` | `BIGINT` | 1 |
| `team_id` | `BIGINT` | 2 |
| `team_id` | `UBIGINT` | 2 |
| `week` | `INTEGER` | 253 |
| `week` | `UBIGINT` | 36 |
| `week` | `BIGINT` | 1 |

`athleteid` typed VARCHAR in: stg.adjusted_player_passing, stg.adjusted_player_rushing, stg.kicker_paar, stg.player_success_game, stg.player_success_game_ngt, stg.player_success_season, stg.player_success_season_ngt, stg.player_usage, stg.player_usage_ngt, stg.play_stats, stg.ppa_players_games, stg.ppa_players_games_ngt, stg.ppa_players_season, stg.ppa_players_season_ngt, stg.recruits, stg.roster, stg.roster__recruitIds

## 5. Declared grain vs actual (duplicate keys)

| table | key | rows | distinct keys | dupes |
|---|---|---:|---:|---:|
| `stg.games` | gameId | 54,267 | 54,267 | 0 |
| `stg_gql.game` | gameId | 112,672 | 112,672 | 0 |
| `stg.teams` | teamId, season | 8,682 | 8,682 | 0 |
| `stg.venues` | venueId | 852 | 852 | 0 |
| `stg.conferences` | conferenceId, season | 256 | 256 | 0 |
| `stg_gql.calendar` | season, week, seasonType | 424 | 29 | **395** |
| `stg_gql.game_lines` | gameId, linesProviderId | 59,627 | 46,636 | **12,991** |
| `stg_gql.game_lines` | gameId, linesProviderId, period | 59,627 | 59,627 | 0 |
| `stg_gql.current_teams` | teamId | 684 | 684 | 0 |
| `stg.lines` | gameId | 15,384 | 15,384 | 0 |

## 6. Season/week integrity (documented `_post_wk` season-loss bug)

Checked 319 season/year columns.
- **Partially** NULL (real data loss - the `_post_wk` signature): **2**
- 100% NULL (column present but never populated by the loader): **102**

### Partially NULL (investigate)

| table | col | rows | nulls | min | max |
|---|---|---:|---:|---:|---:|
| `raw.gamePlayerStat` | `season` | 5,541,660 | **998** (0.02%) | 2012 | 2025 |
| `stg.gamePlayerStat` | `season` | 5,541,660 | **998** (0.02%) | 2012 | 2025 |

<details><summary>100% NULL (102)</summary>

- `stg_gql.game_team__lineScores`.`season` (362,224 rows)
- `raw.gql_game_team`.`season` (225,344 rows)
- `stg_gql.game_team`.`season` (225,344 rows)
- `raw.gql_athlete_team`.`season` (171,553 rows)
- `stg_gql.athlete_team`.`season` (171,553 rows)
- `raw.gql_athlete`.`season` (158,932 rows)
- `stg_gql.athlete`.`season` (158,932 rows)
- `raw.gql_game`.`season` (112,672 rows)
- `raw.gql_recruit`.`season` (93,363 rows)
- `stg_gql.recruit`.`season` (93,363 rows)
- `stg_gql.historical_team__images`.`season` (54,064 rows)
- `raw.gql_poll_rank`.`season` (49,948 rows)
- `stg_gql.poll_rank`.`season` (49,948 rows)
- `raw.gql_game_lines`.`season` (38,647 rows)
- `raw.gql_game_weather`.`season` (27,857 rows)
- `stg_gql.game_weather`.`season` (27,857 rows)
- `raw.gameMedia`.`season` (23,907 rows)
- `stg.gameMedia`.`season` (23,907 rows)
- `raw.gql_predicted_points`.`season` (19,800 rows)
- `stg_gql.predicted_points`.`season` (19,800 rows)
- `raw.gql_transfer`.`season` (18,909 rows)
- `raw.gql_ratings`.`season` (14,730 rows)
- `stg_gql.ratings`.`season` (14,730 rows)
- `raw.gql_hometown`.`season` (14,201 rows)
- `stg_gql.hometown`.`season` (14,201 rows)
- `raw.gql_draft_picks`.`season` (13,080 rows)
- `stg_gql.draft_picks`.`season` (13,080 rows)
- `raw.gql_coach_season`.`season` (12,564 rows)
- `stg_gql.coach_season`.`season` (12,564 rows)
- `raw.actionnetwork_history`.`season` (10,974 rows)
- `raw.predicted_points`.`season` (10,140 rows)
- `stg.predicted_points`.`season` (10,140 rows)
- `raw.gql_adjusted_player_metrics`.`season` (9,502 rows)
- `stg_gql.adjusted_player_metrics`.`season` (9,502 rows)
- `raw.gql_recruit_school`.`season` (9,282 rows)
- `stg_gql.recruit_school`.`season` (9,282 rows)
- `raw.gql_recruiting_team`.`season` (4,578 rows)
- `stg_gql.recruiting_team`.`season` (4,578 rows)
- `raw.recruiting_groups`.`season` (3,764 rows)
- `stg.recruiting_groups`.`season` (3,764 rows)
- `raw.conference_affiliations`.`season` (3,604 rows)
- `stg.conference_affiliations`.`season` (3,604 rows)
- `raw.gql_historical_team`.`season` (3,448 rows)
- `stg_gql.historical_team`.`season` (3,448 rows)
- `raw.gql_poll`.`season` (2,447 rows)
- `raw.gql_team_talent`.`season` (2,413 rows)
- `stg_gql.team_talent`.`season` (2,413 rows)
- `raw.gql_adjusted_team_metrics`.`season` (2,363 rows)
- `stg_gql.adjusted_team_metrics`.`season` (2,363 rows)
- `raw.gql_coach`.`season` (1,842 rows)
- `stg_gql.coach`.`season` (1,842 rows)
- `raw.venues`.`season` (852 rows)
- `stg.venues`.`season` (852 rows)
- `raw.venue_orientation`.`season` (798 rows)
- `stg.venue_orientation`.`season` (798 rows)
- `raw.gql_current_teams`.`season` (684 rows)
- `stg_gql.current_teams`.`season` (684 rows)
- `raw.gql_calendar`.`season` (424 rows)
- `stg_gql.calendar`.`season` (424 rows)
- `raw.conferences`.`season` (256 rows)
- `raw.gql_conference`.`season` (256 rows)
- `stg.conferences`.`season` (256 rows)
- `stg_gql.conference`.`season` (256 rows)
- `raw.lines_2026_week1`.`season` (144 rows)
- `raw.lines_2026_week1_20260831`.`season` (144 rows)
- `raw.field_goal_ep`.`season` (100 rows)
- `stg.field_goal_ep`.`season` (100 rows)
- `raw.lines_2026_week1_20260826`.`season` (99 rows)
- `raw.lines_2026_week2`.`season` (86 rows)
- `raw.lines_2026_week2_20260826`.`season` (86 rows)
- `raw.play_types`.`season` (49 rows)
- `stg.play_types`.`season` (49 rows)
- `stg.pff_facet_offense_summary_21580__offense_summary`.`season` (43 rows)
- `raw.stat_categories`.`season` (38 rows)
- `stg.stat_categories`.`season` (38 rows)
- `raw.draft_teams`.`season` (32 rows)
- `raw.gql_draft_team`.`season` (32 rows)
- `stg.draft_teams`.`season` (32 rows)
- `stg_gql.draft_team`.`season` (32 rows)
- `raw.gql_draft_position`.`season` (31 rows)
- `stg_gql.draft_position`.`season` (31 rows)
- `raw.draft_positions`.`season` (29 rows)
- `stg.draft_positions`.`season` (29 rows)
- `raw.gql_position`.`season` (28 rows)
- `raw.gql_recruit_position`.`season` (28 rows)
- `stg_gql.position`.`season` (28 rows)
- `stg_gql.recruit_position`.`season` (28 rows)
- `raw.gql_weather_condition`.`season` (27 rows)
- `stg_gql.weather_condition`.`season` (27 rows)
- `raw.play_stat_types`.`season` (26 rows)
- `stg.play_stat_types`.`season` (26 rows)
- `raw.gql_player_stat_type`.`season` (24 rows)
- `stg_gql.player_stat_type`.`season` (24 rows)
- `stg_gql.lines_provider`.`season` (17 rows)
- `stg.pff_facet_offense_summary_21580__restricted`.`season` (15 rows)
- `raw.gql_lines_provider`.`season` (12 rows)
- `raw.gql_player_stat_category`.`season` (10 rows)
- `stg_gql.player_stat_category`.`season` (10 rows)
- `raw.gql_poll_type`.`season` (8 rows)
- `stg_gql.poll_type`.`season` (8 rows)
- `raw.pff_facet_offense_summary_21580`.`season` (1 rows)
- `stg.pff_facet_offense_summary_21580`.`season` (1 rows)

</details>

## 7. Season coverage

| table | season col | seasons | min | max | gaps |
|---|---|---:|---:|---:|---|
| `stg.games` | `season` | 35 | 1992 | 2026 | - |
| `stg_gql.game` | `season` | 157 | 1869 | 2026 | **1871** |
| `stg.lines` | `season` | 15 | 2012 | 2026 | - |
| `stg.plays` | `season` | 14 | 2012 | 2025 | - |
| `stg.drives` | `season` | 14 | 2012 | 2025 | - |
| `stg.actionnetwork_scoreboard` | `season` | 12 | 2015 | 2026 | - |
| `stg.teams` | `season` | 14 | 2012 | 2025 | - |
| `stg.advanced_game_stats` | `season` | 14 | 2012 | 2025 | - |
| `stg.game_player_stats` | `season` | 14 | 2012 | 2025 | - |
| `stg.recruits` | `season` | 14 | 2012 | 2025 | - |
| `stg.roster` | `season` | 14 | 2012 | 2025 | - |
| `stg.ratings_sp` | - | - | - | - | no season column |
| `stg.ppa_teams` | `season` | 14 | 2012 | 2025 | - |

## 8. Dead columns (100% NULL / single-valued)

Scanned 266 tables (<= 200,000 rows); 27 larger tables skipped.

Loader-added partition columns (`_source_file`, `season`, `season_type`, `week`) are reported separately: they are NULL by design on datasets scraped as one whole-corpus file.

- 100% NULL: **621** total = **74** payload columns + 547 partition columns

<details><summary>100% NULL, payload columns (74)</summary>

- `meta.load_report`.`error` (120 rows)
- `stg.actionnetwork_scoreboard__linescore`.`linescore_starting_team_possession` (39,802 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score`.`markets_event_core_bet_type_6_team_score_odds_coefficient_score` (31,370 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline`.`markets_event_moneyline_odds_coefficient_score` (17,680 rows)
- `stg.actionnetwork_scoreboard__teams`.`teams_standings_overtime_losses` (21,736 rows)
- `stg.games`.`homePostgameWinProbability` (54,267 rows)
- `stg.games`.`awayPostgameWinProbability` (54,267 rows)
- `stg.games`.`venueId` (54,267 rows)
- `stg.games`.`venue` (54,267 rows)
- `stg.games`.`attendance` (54,267 rows)
- `stg.games`.`excitementIndex` (54,267 rows)
- `stg.games`.`notes` (54,267 rows)
- `stg.games__awayLineScores`.`homePostgameWinProbability` (179,947 rows)
- `stg.games__awayLineScores`.`awayPostgameWinProbability` (179,947 rows)
- `stg.games__awayLineScores`.`venueId` (179,947 rows)
- `stg.games__awayLineScores`.`venue` (179,947 rows)
- `stg.games__awayLineScores`.`attendance` (179,947 rows)
- `stg.games__awayLineScores`.`excitementIndex` (179,947 rows)
- `stg.games__awayLineScores`.`notes` (179,947 rows)
- `stg.games__awayLineScores`.`awayLineScores` (179,947 rows)
- `stg.games__homeLineScores`.`homePostgameWinProbability` (179,947 rows)
- `stg.games__homeLineScores`.`awayPostgameWinProbability` (179,947 rows)
- `stg.games__homeLineScores`.`venueId` (179,947 rows)
- `stg.games__homeLineScores`.`venue` (179,947 rows)
- `stg.games__homeLineScores`.`attendance` (179,947 rows)
- `stg.games__homeLineScores`.`excitementIndex` (179,947 rows)
- `stg.games__homeLineScores`.`notes` (179,947 rows)
- `stg.games__homeLineScores`.`homeLineScores` (179,947 rows)
- `stg.lines_2026_week1_20260826`.`homeScore` (99 rows)
- `stg.lines_2026_week1_20260826`.`awayScore` (99 rows)
- `stg.lines_2026_week1_20260826__lines`.`homeScore` (150 rows)
- `stg.lines_2026_week1_20260826__lines`.`awayScore` (150 rows)
- `stg.lines_2026_week2`.`homeScore` (86 rows)
- `stg.lines_2026_week2`.`awayScore` (86 rows)
- `stg.lines_2026_week2_20260826`.`homeScore` (86 rows)
- `stg.lines_2026_week2_20260826`.`awayScore` (86 rows)
- `stg.lines_2026_week2_20260826__lines`.`homeScore` (9 rows)
- `stg.lines_2026_week2_20260826__lines`.`awayScore` (9 rows)
- `stg.lines_2026_week2__lines`.`homeScore` (2 rows)
- `stg.lines_2026_week2__lines`.`awayScore` (2 rows)
- `stg.lines__lines`.`lines_awayMoneyline` (38,689 rows)
- `stg.lines__lines`.`lines_homeMoneyline` (38,689 rows)
- `stg.lines__lines`.`lines_overUnderOpen` (38,689 rows)
- `stg.lines__lines`.`lines_spreadOpen` (38,689 rows)
- `stg.team_stats`.`statValue_anyof_schema_1_validator` (112,242 rows)
- `stg_gql.game`.`homePostgameWinProb` (112,672 rows)
- `stg_gql.game`.`awayPostgameWinProb` (112,672 rows)
- `stg_gql.game`.`startTimeTbd` (112,672 rows)
- `stg_gql.game`.`venueId` (112,672 rows)
- `stg_gql.game`.`attendance` (112,672 rows)
- `stg_gql.game`.`excitement` (112,672 rows)
- `stg_gql.game`.`notes` (112,672 rows)
- `stg_gql.game__awayLineScores`.`homePostgameWinProb` (181,112 rows)
- `stg_gql.game__awayLineScores`.`awayPostgameWinProb` (181,112 rows)
- `stg_gql.game__awayLineScores`.`startTimeTbd` (181,112 rows)
- `stg_gql.game__awayLineScores`.`venueId` (181,112 rows)
- `stg_gql.game__awayLineScores`.`attendance` (181,112 rows)
- `stg_gql.game__awayLineScores`.`excitement` (181,112 rows)
- `stg_gql.game__awayLineScores`.`notes` (181,112 rows)
- `stg_gql.game__awayLineScores`.`awayLineScores` (181,112 rows)
- `stg_gql.game__homeLineScores`.`homePostgameWinProb` (181,112 rows)
- `stg_gql.game__homeLineScores`.`awayPostgameWinProb` (181,112 rows)
- `stg_gql.game__homeLineScores`.`startTimeTbd` (181,112 rows)
- `stg_gql.game__homeLineScores`.`venueId` (181,112 rows)
- `stg_gql.game__homeLineScores`.`attendance` (181,112 rows)
- `stg_gql.game__homeLineScores`.`excitement` (181,112 rows)
- `stg_gql.game__homeLineScores`.`notes` (181,112 rows)
- `stg_gql.game__homeLineScores`.`homeLineScores` (181,112 rows)
- `stg_gql.game_weather`.`windGust` (27,857 rows)
- `stg_gql.poll_rank`.`firstPlaceVotes` (49,948 rows)
- `stg_gql.poll_rank`.`points` (49,948 rows)
- `stg_gql.poll_type`.`abbreviation` (8 rows)
- `stg_gql.recruit`.`overallRank` (93,363 rows)
- `stg_gql.recruit`.`positionRank` (93,363 rows)

</details>

- single-valued: **239** total = **148** payload columns + 91 partition columns

<details><summary>single-valued, payload columns (148)</summary>

- `meta.load_report`.`schema` (120 rows)
- `meta.load_report`.`loaded_at` (120 rows)
- `raw.conference_affiliations`.`source_file` (3,604 rows)
- `raw.conferences`.`source_file` (256 rows)
- `raw.draft_positions`.`source_file` (29 rows)
- `raw.draft_teams`.`source_file` (32 rows)
- `raw.field_goal_ep`.`source_file` (100 rows)
- `raw.gameMedia`.`source_file` (23,907 rows)
- `raw.gql_adjusted_player_metrics`.`source_file` (9,502 rows)
- `raw.gql_adjusted_team_metrics`.`source_file` (2,363 rows)
- `raw.gql_athlete`.`source_file` (158,932 rows)
- `raw.gql_athlete_team`.`source_file` (171,553 rows)
- `raw.gql_calendar`.`source_file` (424 rows)
- `raw.gql_coach`.`source_file` (1,842 rows)
- `raw.gql_coach_season`.`source_file` (12,564 rows)
- `raw.gql_conference`.`source_file` (256 rows)
- `raw.gql_current_teams`.`source_file` (684 rows)
- `raw.gql_draft_picks`.`source_file` (13,080 rows)
- `raw.gql_draft_position`.`source_file` (31 rows)
- `raw.gql_draft_team`.`source_file` (32 rows)
- `raw.gql_game`.`source_file` (112,672 rows)
- `raw.gql_game_lines`.`source_file` (38,647 rows)
- `raw.gql_game_weather`.`source_file` (27,857 rows)
- `raw.gql_historical_team`.`source_file` (3,448 rows)
- `raw.gql_hometown`.`source_file` (14,201 rows)
- `raw.gql_lines_provider`.`source_file` (12 rows)
- `raw.gql_player_stat_category`.`source_file` (10 rows)
- `raw.gql_player_stat_type`.`source_file` (24 rows)
- `raw.gql_poll`.`source_file` (2,447 rows)
- `raw.gql_poll_rank`.`source_file` (49,948 rows)
- `raw.gql_poll_type`.`source_file` (8 rows)
- `raw.gql_position`.`source_file` (28 rows)
- `raw.gql_predicted_points`.`source_file` (19,800 rows)
- `raw.gql_ratings`.`source_file` (14,730 rows)
- `raw.gql_recruit`.`source_file` (93,363 rows)
- `raw.gql_recruit_position`.`source_file` (28 rows)
- `raw.gql_recruit_school`.`source_file` (9,282 rows)
- `raw.gql_recruiting_team`.`source_file` (4,578 rows)
- `raw.gql_team_talent`.`source_file` (2,413 rows)
- `raw.gql_transfer`.`source_file` (18,909 rows)
- `raw.gql_weather_condition`.`source_file` (27 rows)
- `raw.lines_2026_week1`.`source_file` (144 rows)
- `raw.lines_2026_week1_20260826`.`source_file` (99 rows)
- `raw.lines_2026_week1_20260831`.`source_file` (144 rows)
- `raw.lines_2026_week2`.`source_file` (86 rows)
- `raw.lines_2026_week2_20260826`.`source_file` (86 rows)
- `raw.pff_facet_offense_summary_21580`.`payload` (1 rows)
- `raw.pff_facet_offense_summary_21580`.`source_file` (1 rows)
- `raw.play_stat_types`.`source_file` (26 rows)
- `raw.play_types`.`source_file` (49 rows)
- `raw.predicted_points`.`source_file` (10,140 rows)
- `raw.recruiting_groups`.`source_file` (3,764 rows)
- `raw.stat_categories`.`source_file` (38 rows)
- `raw.venue_orientation`.`source_file` (798 rows)
- `raw.venues`.`source_file` (852 rows)
- `stg.actionnetwork_scoreboard`.`league_id` (10,868 rows)
- `stg.actionnetwork_scoreboard`.`league_name` (10,868 rows)
- `stg.actionnetwork_scoreboard__last_play`.`league_id` (6,445 rows)
- `stg.actionnetwork_scoreboard__last_play`.`league_name` (6,445 rows)
- `stg.actionnetwork_scoreboard__latest_odds`.`league_id` (6,708 rows)
- `stg.actionnetwork_scoreboard__latest_odds`.`league_name` (6,708 rows)
- `stg.actionnetwork_scoreboard__linescore`.`league_id` (39,802 rows)
- `stg.actionnetwork_scoreboard__linescore`.`league_name` (39,802 rows)
- `stg.actionnetwork_scoreboard__markets`.`league_id` (9,953 rows)
- `stg.actionnetwork_scoreboard__markets`.`league_name` (9,953 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score`.`league_id` (31,370 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score`.`league_name` (31,370 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score`.`markets_event_core_bet_type_6_team_score_event_type` (31,370 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score`.`markets_event_core_bet_type_6_team_score_period` (31,370 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score`.`markets_event_core_bet_type_6_team_score_type` (31,370 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline`.`league_id` (17,680 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline`.`league_name` (17,680 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline`.`markets_event_moneyline_event_type` (17,680 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline`.`markets_event_moneyline_period` (17,680 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline`.`markets_event_moneyline_type` (17,680 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline`.`markets_event_moneyline_value` (17,680 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_spread`.`league_id` (19,697 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_spread`.`league_name` (19,697 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_spread`.`markets_event_spread_event_type` (19,697 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_spread`.`markets_event_spread_period` (19,697 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_spread`.`markets_event_spread_type` (19,697 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_total`.`league_id` (19,679 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_total`.`league_name` (19,679 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_total`.`markets_event_total_event_type` (19,679 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_total`.`markets_event_total_period` (19,679 rows)
- `stg.actionnetwork_scoreboard__markets__markets_event_total`.`markets_event_total_type` (19,679 rows)
- `stg.actionnetwork_scoreboard__ranks`.`league_id` (874 rows)
- `stg.actionnetwork_scoreboard__ranks`.`league_name` (874 rows)
- `stg.actionnetwork_scoreboard__ranks`.`ranks_poll` (874 rows)
- `stg.actionnetwork_scoreboard__teams`.`league_id` (21,736 rows)
- `stg.actionnetwork_scoreboard__teams`.`league_name` (21,736 rows)
- `stg.adjusted_player_passing`.`position` (2,497 rows)
- `stg.advanced_season_stats`.`defense_openFieldYardsTotal` (1,892 rows)
- `stg.advanced_season_stats_ngt`.`defense_openFieldYardsTotal` (1,815 rows)
- `stg.cfp_games`.`game_completed` (52 rows)
- `stg.cfp_games__slots`.`game_completed` (104 rows)
- `stg.cfp_playoff`.`competition` (12 rows)
- `stg.cfp_playoff`.`status` (12 rows)
- `stg.cfp_playoff__participants`.`competition` (64 rows)
- `stg.cfp_playoff__participants`.`status` (64 rows)
- `stg.cfp_playoff__rounds`.`competition` (28 rows)
- `stg.cfp_playoff__rounds`.`status` (28 rows)
- `stg.cfp_playoff__rounds__rounds_matchups`.`competition` (52 rows)
- `stg.cfp_playoff__rounds__rounds_matchups`.`status` (52 rows)
- `stg.cfp_playoff__rounds__rounds_matchups`.`rounds_matchups_game_completed` (52 rows)
- `stg.cfp_playoff__rounds__rounds_matchups__rounds_matchups_slots`.`competition` (104 rows)
- `stg.cfp_playoff__rounds__rounds_matchups__rounds_matchups_slots`.`status` (104 rows)
- `stg.cfp_playoff__rounds__rounds_matchups__rounds_matchups_slots`.`rounds_matchups_game_completed` (104 rows)
- `stg.coach_seasons`.`ties` (1,961 rows)
- `stg.coaches__seasons`.`seasons_ties` (1,937 rows)
- `stg.core_ratings`.`modelVersion` (1,309 rows)
- `stg.core_ratings`.`throughSeasonType` (1,309 rows)
- `stg.core_ratings`.`throughWeek` (1,309 rows)
- `stg.fbs_teams`.`classification` (1,817 rows)
- `stg.fbs_teams__alternateNames`.`classification` (3,943 rows)
- `stg.fbs_teams__logos`.`classification` (3,634 rows)
- `stg.games__awayLineScores`.`completed` (179,947 rows)
- `stg.games__homeLineScores`.`completed` (179,947 rows)
- `stg.lines_2026_week1`.`seasonType` (144 rows)
- `stg.lines_2026_week1_20260826`.`seasonType` (99 rows)
- `stg.lines_2026_week1_20260826`.`homeClassification` (99 rows)
- `stg.lines_2026_week1_20260826__lines`.`seasonType` (150 rows)
- `stg.lines_2026_week1_20260826__lines`.`homeClassification` (150 rows)
- `stg.lines_2026_week1_20260831`.`seasonType` (144 rows)
- `stg.lines_2026_week1_20260831__lines`.`seasonType` (236 rows)
- `stg.lines_2026_week1__lines`.`seasonType` (236 rows)
- `stg.lines_2026_week2`.`seasonType` (86 rows)
- `stg.lines_2026_week2`.`homeClassification` (86 rows)
- `stg.lines_2026_week2_20260826`.`seasonType` (86 rows)
- `stg.lines_2026_week2_20260826`.`homeClassification` (86 rows)
- `stg.lines_2026_week2_20260826__lines`.`seasonType` (9 rows)
- `stg.lines_2026_week2_20260826__lines`.`homeClassification` (9 rows)
- `stg.lines_2026_week2_20260826__lines`.`awayClassification` (9 rows)
- `stg.lines_2026_week2__lines`.`seasonType` (2 rows)
- `stg.lines_2026_week2__lines`.`homeClassification` (2 rows)
- `stg.lines_2026_week2__lines`.`awayClassification` (2 rows)
- `stg.lines_2026_week2__lines`.`lines_idx` (2 rows)
- `stg.lines_2026_week2__lines`.`lines_provider` (2 rows)
- `stg.pff_facet_offense_summary_21580`.`offense_summary` (1 rows)
- `stg.pff_facet_offense_summary_21580`.`restricted` (1 rows)
- `stg.records`.`postseason_ties` (5,772 rows)
- `stg.recruits`.`recruitType` (45,927 rows)
- `stg.team_stats`.`statValue_any_of_schemas` (112,242 rows)
- `stg.weather`.`snowfall` (21,249 rows)
- `stg_gql.game__awayLineScores`.`status` (181,112 rows)
- `stg_gql.game__homeLineScores`.`status` (181,112 rows)
- `stg_gql.historical_team__images`.`active` (54,064 rows)
- `stg_gql.historical_team__images`.`countryCode` (54,064 rows)

</details>

## 9. Orphan game ids (vs `stg.games`)

| table | col | rows | orphan game ids | orphan rows |
|---|---|---:|---:|---:|
| `stg.advanced_game_stats` | `gameId` | 29,114 | 0 | 0 |
| `stg.advanced_game_stats_ngt` | `gameId` | 29,112 | 0 | 0 |
| `stg.cfp_games` | `game_id` | 52 | 0 | 0 |
| `stg.cfp_games__slots` | `game_id` | 104 | 0 | 0 |
| `stg.drives` | `gameId` | 363,504 | 0 | 0 |
| `stg.games` | `gameId` | 54,267 | 0 | 0 |
| `stg.games__awayLineScores` | `gameId` | 179,947 | 0 | 0 |
| `stg.games__homeLineScores` | `gameId` | 179,947 | 0 | 0 |
| `stg.game_havoc_stats` | `gameId` | 20,773 | 0 | 0 |
| `stg.game_player_stats` | `gameId` | 15,457 | 0 | 0 |
| `stg.game_player_stats__teams` | `gameId` | 30,792 | 0 | 0 |
| `stg.game_player_stats__teams__teams_categories` | `gameId` | 247,543 | 0 | 0 |
| `stg.game_player_stats__teams__teams_categories__teams_categories_types` | `gameId` | 1,249,445 | 0 | 0 |
| `stg.game_player_stats__teams__teams_categories__teams_categories_types__teams_categories_types_athletes` | `gameId` | 5,528,960 | 0 | 0 |
| `stg.game_team_stats` | `gameId` | 14,852 | 0 | 0 |
| `stg.game_team_stats__teams` | `gameId` | 29,704 | 0 | 0 |
| `stg.game_team_stats__teams__teams_stats` | `gameId` | 873,037 | 0 | 0 |
| `stg.lines` | `gameId` | 15,384 | 0 | 0 |
| `stg.lines__lines` | `gameId` | 38,689 | 0 | 0 |
| `stg.media` | `gameId` | 17,825 | 0 | 0 |
| `stg.player_success_game` | `gameId` | 148,257 | 0 | 0 |
| `stg.player_success_game_ngt` | `gameId` | 132,913 | 0 | 0 |
| `stg.plays` | `gameId` | 2,600,679 | 0 | 0 |
| `stg.play_stats` | `gameId` | 410,083 | 0 | 0 |
| `stg.ppa_games` | `gameId` | 22,493 | 0 | 0 |
| `stg.ppa_games_ngt` | `gameId` | 22,493 | 0 | 0 |
| `stg.pregame_win_prob` | `gameId` | 11,028 | 0 | 0 |
| `stg.weather` | `gameId` | 21,249 | **1** | 1 |
| `stg.win_probability` | `gameId` | 1,554,334 | 0 | 0 |
| `stg_gql.game` | `gameId` | 112,672 | **58,408** | 58,408 |
| `stg_gql.game_lines` | `gameId` | 59,627 | 0 | 0 |
| `stg_gql.game_team` | `gameId` | 225,344 | **58,408** | 116,816 |
| `stg_gql.game_team__lineScores` | `gameId` | 362,224 | **339** | 2,770 |
| `stg_gql.game_weather` | `gameId` | 27,857 | **204** | 204 |
| `stg_gql.game__awayLineScores` | `gameId` | 181,112 | **339** | 1,385 |
| `stg_gql.game__homeLineScores` | `gameId` | 181,112 | **339** | 1,385 |

## 10. Partition vs payload twin columns (`season`/`year`, `season_type`/`seasonType`)

| table | partition col | non-null | payload twin | non-null | risk |
|---|---|---:|---|---:|---|
| `stg_gql.adjusted_player_metrics` | `season` | 0 | `year` | 9,502 | **partition col unusable - filter on payload twin** |
| `stg_gql.adjusted_team_metrics` | `season` | 0 | `year` | 2,363 | **partition col unusable - filter on payload twin** |
| `stg_gql.calendar` | `season` | 0 | `year` | 424 | **partition col unusable - filter on payload twin** |
| `stg_gql.coach_season` | `season` | 0 | `year` | 12,564 | **partition col unusable - filter on payload twin** |
| `stg_gql.draft_picks` | `season` | 0 | `year` | 13,080 | **partition col unusable - filter on payload twin** |
| `stg_gql.ratings` | `season` | 0 | `year` | 14,730 | **partition col unusable - filter on payload twin** |
| `stg_gql.recruit` | `season` | 0 | `year` | 93,363 | **partition col unusable - filter on payload twin** |
| `stg_gql.recruiting_team` | `season` | 0 | `year` | 4,578 | **partition col unusable - filter on payload twin** |
| `stg_gql.team_talent` | `season` | 0 | `year` | 2,413 | **partition col unusable - filter on payload twin** |
| `stg.advanced_game_stats` | `season_type` | 0 | `seasonType` | 29,114 | **partition col unusable - filter on payload twin** |
| `stg.advanced_game_stats_ngt` | `season_type` | 0 | `seasonType` | 29,112 | **partition col unusable - filter on payload twin** |
| `stg.game_havoc_stats` | `season_type` | 0 | `seasonType` | 20,773 | **partition col unusable - filter on payload twin** |
| `stg.games` | `season_type` | 0 | `seasonType` | 54,267 | **partition col unusable - filter on payload twin** |
| `stg.games__awayLineScores` | `season_type` | 0 | `seasonType` | 179,947 | **partition col unusable - filter on payload twin** |
| `stg.games__homeLineScores` | `season_type` | 0 | `seasonType` | 179,947 | **partition col unusable - filter on payload twin** |
| `stg.lines` | `season_type` | 0 | `seasonType` | 15,384 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week1` | `season_type` | 0 | `seasonType` | 144 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week1_20260826` | `season_type` | 0 | `seasonType` | 99 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week1_20260826__lines` | `season_type` | 0 | `seasonType` | 150 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week1_20260831` | `season_type` | 0 | `seasonType` | 144 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week1_20260831__lines` | `season_type` | 0 | `seasonType` | 236 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week1__lines` | `season_type` | 0 | `seasonType` | 236 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week2` | `season_type` | 0 | `seasonType` | 86 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week2_20260826` | `season_type` | 0 | `seasonType` | 86 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week2_20260826__lines` | `season_type` | 0 | `seasonType` | 9 | **partition col unusable - filter on payload twin** |
| `stg.lines_2026_week2__lines` | `season_type` | 0 | `seasonType` | 2 | **partition col unusable - filter on payload twin** |
| `stg.lines__lines` | `season_type` | 0 | `seasonType` | 38,689 | **partition col unusable - filter on payload twin** |
| `stg.media` | `season_type` | 0 | `seasonType` | 17,825 | **partition col unusable - filter on payload twin** |
| `stg.ppa_games` | `season_type` | 0 | `seasonType` | 22,493 | **partition col unusable - filter on payload twin** |
| `stg.ppa_games_ngt` | `season_type` | 0 | `seasonType` | 22,493 | **partition col unusable - filter on payload twin** |
| `stg.pregame_win_prob` | `season_type` | 0 | `seasonType` | 11,028 | **partition col unusable - filter on payload twin** |
| `stg.rankings` | `season_type` | 0 | `seasonType` | 229 | **partition col unusable - filter on payload twin** |
| `stg.rankings__polls` | `season_type` | 0 | `seasonType` | 913 | **partition col unusable - filter on payload twin** |
| `stg.rankings__polls__polls_ranks` | `season_type` | 0 | `seasonType` | 22,846 | **partition col unusable - filter on payload twin** |
| `stg.weather` | `season_type` | 0 | `seasonType` | 21,249 | **partition col unusable - filter on payload twin** |
| `stg_gql.calendar` | `season_type` | 0 | `seasonType` | 424 | **partition col unusable - filter on payload twin** |
| `stg_gql.game` | `season_type` | 0 | `seasonType` | 112,672 | **partition col unusable - filter on payload twin** |
| `stg_gql.game__awayLineScores` | `season_type` | 0 | `seasonType` | 181,112 | **partition col unusable - filter on payload twin** |
| `stg_gql.game__homeLineScores` | `season_type` | 0 | `seasonType` | 181,112 | **partition col unusable - filter on payload twin** |
| `stg_gql.poll` | `season_type` | 0 | `seasonType` | 2,447 | **partition col unusable - filter on payload twin** |
