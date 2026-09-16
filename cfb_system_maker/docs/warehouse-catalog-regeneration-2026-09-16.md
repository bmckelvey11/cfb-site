# Warehouse catalog regeneration — 2026-09-16

## Question

`docs/cfb-warehouse-catalog.html` was last built by hand on 2026-08-29. What had
changed in the warehouse since, and can the catalog be regenerated rather than
re-typed?

## Method

`scripts/build_warehouse_catalog.py` rewrites the catalog's embedded
`const DATA = {...}` block from live introspection of `cfb.duckdb` (read-only)
plus the loader's own GraphQL destination maps. The HTML/CSS/JS shell around it
stays hand-written and untouched.

Before writing the generator, the old `DATA` block was parsed back into Python
and diffed against the live database to recover the classification rules the
hand-built catalog had applied but never written down. Those rules are now in
the script and pinned by `tests/test_warehouse_catalog.py` (18 tests).

Data: local `cfb.duckdb`, 5.0 GB, loaded 2026-09-16 17:25 UTC via
`refresh_cfbd.py` — 119 raw + 28 stg tables reported, 0 load errors, 0 empty.
Reproduce with `python scripts/build_warehouse_catalog.py` (`--check` to test
for staleness without writing).

## What changed since 2026-08-29

| | 2026-08-29 | 2026-09-16 |
| --- | --- | --- |
| tables | 233 | 322 |
| schemas | core, stg, raw, graphql, meta | core, stg, raw, meta |
| exploded stat columns | 925 | 1,947 |
| named box/play stats | 176 | 176 |

Per schema, now: `stg` 184 tables / 32,285,774 rows · `raw` 119 /
15,131,083 · `core` 18 / 441,917 · `meta` 1 / 147.

The catalog was stale in structure, not only in counts. Two migrations had
landed underneath it:

- **ADR-0003 collapsed `stg_gql` on 2026-09-10.** The `graphql` schema is gone.
  GraphQL dumps land in `raw` under a `gql_` prefix and collapse into `stg`
  beside REST, with a `_gql` suffix on exactly the three names REST also owns
  (`calendar`, `draft_picks`, `predicted_points`).
- **The camelCase → snake_case rename.** The old catalog listed
  `stg.adjustedPlayerMetrics`, `stg.coachSeason`, `stg.gameLines`; those
  spellings no longer exist.

65 catalogued tables were dropped (36 `graphql.*`, 27 camelCase `stg.*`,
`raw.actionnetwork_odds` → `raw.an_odds`, and one stray
`pff_facet_offense_summary_21580`). 154 were added, the largest groups being
21 PFF tables, 34 `raw.gql_*` dumps, 11 `advanced_box_score__*` explosions and
10 new `core` tables (`dim_coach`, `dim_draft_pick`, `dim_recruit`,
`fact_coach_season`, `fact_game_historical`, `fact_game_odds`,
`fact_team_talent`, plus three audit tables).

## The three rules that are not introspectable

Most of `DATA` is mechanical (row counts, column counts, types). Three fields
carry judgement, and a naive rebuild would have destroyed them.

### origin — the only surviving record of transport

With the `graphql` schema gone, `o` is the one place the catalog still records
whether a table came over REST or GraphQL. It is derived from
`GQL_ENTITY_TO_RAW` / `GQL_ENTITY_TO_STG` in `cfb_system_maker/graphql_client.py`
rather than carried forward from the old file, so it stays correct as those maps
change. All 34 GraphQL destinations resolve in both schemas. The pairs this
keeps apart, e.g.:

| table | origin | rows |
| --- | --- | --- |
| `stg.coach_season` | GraphQL | 12,564 |
| `stg.coach_seasons` | REST | 2,099 |

### domain — token matching, and children inherit their root

The hand-built catalog's domain assignments were not reproducible by substring
matching: `play` matches `players` and `playoff`, `line` matches `line_scores`.
The rules now match whole name tokens, and an exploded child takes the domain of
the root before `__` — `advanced_box_score__teams_rushing` is a game table
because `advanced_box_score` is, not a player table because its leaf says
`rushing`.

Rule order encodes the old catalog's judgement calls: `personnel` (recruiting,
draft, transfers) outranks the generic `players`; a derived rating outranks the
thing it rates (`kicker_paar`); a per-game team table is a game table
(`team_stats`, `records`).

This agrees with the hand-built catalog on **164 of 168 surviving tables**.

### wstats — what counts as a measurement

Numeric and boolean columns, minus keys (`*_id`, `*Id`, bare `id`), calendar
grain (`season`, `year`, `week`), kickoff clock parts and `_`-prefixed loader
columns. Booleans are `flag`, the rest `stat`. Recovered by diffing the old
`wstats` list against live column types — every numeric column the old catalog
omitted matches one of those exclusions.

## What this does *not* support

- **The 4 remaining domain disagreements are not resolved, they are overruled.**
  `pregame_win_prob` (old: betting) and `win_probability` (old: games) are both
  filed under `ratings` now. The old catalog put two win-probability tables in
  two different domains; picking one is a judgement call, not a derivation.
- **Domain is a presentation grouping, not a contract.** Nothing reads `g`
  except the catalog's own filter pills. It is not provenance and should not be
  joined on.
- **This says nothing about data quality.** The catalog counts rows and columns.
  It does not check freshness, nulls, NaN-vs-NULL in `stg_gql` numerics, or
  whether any table is correct — `scripts/audit_data_hygiene.py` and
  `scripts/audit_coverage.py` own that.
- **`named` counts are row counts, not distinct entities.** `stat_categories`
  is a name catalog with no fact rows, so its `n` is reported as 0 by
  construction rather than measured.
- **Row counts are a point-in-time snapshot** of the 2026-09-16 13:25 EDT load.
  `loaded` in `DATA` records the build date; `--check` is what tells you the
  file has drifted from the database.

## Verification

- `python scripts/build_warehouse_catalog.py --check` → clean.
- `python -m pytest` → 970 passed, 2 skipped.
- Page rendered and driven in a browser: header reads "322 tables across 4
  schemas", donut shows 4 schemas, 322 of 322 tables list, search and
  schema/domain filters work, Stats pane totals 1,947 columns + 176 named
  = 2,123. No console errors.

## Two staleness signals, deliberately different

- `--check` is **byte-exact**. It is the human-invoked "should I regenerate?"
  question, and it fires on row drift, which is what you want after a refresh.
- `test_committed_catalog_matches_the_live_warehouse` compares **structure
  only** — tables minus row counts, wstats, named unordered, domainOrder,
  coreNote. Row counts move on every `refresh_cfbd.py`, and the root
  `CLAUDE.md` makes `python -m pytest` the default gate, so a volume-sensitive
  assertion there would redden the suite on unrelated work. The test still
  catches a table appearing or vanishing, a column set changing, and an origin
  or domain shift.

## Related

- `cfb_system_maker/docs/data-flow-guide.md` — how data reaches these tables.
- `docs/stg-gql-collapse-2026-09-10.md` — ADR-0003, why `graphql` is gone.
