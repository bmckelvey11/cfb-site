# Making the warehouse navigable from a SQL prompt — 2026-09-18

**Question.** The warehouse is 324 tables across four flat schemas. Everything that tells
them apart — which upstream system a table came from, what its grain is, which joins
silently drop rows — lives *outside* the database, in `data-flow-guide.md` and a generated
HTML catalog. Neither is reachable from a SQL prompt. What can be added to the schema
itself so that the questions people actually ask ("which `game` do I want?", "is this join
lossy?") are answerable in SQL?

**Method.** Read-only inventory of `data/cfb.duckdb` (5.3 GB, built 2026-09-18 05:06)
through `duckdb_tables()` / `duckdb_constraints()` / `duckdb_indexes()`, plus measured
uniqueness and orphan counts on every `core` table. Candidate changes were applied to a
byte-identical copy and exercised by running the real `build_core` against it before
anything touched the live file.

Reproduce with `python -m cfb_system_maker duckdb` → `build_core`, or read the code:
[`cfb_system_maker/warehouse_dictionary.py`](../cfb_system_maker/warehouse_dictionary.py).

## What the inventory found

| | Before | After |
|---|---|---|
| Tables | 322 (`raw` 119, `stg` 184, `core` 18, `meta` 1) | 324 (+2 in `meta`) |
| Views | 0 | 1 (`core.v_game`) |
| Table + view comments | 0 | 44 (`core` 19, `stg` 22, `meta` 3) |
| Foreign keys | 0 | 0 — replaced by `meta.relationship`, see change 2 below |
| Primary keys | 11, all on `core` | 14 (+`dim_draft_pick`, +2 `meta`) |
| Indexes | 5, all on `core` | 5 |

The navigation cost is concentrated in `stg`, where near-identical names carry entirely
different contracts and nothing in the database says so: `game`/`games`,
`calendar`/`calendar_gql`, `conference`/`conferences`, `coach`/`coaches`/`coach_season`/
`coach_seasons`, `recruit`/`recruits`, `draft_picks`/`draft_picks_gql`,
`predicted_points`/`predicted_points_gql`, plus 12 `_ngt` twins and 37 `__`-suffixed
explosion children whose parent is only implied by the name.

## What was measured

Referential integrity across `core`, on the live 2026-09-18 build:

| Edge | Orphans | NULL keys |
|---|---:|---:|
| `fact_game.away_team_id` → `dim_team` | 401 | 0 |
| `fact_game.home_team_id` → `dim_team` | 91 | 0 |
| `fact_game_team.team_id` → `dim_team` | 492 | 0 |
| `fact_game.(season, week, season_type)` → `dim_week` | 154 | 0 |
| `fact_game.venue_id` → `dim_venue` | 0 | 226 |
| `fact_game_odds.game_id` → `fact_game` | 0 | 264 |
| `fact_game_line.game_id` → `fact_game` | 0 | 0 |
| `fact_game_line.provider_key` → `dim_lines_provider` | 0 | 0 |
| `fact_game_team.game_id` → `fact_game` | 0 | 0 |
| `fact_coach_season.coach_id` → `dim_coach` | 0 | 0 |
| `fact_team_talent.team_id` → `dim_team` | 0 | 25 |

The four lossy edges are both *known* and *intended*: `dim_team` deliberately excludes
opponents outside CFBD's team table, and `dim_week` carries one `postseason` row per
season. They are why the guide says to LEFT JOIN.

Two further findings, neither of them breakage:

- **`core.fact_team_talent` is not unique on `(season, team_id)`** — 2,430 rows, 2,413
  distinct. All 17 collisions are rows where `team_id IS NULL` (3–4 per season, 2015–2023):
  schools that did not resolve to a team. The real grain is `(season, school)`, which *is*
  unique. Recorded, not silently deduplicated.
- **`selected_spread_provider_key` and `selected_total_provider_key` differ on 2,943 games**,
  both non-NULL. Any single join from `fact_game` to `fact_game_line` on one of those keys
  attaches the other market's number from the wrong book.

## What was changed

1. **`meta.table_dictionary`** — one row per table *and view*: `object_type`,
   `source_system` (8-way: `rest`, `gql`, `pff`, `actionnetwork`, `oddsapi`, `massey`,
   `core`, `meta`), `is_exploded_child`, `parent_table`, `column_count`, and a hand-written
   `note` for the 44 objects whose name does not answer the question. Row counts are *not*
   repeated here; they live in `meta.load_report` and `duckdb_tables()`. Views are included
   because the generated HTML catalog reads `duckdb_tables()` only, so `core.v_game` — the
   one object built purely to be queried directly — is invisible there.

2. **`meta.relationship`** — the table above, as data, with `orphan_rows` and
   `null_key_rows` **measured on every build** and `is_lossy` derived from the measurement,
   so neither can go stale. This stands in for foreign keys, which DuckDB cannot add via
   `ALTER TABLE` (verified: `Not implemented Error: No support for adding FOREIGN_KEY
   constraints with ALTER TABLE`) and which would in any case be false for four of the
   eleven edges. It closes the "soft `FOREIGN KEY` clauses" item that
   [duckdb-core-ddl.md](duckdb-core-ddl.md) had left open.

3. **`COMMENT ON TABLE` / `COMMENT ON VIEW`** on the same 44 objects, so `duckdb_tables().comment`,
   `duckdb_views().comment` and any
   client's object browser show the note without knowing the dictionary exists.

4. **`core.v_game`** — `fact_game` with venue attributes, week bounds, and the selected
   spread and total lines already joined. **Two** joins to `fact_game_line`, because of the
   2,943-game finding above. Verified to preserve grain exactly: 34,645 rows in, 34,645 out.

5. **`PRIMARY KEY (year, round, pick)` on `core.dim_draft_pick`** — 13,080/13,080 distinct,
   zero NULLs, and the builder's own docstring already asserted this key.

## What this does *not* support

- **It is not a rename.** No `stg` or `core` table moved. Every existing consumer query is
  untouched, and `tests/test_catalog_resolution.py` still gates renames.
- **`core.v_game` carries no derived result column.** `home_margin` and `total_points` were
  deliberately omitted even though both inputs are on the row: naming a result-informed
  value in a convenience view is how one gets swept into a pre-game feature set untagged.
  Callers who want margin write the subtraction and own that choice.
- **The 44 notes are not a validated data dictionary.** They restate the contracts recorded
  in `data-flow-guide.md` and the core DDL doc. They have not been independently re-derived
  from the data, except for the grain claims measured above.
- **No primary key was added to `core.fact_game_odds`**, although
  `(event_id, book, market, side, pulled_at)` is unique today (113,130/113,130). `pulled_at`
  is second-resolution and shared by every row of a snapshot run — only 40 distinct values
  across the whole table — so a retry or an overlapping 6-hourly pull landing in the same
  second would collide and fail the 05:00 rebuild inside `build_core`. The grain is recorded
  in the table's note instead.
- **The orphan counts are a snapshot**, re-measured on each build. The numbers in the table
  above describe the 2026-09-18 warehouse, not a permanent property.
- **`source_system` is coarser than provenance.** It says which pipeline wrote a table, not
  which vendor endpoint or which pull date. `meta.load_report` and
  `scripts/audit_graphql_dump_age.py` own freshness.

## Relationship to the HTML catalog

[cfb-warehouse-catalog.html](cfb-warehouse-catalog.html) remains the browsable reference
with columns, types and sample rows; the dictionary is the SQL-queryable subset. They are
not duplicates of each other's content: the catalog's `origin_of` is a deliberately coarser
four-way classifier whose output is pinned by `tests/test_warehouse_catalog.py` and baked
into the rendered HTML, and its `DOMAIN_RULES` grouping is editorial and stays there.
`source_system_of` is a separate ~10-line derivation over
`GQL_ENTITY_TO_RAW`/`GQL_ENTITY_TO_STG` (which the catalog already imports *from* the
package) plus vendor name prefixes. Folding the two classifiers together, and lifting
`DOMAIN_RULES` into the package so domains are queryable in SQL, is a reasonable follow-up
and was left out of this change on purpose.
