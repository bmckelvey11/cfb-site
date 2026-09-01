# raw ↔ stg Classification

Audit of every `stg` table against its `raw` counterpart, to answer whether `stg` earns
its footprint or is passthrough duplication.

Run 2026-08-31 against **local `C:\Users\mckel\data\cfb\cfb.duckdb`** (source of truth per
root `CLAUDE.md`), not the `md:cfb` mirror. The mirror is stale and gives different
answers — see "Mirror drift" below.

## Verdict

**`stg` is not passthrough.** Zero tables fall in the passthrough bucket. `raw` is a JSON
landing zone, not a table-shaped mirror; `stg` is the shred that makes it queryable. The
layer is doing real work and should stay materialized.

This retires the claim that `stg` duplicates `raw`. That claim came from matching table
*names* across the two schemas without looking at columns.

## Why the name-match reading was wrong

119 of 120 `raw` tables share one identical 5-column signature:

```
payload, season, season_type, source_file, week
```

`payload` is the undecoded API response. Every `raw` table is the same shape regardless of
what it holds. `stg.games` has 44 typed columns; `raw.games` has 5. Same name, unrelated
structure.

The single exception is `raw.actionnetwork_odds` (23 pre-flattened columns) — see gaps.

## Buckets

| Bucket | Tables | Notes |
|---|---:|---|
| **JSON shred + typing, 1:1 rows** | 115 | `payload` unnested to typed columns |
| **JSON shred + fan-out** | 4 | payload arrays unnested, row count multiplies |
| Passthrough | **0** | — |
| Typed cleanup only | **0** | — |
| Filtered / deduped / business-rule | **0** | no row loss anywhere |
| raw-only (never staged) | 1 | `actionnetwork_odds` |
| stg-only (no raw source) | 0 | — |

### The four fan-outs

| Table | raw | stg | Reading |
|---|---:|---:|---|
| `actionnetwork_history` | 10,974 | 149,997 | line-movement arrays unnested |
| `actionnetwork_scoreboard` | 175 | 10,868 | scoreboard arrays unnested |
| `gameLines` | 38,647 | 63,293 | one row per game per provider |
| `linesProvider` | 12 | 17 | array unnest |

All four go **up**. No `stg` table has fewer rows than its `raw` source, so nothing in
this layer filters or dedupes. `stg` is a pure shred.

## What `stg` adds

- **Typing.** 2,088 columns: DOUBLE 560, UBIGINT 498, INTEGER 221, BOOLEAN 27, plus
  nested `STRUCT[]` preserved from source (box scores, poll ranks, CFP brackets).
  VARCHAR is 743 — about 35%.
- **Partition keys retained.** 117 of 119 `stg` tables keep `season`, `week`, and
  `seasonType`. The two that don't are `actionnetwork_history` and `gameLines`, both
  fan-outs that carry `gameId` instead.
- **Lineage.** All 119 carry `source_file`.

## Gaps

1. ~~**No temporal types at all.**~~ **Fixed 2026-08-31.** 20 VARCHAR date/time columns
   were promoted to `TIMESTAMPTZ` by `promote_timestamp_columns` in `duckdb_load.py`,
   which also runs at the end of every `explode_payloads`. Source strings arrive in three
   shapes — REST `2023-09-02 16:00:00+00:00`, GraphQL naive `2023-09-02T16:00:00`, and
   Action Network `...T23:30:00.000Z` — and naive values are stamped UTC rather than left
   to the session timezone. The three remaining VARCHARs (`venues.timezone`,
   `teams.location_timezone`, `fbs_teams.location_timezone`) hold IANA zone names and are
   correctly excluded: promotion requires every non-null value to parse.

   Five of the 20 are ad-hoc snapshot dumps (`lines_2026_week1`,
   `lines_2026_week1_20260826`, and siblings). They have no `raw` counterpart and are
   outside the shred contract, so they were promoted opportunistically and will drift
   back to VARCHAR if something recreates them by another path.
2. **`actionnetwork_odds` is never staged.** It is the only `raw` table already flat
   (23 typed columns, live odds shape). No `stg` counterpart, so it is invisible to
   anything reading the staged layer.
3. **camelCase carried through.** `gameId`, `awayTeam`, `adjustedPlayerMetrics` come
   straight from the source JSON keys. Defensible in `raw`; a real cost in `stg`, where
   it forces quoting and blocks generated SQL.

Remaining, ordered by payoff: (2) then (3).

## Separately: `core.fact_game_line.spread_open` is entirely NULL

Not a `stg` issue, found while verifying the above. All 38,689 rows in
`core.fact_game_line` have `spread_open IS NULL` (against 89 NULL `spread_close`), so
`tests/test_core_agreement.py::test_live_warehouse_agreement_4_5_6` fails on
`assert row[1] == moves["spread_open"]`. The opening number exists in `stg`; the core
build never carries it across. `meta.warehouse_version` is also absent locally, so this
`core` predates the documented build.

## Mirror drift

`md:cfb` disagrees with the source of truth and should not be audited in its place:

| | local (truth) | `md:cfb` |
|---|---:|---:|
| `raw` tables | 120 | 115 |
| `stg` tables | 119 | 116 |
| `stg.gamePlayerStat` rows | 5,541,660 | 1,696,159 |

The mirror is missing five `raw` tables and is 69% short on `gamePlayerStat`. It also
carries `ppa_games_defense` and the `venue_orientation_labeled` view, which have no
counterpart locally. Re-sync before anyone reads `md:cfb` as current.
