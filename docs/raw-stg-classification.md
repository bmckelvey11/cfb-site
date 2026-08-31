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

1. **No temporal types at all.** Zero `DATE` or `TIMESTAMP` columns exist in `stg`,
   against 34 columns named for a date or time. `startDate` is a VARCHAR.
2. **`actionnetwork_odds` is never staged.** It is the only `raw` table already flat
   (23 typed columns, live odds shape). No `stg` counterpart, so it is invisible to
   anything reading the staged layer.
3. **camelCase carried through.** `gameId`, `awayTeam`, `adjustedPlayerMetrics` come
   straight from the source JSON keys. Defensible in `raw`; a real cost in `stg`, where
   it forces quoting and blocks generated SQL.

Ordered by payoff: (1) is the cheapest fix with the widest blast radius — every date
comparison downstream is currently string math.

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
