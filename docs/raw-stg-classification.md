# raw ↔ stg Classification

Audit of every `stg` table against its `raw` counterpart, to answer whether `stg` earns
its footprint or is passthrough duplication.

Run 2026-08-31 against **local `C:\Users\mckel\dev\cfb\data\cfb.duckdb`** (source of truth per
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

## Separately: prefix-sampled structure inference silently nulled whole columns

**Fixed 2026-08-31.** Found while verifying the above, and it *was* a `stg` issue — the
first reading here ("the opening number exists in `stg`; the core build never carries it
across") was wrong on both halves. `duckdb_core.py` reads `spreadOpen` correctly, and
`stg` did not hold the value to carry: `stg.lines.lines.spreadOpen` and
`stg.gameLines.spreadOpen` were 0 non-null, so no `core` rebuild could have fixed it.

`_payload_structure` typed each `raw` table from `json_group_structure` over a
`LIMIT 5000` **prefix**. Raw rows load season-ordered, so that sample saw only the oldest
seasons, where the sportsbook API had not yet returned opening numbers or moneylines. Keys
absent from the sample come back typed `"NULL"`, and `json_transform` then materializes
the column as all-NULL — discarding every value in the other 33,689 rows without an error.

Five `core` columns were empty, not one:

| table.column | before | after |
|---|---:|---:|
| `fact_game_line.spread_open` | 0 | 8,413 |
| `fact_game_line.total_open` | 0 | 6,917 |
| `fact_game_line.moneyline_home` | 0 | 7,908 |
| `fact_game_line.moneyline_away` | 0 | 7,899 |
| `fact_game.venue_id` | 0 | 46,794 |

`spread_close` (38,600) and row counts (38,689 / 54,264) are unchanged, confirming the
rebuild restored columns without disturbing what already worked.

Diffing sampled-vs-repaired structure across all 119 `raw` tables that carry `payload`,
5 have keys to repair — the rest are unaffected:

| raw table | keys repaired |
|---|---:|
| `games` | 9 (`venueId`, `attendance`, `notes`, line scores, postgame win prob, …) |
| `game` | 9 (GraphQL twin of the above) |
| `lines` | 4 |
| `gameLines` | 4 |
| `pollRank` | 2 (`firstPlaceVotes`, `points`) |

`stg.games`, `stg.game`, `stg.pollRank`, `stg.lines`, and `stg.gameLines` were re-exploded
and `core` rebuilt. Nine further tables keep `"NULL"` keys after the repair — either the
key is genuinely always null, or the table is too large to scan (`plays`,
`gamePlayerStat`); those keep today's behavior rather than regressing.

Restored `stg.games` columns include result-informed ones (`homePostgameWinProbability`,
`excitementIndex`, line scores). `core` does not read them, but anything that starts to
must respect the root `CLAUDE.md` no-lookahead rule.

Watch out when re-running: `explode_payloads` already calls
`backfill_gamelines_from_actionnetwork` and `promote_timestamp_columns` at the end, and
that backfill is **not idempotent** — calling it again on an already-backfilled
`stg.gameLines` re-adds the Action Network rows (63,293 → 79,821). Re-explode `gameLines`
in the same run rather than invoking the backfill directly.

The fix keeps the cheap prefix sample and repairs **only** keys it typed `"NULL"`,
re-inferring those from a full-table scan (falling back to the sample when it will not fit
in memory — `raw.plays` and `raw.gamePlayerStat` still OOM a full scan). Widening the
sample wholesale would have been wrong: `raw.gameLines.overUnder` is 8.8% `"NaN"` strings,
so any broader sample retypes it from DOUBLE to JSON. Repairing unseen keys only cannot
retype a key the sample already resolved.

`meta.warehouse_version` is still absent locally, so this `core` predates the documented
build — but that was a red herring, not the cause.

## Mirror drift

~~`md:cfb` disagrees with the source of truth.~~ **Re-synced 2026-08-31** via
`scripts/promote_to_motherduck.py --yes`, after the structure-inference fix above and a
`core` rebuild. All 248 tables promoted, every row count matching:

| | local (truth) | `md:cfb` before | `md:cfb` after |
|---|---:|---:|---:|
| `raw` tables | 120 | 115 | 120 |
| `stg` tables | 119 | 116 | 120 |
| `stg.gamePlayerStat` rows | 5,541,660 | 1,696,159 | 5,541,660 |
| `core.fact_game_line.spread_open` | 8,413 | 0 | 8,413 |

Both sides are now stamped `meta.warehouse_version` = `70e163c` — that table previously
did not exist locally at all, which is why the pre-fix `core` looked undated.

Two caveats for the next promote:

- **The script never drops.** It uses `CREATE OR REPLACE TABLE` per table, so anything
  retired locally survives on the mirror indefinitely. `md.stg.ppa_games_defense` was one
  such leftover (21,392 rows sourced from the retired `cfb-site` repo) and was dropped
  manually after checking every row already existed in local `stg.ppa_games`; its only 10
  divergent values were stale pre-revision PPA for five multi-overtime games. Table counts
  now match exactly at 120/119/8/2. A view, `md.stg.venue_orientation_labeled` (497 rows),
  still has no local counterpart — views are outside the promote's table-only contract.
- **The copy needs a memory budget.** The first attempt died with
  `OutOfMemoryException: Allocation failure` partway through `raw`, leaving the mirror
  half-updated (`core` new, `stg` stale) — the promote is not atomic, and a failure
  mid-run is a mixed state, not a no-op. The script now sets `memory_limit`,
  `preserve_insertion_order=false`, and a `temp_directory` so million-row tables spill
  instead of aborting.
